"""Classify scraped reviews with Mistral, then aggregate them deterministically.

The LLM's only job here is per-review labelling (sentiment / themes / complaint category).
Every statistic derived from those labels is computed in Python, so the numbers the report
quotes cannot drift with the model's mood.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import Counter, defaultdict

from app.core.config import get_settings
from app.services.llm.core.gateway import build_mistral_gateway
from app.services.llm.utils import extract_json
from app.schemas.scraping import (
    AnalysisSummary,
    ReviewClassification,
    ScrapedReview,
    TopicCount,
)

logger = logging.getLogger(__name__)

# Total reviews sent for classification across all channels. Higher coverage means the
# frequency counts mean something. Deliberately set to exactly one concurrency wave
# (_MAX_CONCURRENCY * _CHUNK_SIZE): the report only surfaces the main complaint dimensions
# and headline sentiment, both of which are stable well below this, so a second wave would
# spend extra Mistral calls and latency to sharpen a long tail nobody reads. Note the rating
# histogram is computed from every collected review regardless -- the cap only bounds the
# semantic layer, never the headline numbers.
_MAX_CONCURRENCY = max(1, int(os.getenv("SOCIAL_CLASSIFY_MAX_CONCURRENCY", "1")))
_CHUNK_SIZE = max(1, int(os.getenv("SOCIAL_CLASSIFY_CHUNK_SIZE", "30")))
_MAX_REVIEWS_TO_CLASSIFY = max(
    _CHUNK_SIZE,
    int(os.getenv("SOCIAL_CLASSIFY_MAX_REVIEWS", str(_MAX_CONCURRENCY * _CHUNK_SIZE))),
)


def _select_balanced_sample(reviews: list[ScrapedReview]) -> list[ScrapedReview]:
    """Pick which reviews to classify, giving every channel a fair share.

    Round-robin across channels rather than a fixed per-channel quota, so the logic holds
    for any number of platforms and a quiet channel never starves a busy one.
    """
    if len(reviews) <= _MAX_REVIEWS_TO_CLASSIFY:
        return list(reviews)

    by_platform: dict[str, list[ScrapedReview]] = defaultdict(list)
    for review in reviews:
        by_platform[review.platform].append(review)

    selected: list[ScrapedReview] = []
    queues = list(by_platform.values())
    cursor = 0
    while len(selected) < _MAX_REVIEWS_TO_CLASSIFY and any(queues):
        queue = queues[cursor % len(queues)]
        if queue:
            selected.append(queue.pop(0))
        else:
            queues.remove(queue)
            continue
        cursor += 1
    return selected


def _build_prompt(brand_name: str, chunk: list[ScrapedReview]) -> str:
    payload = [
        {"index": idx, "platform": r.platform, "text": r.text, "rating": r.rating}
        for idx, r in enumerate(chunk)
    ]
    dimensions_block = "\n".join(f"- {d}" for d in _COMPLAINT_DIMENSIONS)
    return f"""You are an expert customer experience (CX) analyst specializing in multi-lingual social media feedback analysis.
Classify each of the following reviews about the brand '{brand_name}'.

The reviews may be in French, Arabic (Standard & North African / Tunisian Derja / Arabizi), English, or mixed languages.
ALWAYS respond in ENGLISH: every label you produce is printed in an English-language client report.

SPECIAL SENSITIVITY & NUANCE RULES:
1. SARCASM & IRONY DETECTION:
   - Carefully analyze sarcastic praise or ironic compliments (e.g. "Bravo TT 👏 10h sans internet", "يعطيهم الصحة على السيرفيس الروعة", "شكرا على خدماتكم الممتازة" when followed by complaints).
   - Sarcastic or ironic statements where the customer is expressing frustration MUST be classified as "negative".
2. NORTH AFRICAN & TUNISIAN DERJA DIALECT:
   - Recognize regional expressions, idioms, and mixed French-Arabic phrases (e.g. "ريزوا قاصص", "تحيل", "تعبتونا", "خايب", "ما لقاوش حل").
   - Focus on the true underlying customer emotion and satisfaction level rather than literal dictionary words.
3. SPAM & NON-OPINION CHATTER:
   - If a text carries no actual customer sentiment or opinion, classify sentiment as "neutral" with lower confidence.
4. MIXED REVIEWS & UNRESOLVED ISSUES:
   - If a customer begins with polite or surface praise but reports an unresolved complaint, long wait time, or persistent issue (e.g. "Service au top, 3 mois ntaba3 m3ahom ma l9awch 7al"), classify the overall sentiment as "negative".

For EACH review, determine:
1. Sentiment polarity: "positive", "neutral", or "negative".
2. A confidence score (0.0 to 1.0).
3. The key topics discussed. Maximum 3 topics.
4. If the sentiment is "negative", the matching complaint category. Otherwise null.
5. "is_advertisement": true ONLY if the post is promotional content rather than a genuine
   customer opinion — e.g. it advertises a product/offer/promo/new plan, announces a giveaway
   or contest, is affiliate/marketing spam, or links to sell something. A real customer complaint
   or compliment is NOT an advertisement, even if it mentions a product or price. When unsure,
   set false.

No industry is assumed: derive the TOPICS from what the reviews actually say. For a telecom
they will concern network or billing, for a restaurant the food or table service, for a bank
fees or processing times.

RULE for 'themes' — the specific SUBJECT the review is about, in the brand's own domain:
SHORT English labels (1 to 3 words), reused verbatim from one review to the next
(for example "Network", "Fibre", "Food quality", "Delivery", "Bank fees"). These labels are
counted, so two phrasings of one subject would corrupt the statistics.

RULE for 'complaint_category' — the DIMENSION of the problem, which MUST be chosen from the
closed list below and copied exactly. These dimensions are universal and apply to any
industry; the precise detail of the problem belongs in the topic, not here.
Never invent another value: use "Other" if none fits.
{dimensions_block}

You must return EXACTLY one object per review, carrying its original index.

Expected response format (JSON only, no markdown):
{{
  "classifications": [
    {{"index": 0, "sentiment": "negative", "confidence": 0.9,
      "themes": ["Billing"], "complaint_category": "Pricing, billing and fees",
      "is_advertisement": false}}
  ]
}}

Reviews to classify:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return only valid JSON, with no surrounding text or markdown.
"""



def _parse_response(response_text: str) -> list[dict]:
    result_dict = extract_json(response_text)
    if not result_dict:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        result_dict = json.loads(cleaned)
    return result_dict.get("classifications", []) or []


_VALID_SENTIMENTS = {"positive", "neutral", "negative"}

# Universal CX complaint dimensions. NOT a domain vocabulary -- these are the axes any
# business is judged on, so they map onto a restaurant, a bank or a telecom equally well
# (food -> quality, waiter -> staff, table wait -> waiting; app outage -> reliability...).
# Themes stay fully open and carry the domain-specific detail; complaints snap to this fixed
# analytical frame because an open complaint vocabulary fragments into synonyms ("service
# nul" / "service médiocre" / "mauvaise qualité") that no structural merge can reunite,
# which understates the very problems the report is meant to rank.
_COMPLAINT_DIMENSIONS = [
    "Product or service quality",
    "Staff and customer relations",
    "Wait times and delays",
    "Pricing, billing and fees",
    "Reliability and outages",
    "Information and communication",
    "Access and availability",
    "Administrative processes",
    "Other",
]


def _clean_labels(raw_labels, limit: int) -> list[str]:
    """Trim, de-duplicate and cap a label list coming back from the model."""
    labels: list[str] = []
    seen: set[str] = set()
    for value in raw_labels:
        label = str(value).strip()
        if not label or label.casefold() in seen:
            continue
        seen.add(label.casefold())
        labels.append(label)
    return labels[:limit]


def _fold(value: str) -> str:
    import unicodedata

    stripped = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(ch for ch in stripped if not unicodedata.combining(ch))


_DIMENSION_BY_FOLD = {_fold(d): d for d in _COMPLAINT_DIMENSIONS}


def _snap_complaint(raw: str | None) -> str | None:
    """Snap a returned complaint onto the fixed dimension list.

    Exact match (accent/case tolerant) first; then a token-overlap fallback so a close
    paraphrase still lands on a dimension rather than silently becoming 'Autre'. Anything
    genuinely unrecognised becomes 'Autre' -- never free text, or the counting fragments.
    """
    if not raw:
        return None
    folded = _fold(raw)
    if folded in _DIMENSION_BY_FOLD:
        return _DIMENSION_BY_FOLD[folded]

    raw_tokens = {t for t in folded.split() if len(t) > 3}
    best, best_overlap = "Other", 0
    for dimension in _COMPLAINT_DIMENSIONS[:-1]:  # skip 'Other' itself
        dim_tokens = {t for t in _fold(dimension).split() if len(t) > 3}
        overlap = len(raw_tokens & dim_tokens)
        if overlap > best_overlap:
            best, best_overlap = dimension, overlap
    return best


async def _classify_chunk(
    gateway,
    brand_name: str,
    chunk: list[ScrapedReview],
    semaphore: asyncio.Semaphore,
) -> None:
    """Classify one chunk in place.

    Indices are resolved against `chunk` itself -- the exact list that was serialised into
    the prompt -- so a label can never be attached to a different review than the one it
    describes.
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON objects."},
        {"role": "user", "content": _build_prompt(brand_name, chunk)},
    ]
    try:
        async with semaphore:
            response_text = await gateway.chat_messages(messages)
        entries = _parse_response(response_text)
    except Exception:
        logger.exception("Classification chunk failed (%d reviews) — left unclassified", len(chunk))
        return

    for entry in entries:
        try:
            index = entry.get("index")
            if not isinstance(index, int) or not 0 <= index < len(chunk):
                continue
            sentiment = (entry.get("sentiment") or "").strip().lower()
            if sentiment not in _VALID_SENTIMENTS:
                sentiment = "neutral"
            try:
                confidence = float(entry.get("confidence") or 0.8)
            except (TypeError, ValueError):
                confidence = 0.8
            raw_complaint = entry.get("complaint_category")
            complaint = (
                _snap_complaint(str(raw_complaint)) if raw_complaint and sentiment == "negative" else None
            )
            chunk[index].classification = ReviewClassification(
                sentiment=sentiment,
                confidence=max(0.0, min(1.0, confidence)),
                themes=_clean_labels(entry.get("themes") or [], limit=3),
                complaint_category=complaint,
                is_advertisement=bool(entry.get("is_advertisement")),
            )
        except Exception:
            logger.warning("Skipping malformed classification entry: %s", entry)


# Words carrying no topical meaning, ignored when deciding whether two theme labels are
# variants of each other.
_THEME_STOPWORDS = {
    "de", "du", "des", "d", "la", "le", "les", "l", "un", "une",
    "et", "ou", "a", "au", "aux", "en", "sur", "pour", "par", "avec",
}


def _theme_tokens(label: str) -> frozenset[str]:
    """Reduce a label to its meaningful word stems for comparison.

    Accent-, case-, punctuation- and plural-insensitive, so 'Délais' and 'delai' collapse
    onto the same token.
    """
    import re
    import unicodedata

    folded = unicodedata.normalize("NFKD", label.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    tokens = set()
    for word in re.split(r"[^a-z0-9]+", folded):
        if not word or word in _THEME_STOPWORDS:
            continue
        # Crude singular form: enough to merge 'delais'/'delai', 'pannes'/'panne'.
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        tokens.add(word)
    return frozenset(tokens)


def _build_mapping(counts: Counter[str]) -> dict[str, str]:
    """Map every label variant onto the dominant spelling of its group.

    Two labels merge when one's meaningful tokens are a subset of the other's. The variant
    that occurs most often wins, since the dominant phrasing is the one the reader should
    see. Labels with no subset relation are left alone: 'Qualité du réseau' and 'Qualité du
    service' share a token but neither contains the other, so they stay distinct.
    """
    if not counts:
        return {}

    # Most frequent first, so a variant always merges into the dominant spelling.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    canonical_tokens: list[tuple[frozenset[str], str]] = []
    mapping: dict[str, str] = {}
    for label, _count in ordered:
        tokens = _theme_tokens(label)
        if not tokens:
            mapping[label] = label
            continue
        for known_tokens, known_label in canonical_tokens:
            if tokens <= known_tokens or known_tokens <= tokens:
                mapping[label] = known_label
                break
        else:
            canonical_tokens.append((tokens, label))
            mapping[label] = label
    return mapping


def canonicalize_themes(reviews: list[ScrapedReview]) -> dict[str, str]:
    """Reconcile the open theme vocabulary across chunks.

    Chunks are independent LLM calls, so one may answer 'Qualité du réseau' where another
    answers 'Réseau'. Counting the raw strings splits one topic into several small rows and
    understates it. No prompt can fix this -- the calls never see each other -- so themes
    are reconciled here, once, after every chunk has returned. This is what lets the theme
    vocabulary stay open and still work for a telecom, a restaurant or a bank.

    Complaints are NOT reconciled here: they were snapped to the fixed dimension list at
    classification time, precisely because an open complaint vocabulary fragments into
    synonyms ('service nul' / 'service médiocre') that share no token and so never merge.
    """
    theme_counts: Counter[str] = Counter()
    for review in reviews:
        if review.classification:
            for theme in set(review.classification.themes or []):
                theme_counts[theme] += 1

    theme_map = _build_mapping(theme_counts)
    merged = {src: dst for src, dst in theme_map.items() if src != dst}
    if merged:
        logger.info("Merged %d theme variant(s): %s", len(merged), merged)

    for review in reviews:
        if not review.classification:
            continue
        rewritten: list[str] = []
        for theme in review.classification.themes or []:
            canonical = theme_map.get(theme, theme)
            if canonical not in rewritten:  # a review can hold two variants of one theme
                rewritten.append(canonical)
        review.classification.themes = rewritten

    return theme_map


def _build_summary(reviews: list[ScrapedReview]) -> AnalysisSummary | None:
    """Aggregate the labels arithmetically. No LLM involved, so the percentages always
    add up and always match the reviews actually shown in the report."""
    classified = [r for r in reviews if r.classification]
    total = len(classified)
    if total == 0:
        return None

    pos = sum(1 for r in classified if r.classification.sentiment == "positive")
    neu = sum(1 for r in classified if r.classification.sentiment == "neutral")
    neg = sum(1 for r in classified if r.classification.sentiment == "negative")

    theme_counts: Counter[str] = Counter()
    complaint_counts: Counter[str] = Counter()
    for review in classified:
        for theme in set(review.classification.themes or []):
            theme_counts[theme] += 1
        if review.classification.sentiment == "negative" and review.classification.complaint_category:
            complaint_counts[review.classification.complaint_category] += 1

    return AnalysisSummary(
        positive_pct=round(pos / total * 100, 1),
        neutral_pct=round(neu / total * 100, 1),
        negative_pct=round(neg / total * 100, 1),
        top_themes=[label for label, _ in theme_counts.most_common(5)],
        top_complaints=[TopicCount(topic=label, count=n) for label, n in complaint_counts.most_common(5)],
        summary_text=None,  # the narrative lives in the unified report's executive summary
    )


async def classify_reviews(
    reviews: list[ScrapedReview],
    brand_name: str,
) -> tuple[list[ScrapedReview], AnalysisSummary | None]:
    """Classify reviews in place and return them alongside a deterministic summary.

    Reviews outside the sampled subset keep `classification = None` and are simply excluded
    from every statistic, rather than inheriting a neighbour's label.
    """
    if not reviews:
        return reviews, None

    # Star-only reviews carry no text to classify. They still count toward the rating
    # distribution, but sending them to the model would waste a slot in the sample.
    with_text = [r for r in reviews if r.text.strip()]
    if not with_text:
        return reviews, None

    sample = _select_balanced_sample(with_text)
    chunks = [sample[i : i + _CHUNK_SIZE] for i in range(0, len(sample), _CHUNK_SIZE)]

    try:
        settings = get_settings()
        gateway = build_mistral_gateway(settings)
    except Exception:
        logger.exception("Could not build the Mistral gateway — reviews left unclassified")
        return reviews, None

    logger.info(
        "Classifying %d of %d commented reviews (%d collected incl. star-only) for '%s' in %d chunk(s)",
        len(sample), len(with_text), len(reviews), brand_name, len(chunks),
    )
    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    # Chunks mutate their own review objects, so failures stay contained to one chunk.
    from app.services.observability.llm_metrics import llm_context

    with llm_context(feature="social.classify", kind="run"):
        await asyncio.gather(
            *(_classify_chunk(gateway, brand_name, chunk, semaphore) for chunk in chunks)
        )

    classified_count = sum(1 for r in reviews if r.classification)
    logger.info("Classified %d/%d reviews for '%s'", classified_count, len(reviews), brand_name)

    # Drop promotional/advertising posts the model flagged — they are not customer feedback and
    # must not pollute the reviews, the topics, or the sentiment stats.
    ads = sum(1 for r in reviews if r.classification and r.classification.is_advertisement)
    if ads:
        reviews = [r for r in reviews if not (r.classification and r.classification.is_advertisement)]
        logger.info("Filtered out %d advertisement post(s) for '%s'", ads, brand_name)

    # Reconcile the open theme vocabulary across chunks before anything counts it.
    # (Complaints were already snapped to fixed dimensions at classification time.)
    canonicalize_themes(reviews)

    return reviews, _build_summary(reviews)
