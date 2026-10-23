"""Competitor benchmarking: what sector leaders do about the client's weakest capabilities.

Given a sector, the respondent company and the pain points found by the diagnostic, this builds
the "leaders snapshot" that the maturity report's benchmark section is written from. Per
candidate leader the pipeline is:

  1. candidates come from `sector_leader_candidates` (a curated shortlist per sector);
  2. LangSearch web search, with queries built from the capability's retrieval phrases;
  3. semantic rerank of the results against the pain point, so the evidence actually matches
     the weakness rather than merely mentioning the company;
  4. a credibility filter on the source, because a marketing page is not evidence;
  5. the model evaluates the candidate against what was found and writes the insight.

The binding constraint here is the **search provider**, not the model: LangSearch has per-second,
per-minute and per-day limits (all in `Settings`), so this module owns retry-after parsing and a
bounded retry count, and a deterministic rerank fallback for when the reranker is unavailable.

**Naming is legacy and misleading.** The class is `SemanticLeadersService` and is sector-agnostic;
the module name and the `TelecomSemanticLeadersService` subclass both date from when this handled
telecom only. The subclass exists purely as a backward-compatible alias and adds no behaviour.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import re
from urllib.parse import urlparse
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import httpx

from app.core.config import Settings, get_settings
from app.core.text_normalization import normalize_text
from app.services.assessment.reporting.sector_leader_candidates import (
    LeaderCandidate,
    SECTOR_LEADER_CANDIDATES,
    get_capability_retrieval_phrases,
)


if TYPE_CHECKING:
    from app.services.llm.core.facade_service import LLMService

logger = logging.getLogger(__name__)

# ── EY methodology decks bundled with the app ───────────────────────────────────────────────
# Labels are stored per language rather than translated at runtime: these are client-facing
# titles chosen by the practice, not UI strings.

_EY_MASTER_DECK = {
    "url": "/assets/all.pptx",
    "fr": ("Présentation Méthodologie Globale EY",
           "Guide de référence de la méthodologie d'évaluation de l'expérience client EY et des piliers de maturité."),
    "en": ("EY Customer Experience Global Methodology Master Framework",
           "Master reference guide detailing the EY Customer Experience assessment methodology and maturity pillars."),
}

_EY_SECTOR_DECKS = {
    "healthcare": {
        # Filename is "finantial" for the financial deck below -- that is the asset that ships.
        "url": "/assets/healthcare.pptx",
        "fr": ("Présentation Maturité CX - Secteur Santé",
               "Analyse approfondie de la transformation de l'expérience patient et des parcours de soins."),
        "en": ("CX Maturity Framework - Healthcare Sector",
               "Deep-dive analysis on transforming patient experience and healthcare journeys."),
    },
    "financial": {
        "url": "/assets/finantial.pptx",
        "fr": ("Présentation Maturité CX - Services Financiers",
               "Stratégie d'optimisation de l'expérience client et de digitalisation dans la banque et l'assurance."),
        "en": ("CX Maturity Framework - Financial Services",
               "Strategy for optimizing customer experience and digitization in banking and insurance."),
    },
    "retail": {
        "url": "/assets/retail.pptx",
        "fr": ("Présentation Maturité CX - Retail & E-Commerce",
               "Guide pratique sur l'omnicanalité, la fidélisation et la réduction des frictions d'achat."),
        "en": ("CX Maturity Framework - Retail & E-Commerce",
               "Practical guide on omnichannality, customer loyalty, and checkout friction reduction."),
    },
}

# Several sector keys share one deck.
_EY_DECK_BY_SECTOR = {
    "healthcare": "healthcare",
    "banking_insurance": "financial",
    "banking": "financial",
    "insurance": "financial",
    "retail_ecommerce": "retail",
    "ecommerce": "retail",
    "retail": "retail",
}


def _deck_card(deck: dict, is_french: bool) -> dict:
    """One presentation entry in the shape the leader card expects."""
    label, why = deck["fr"] if is_french else deck["en"]
    return {
        "label": label,
        "url": deck["url"],
        "source_title": "EY Presentation",
        "mapped_capability": "Industry Benchmark",
        "why_relevant": why,
    }


# ── Source credibility rules ────────────────────────────────────────────────────────────────
# A benchmark claim is only as good as what it cites, so search results are filtered before the
# model ever sees them. The rules are data on purpose: adding a blocked domain or path is an edit
# to one named collection here, not a new branch inside a function.

# Scripts the report cannot render or read. Their presence means the wrong audience entirely.
# Leaders shown in the report, and how many are curated even when the model budget is smaller --
# a leader past the budget is still worth showing, just described deterministically.
_MAX_LEADERS_IN_REPORT = 3
_MIN_SHORTLIST = 3

# The word to use for the sector when searching EY's own publications. Their taxonomy does not use
# the sector names the assessment does, and a search for the wrong one returns nothing.
_SECTOR_SEARCH_LABELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("telecom",), "telecommunications"),
    (("health",), "healthcare"),
    (("hospitality", "travel"), "hospitality"),
)

# Bookkeeping the pipeline hangs on a leader while building it. Stripped before the snapshot
# leaves, so an internal score never reaches the report payload.
_INTERNAL_LEADER_KEYS = (
    "_semantic_score",
    "_pre_curation_score",
    "_curated_score",
    "_debug",
    "_mistral_calls",
    "_raw_links",
    "_coverage_capabilities",
    "_document_assessments",
    "_rejected_evidence",
)


def _sector_label(sector_key: str | None, sector: str) -> str:
    """EY's word for this sector, falling back to the assessment's own name."""
    key = (sector_key or "").lower()
    for terms, label in _SECTOR_SEARCH_LABELS:
        if any(term in key for term in terms):
            return label
    return sector


def _public_leader(leader: dict) -> dict:
    """One leader with the pipeline's internal bookkeeping removed."""
    return {key: value for key, value in leader.items() if key not in _INTERNAL_LEADER_KEYS}


# ── Scoring one candidate leader ────────────────────────────────────────────────────────────
# How many ranked hits to consider. A regeneration looks wider than the first pass, because it is
# usually run precisely because the first pass produced something thin.
_RERANK_TOP_N_INITIAL = 6
_RERANK_TOP_N_REGENERATE = 8

# Evidence kept per candidate, and how much of it the report shows.
_MAX_EVIDENCE_PER_CANDIDATE = 5
_EVIDENCE_LINKS_PER_LEADER = 3

# Adjustments to a candidate's average relevance. Both are small on purpose: they separate
# candidates that scored alike, and must not outweigh whether the evidence was relevant at all.
_SCORE_ADJUSTMENT_STEP = 0.01
# Evidence spread across several publishers is worth more than several pages from one site.
_MAX_DIVERSITY_STEPS = 2
# Repeatedly finding the same story back is a sign of a thin result set.
_MAX_DEDUP_PENALTY_STEPS = 2


@dataclass(frozen=True)
class _CandidateScore:
    """A candidate's score, kept as its parts so the debug endpoints can show the working."""

    average_relevance: float
    diversity_bonus: float
    dedup_penalty: float

    @property
    def total(self) -> float:
        return self.average_relevance + self.diversity_bonus - self.dedup_penalty


@dataclass(frozen=True)
class _CandidateEvidence:
    """What researching one candidate turned up, and what it cost to get there.

    The skip count is kept rather than discarded because it is evidence in itself: a candidate
    whose results were mostly duplicates of each other was not well covered.
    """

    evidence: list[dict[str, str | None]]
    unique_domains: set[str]
    dedup_skips: int
    cumulative_relevance_score: float

    def score(self) -> _CandidateScore:
        return _CandidateScore(
            average_relevance=self.cumulative_relevance_score / max(len(self.evidence), 1),
            diversity_bonus=min(max(len(self.unique_domains) - 1, 0), _MAX_DIVERSITY_STEPS)
            * _SCORE_ADJUSTMENT_STEP,
            dedup_penalty=min(self.dedup_skips, _MAX_DEDUP_PENALTY_STEPS) * _SCORE_ADJUSTMENT_STEP,
        )


def _document_names_company(document: dict, *, url: str, company_name: str) -> bool:
    """Whether a page actually names the company, rather than merely ranking well for it.

    Without this the benchmark fills up with vendor marketing: a CX software page describing "how
    telecom operators improve retention" reranks beautifully against a telecom pain point while
    saying nothing about the operator we are supposed to be evidencing. The name is matched both
    as written and stripped of punctuation, so "Orange Tunisie" still matches "orange-tunisie".
    """
    name = company_name.lower()
    squashed_name = re.sub(r"[^a-z0-9]+", "", name)
    title = str(document.get("title") or "").lower()
    summary = str(document.get("summary") or "").lower()
    return (
        name in title
        or name in summary
        or squashed_name in re.sub(r"[^a-z0-9]+", "", title)
        or squashed_name in re.sub(r"[^a-z0-9]+", "", summary)
        or squashed_name in url.lower()
    )


# Evidence links shown under one leader in the report.
_MAX_CURATED_LINKS = 3
# Added to a candidate's score when its capability is not represented yet -- a tie-breaker towards
# breadth, deliberately too small to promote a genuinely weaker link.
_NEW_CAPABILITY_BONUS = 0.05

# EY's own search results arrive with the brand's boilerplate attached: a country suffix on every
# title, and a marketing tagline in most summaries. Both are stripped before a link is shown.
_EY_TITLE_SUFFIXES = (" | EY - Global", " | EY - US", " | EY - UK", " | EY - Taiwan", " | EY", " - EY")

_EY_TAGLINE_PHRASES = (
    "the better the question the better the answer",
    "building a better working world",
    "the world works case study",
    "case study the better the question",
)

# The benchmark card is a fixed-size box in the report, so its text is cut to fit.
_MAX_LEADER_SUMMARY_CHARS = 140
_MAX_LINK_LABEL_CHARS = 80
_MAX_WHY_RELEVANT_CHARS = 120

# Three links per card. The decks take the first slots and a web search fills what is left.
_EY_CARD_LINK_SLOTS = 3


def _truncate(text: str, limit: int) -> str:
    """Cut `text` to `limit` characters, counting the ellipsis against the limit."""
    return text if len(text) <= limit else text[: limit - 3] + "..."


_NON_LATIN_SCRIPTS = re.compile(
    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]"
)
# A two-letter subdomain is a language edition; only these two are readable here.
_ALLOWED_SUBDOMAIN_LANGUAGES = {"en", "fr"}
# A URL path segment naming a language, e.g. /de/ or /pt/.
_FOREIGN_LANGUAGE_DIRECTORY = re.compile(
    r"/(ar|es|ru|de|nl|hi|ja|zh|ko|it|pt|tr|pl|sv|no|fi|da|el|he|id|th|vi|cs|hu|ro|sk|bg)/",
    re.IGNORECASE,
)
_TITLE_WORDS = re.compile(r"\b[a-zßäöüáéíóúñãõçêâô]+\b")

# Not the production site: a staging or admin host is not evidence of anything.
_NON_PRODUCTION_SUBDOMAINS = {
    'admin', 'demo', 'dev', 'localhost', 'sandbox', 'stage', 'staging', 'test', 'www-test',
}

# Domains that never constitute evidence about a company's customer experience: complaint
# aggregators, crowd-sourced content, social platforms, SEO farms and press-release wires.
_UNRELIABLE_HOSTS = frozenset({
    '1888pressrelease.com', '51cto.com', 'apps.apple.com', 'bbb.org', 'buypapers.club',
    'cnblogs.com', 'complainthub.org', 'complaintsboard.com', 'consumeraffairs.com',
    'coursehero.com', 'csdn.net', 'dearcustomercare.com', 'einnews.com', 'einpresswire.com',
    'facebook.com', 'fastercapital.com', 'gethuman.com', 'glassdoor.com', 'instagram.com',
    'issuu.com', 'justuseapp.com', 'linkedin.com', 'londonprnews.com', 'moldstud.com',
    'onlineprnews.com', 'openpr.co.uk', 'openpr.com', 'oschina.net', 'pissedconsumer.com',
    'play.google.com', 'pr-inside.com', 'pressreleasepoint.com', 'prlog.org', 'prnews.io',
    'prnob.com', 'productreview.com.au', 'prwire.com', 'qiita.com', 'quora.com', 'reddit.com',
    'scribd.com', 'sitejabber.com', 'slideshare.net', 'studocu.com', 'suaramerdeka.com',
    'trustpilot.com', 'twitter.com', 'wikihow.com', 'wikipedia.org', 'yelp.com', 'youtube.com',
    'zhihu.com',
})

# Substrings that disqualify a URL. Grouped by what they indicate, because the group name is what
# a reader needs when wondering why a plausible-looking result was dropped. All are matched the
# same way -- against the full lower-cased URL and its path.
_URL_BLOCKLISTS: dict[str, frozenset[str]] = {
    "press-release wire": frozenset({
    'contact-number', 'customer-care-number', 'customer-service-phone-number', 'einnews',
    'einpresswire', 'helpline', 'helpline-number', 'hotline', 'news-release', 'newsrelease',
    'openpr', 'phone-directory', 'phone-number', 'pr-news', 'pr-wire', 'press-release',
    'pressrelease', 'prlog', 'prnews', 'prwire', 'returns-department', 'toll-free',
    'toll-free-helpline', 'tollfree',
    }),
    "help or complaints portal": frozenset({
    '-chinese', '-mandarin', '-spanish', '/complaints', '/contact', '/contact-us', '/faq',
    '/feedback', '/help', '/support', 'complaint-handling', 'faq', 'make-a-complaint',
    }),
    "forum or discussion thread": frozenset({
    '/answers', '/comment', '/community', '/discussion', '/forum', 'answers.', 'community.',
    'discussion.', 'discussions.', 'forum.', 'forums.',
    }),
    "legal or privacy page": frozenset({
    '/conditions', '/cookie', '/legal', '/privacy', '/terms', 'conditions-generales',
    'datenschutz', 'declaration-de-confidentialite', 'modal', 'policy',
    }),
    "asset vault or upload directory": frozenset({
    '/assets/pdf/', '/content/dam/', '/draft/', '/gated/', '/private/', '/secure/',
    '/wp-content/plugins/', '/wp-content/uploads/',
    }),
    "consumer transaction page": frozenset({
    '/accounts/', '/activate', '/apply', '/billing', '/booking/', '/boutique/', '/cards',
    '/chambres', '/checkout', '/compte', '/connexion', '/detail/', '/facture', '/forfaits/',
    '/listings/', '/loans/', '/login', '/mortgages/', '/my-account', '/offres/', '/plans/',
    '/refill', '/rentals/', '/reserver', '/rooms/', '/shop/', '/stay/', '/trips/',
    }),
    "partner or seller guide": frozenset({
    '/guide/', '/guides/', '/help-center', '/host/', '/hosting/', '/hosts/', '/merchant',
    '/partner', '/resources/hosting', '/resources/merchant', '/resources/seller', '/seller',
    '/support-center', '/vendor',
    }),
}

# Title phrasing that gives away a directory listing or complaints page rather than analysis.
_UNRELIABLE_TITLE_TERMS = frozenset({
    'complaints', 'contact number', 'customer care number', 'customer service number',
    'customer service phone number', 'faq', 'frequently asked questions', 'helpline',
    'hotline', 'is safe or legit', 'news release', 'phone number', 'pr wire', 'pr-wire',
    'press release', 'press-release', 'privacy policy', 'ratings & reviews',
    'telephone number', 'toll free', 'toll-free', 'tollfree',
})

# Stop words per language, with how many must appear before the title is treated as that
# language. Dutch needs three because several of its stop words are also English words.
_TITLE_LANGUAGE_STOPWORDS: dict[str, tuple[frozenset[str], int]] = {
    "German": (frozenset({
    'bei', 'das', 'dem', 'den', 'des', 'ein', 'eine', 'einem', 'einen', 'einer', 'eines',
    'ist', 'mit', 'nicht', 'oder', 'sind', 'und', 'von',
    }), 2),
    "Spanish": (frozenset({
    'como', 'con', 'del', 'las', 'los', 'para', 'pero', 'por', 'una',
    }), 2),
    "Italian": (frozenset({
    'come', 'con', 'dei', 'del', 'gli', 'ma', 'per', 'una',
    }), 2),
    "Portuguese": (frozenset({
    'com', 'como', 'esta', 'este', 'mais', 'para', 'pela', 'pelo', 'por', 'suporte', 'uma',
    }), 2),
    "Dutch": (frozenset({
    'dat', 'die', 'een', 'en', 'in', 'is', 'met', 'op', 'van', 'voor',
    }), 3),
}
# Single words strong enough on their own, where the stop-word count would miss the title.
_DECISIVE_GERMAN_WORDS = {"für"}
_DECISIVE_GERMAN_SUBSTRINGS = {"hervorragende", "auszeichnung"}
_DECISIVE_PORTUGUESE_WORDS = {"guia", "produto", "servico", "serviço", "atendimento", "cliente"}


def source_rejection_reason(url: str, title: str, summary: str | None = None) -> str | None:
    """Why this search result cannot be cited, or None if it can.

    Returns a reason rather than a bool so a discarded source can be logged and argued with. A
    benchmark that silently drops evidence is impossible to debug when it comes back thin.

    The order is cheapest-first: parsing and script checks before the substring sweeps.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()
        url_lower = url.lower()
    except Exception:
        return "unparseable URL"

    if _NON_LATIN_SCRIPTS.search(title) or _NON_LATIN_SCRIPTS.search(url):
        return "non-Latin script in title or URL"
    if summary and _NON_LATIN_SCRIPTS.search(summary):
        return "non-Latin script in summary"

    host_parts = host.split(".")
    if len(host_parts) >= 3:
        subdomain = host_parts[0]
        if len(subdomain) == 2 and subdomain not in _ALLOWED_SUBDOMAIN_LANGUAGES:
            return f"foreign-language subdomain ({subdomain})"

    for part in host_parts[:-2]:
        if part.lower() in _NON_PRODUCTION_SUBDOMAINS:
            return f"non-production subdomain ({part})"

    for blocked in _UNRELIABLE_HOSTS:
        if blocked in host or host.endswith(f".{blocked}"):
            return f"unreliable host ({blocked})"

    for reason, terms in _URL_BLOCKLISTS.items():
        for term in terms:
            if term in url_lower or term in path:
                return f"{reason} ({term})"

    if _FOREIGN_LANGUAGE_DIRECTORY.search(url_lower):
        return "foreign-language path segment"

    title_lower = normalize_text(title).lower()
    language = _title_language(title_lower)
    if language:
        return f"{language}-language title"

    for term in _UNRELIABLE_TITLE_TERMS:
        if term in title_lower:
            return f"title reads as a directory or complaints page ({term})"

    return None


def _title_language(title_lower: str) -> str | None:
    """The non-English/French language a title appears to be in, or None.

    Counting stop words rather than matching one: "des" and "in" appear in English too, so a
    single hit means nothing, while two German stop words in one title do not happen by accident.
    Dutch needs three because more of its stop words overlap with English.

    Languages are tested in a fixed order, and the order matters -- Spanish and Portuguese share
    vocabulary ("cliente", "para", "como"), so a Spanish title would otherwise be reported as
    Portuguese. The outcome is the same either way, but the reason given would be wrong.
    """
    words = _TITLE_WORDS.findall(title_lower)
    word_set = set(words)

    def stopword_hits(language: str) -> int:
        stopwords, _ = _TITLE_LANGUAGE_STOPWORDS[language]
        return sum(1 for w in words if w in stopwords)

    def meets(language: str) -> bool:
        _, threshold = _TITLE_LANGUAGE_STOPWORDS[language]
        return stopword_hits(language) >= threshold

    if (
        meets("German")
        or _DECISIVE_GERMAN_WORDS & word_set
        or any(fragment in title_lower for fragment in _DECISIVE_GERMAN_SUBSTRINGS)
    ):
        return "German"
    if meets("Spanish"):
        return "Spanish"
    if meets("Italian"):
        return "Italian"
    if meets("Portuguese") or _DECISIVE_PORTUGUESE_WORDS & word_set:
        return "Portuguese"
    if meets("Dutch"):
        return "Dutch"
    return None


class SemanticLeadersService:
    _langsearch_max_retries = 3
    _rerank_summary_char_limit = 3500

    def __init__(self, settings: Settings | None = None, llm_service: "LLMService | None" = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm_service
        self._metrics: dict[str, int] = {}
        self._last_rerank_debug: dict = {}

    async def build_leaders_snapshot(
        self,
        *,
        sector: str,
        respondent_company_name: str,
        pain_points: list[dict[str, str | None]],
        generation_mode: str = "initial",
        language: str = "fr",
    ) -> dict:
        return await self._build_snapshot(
            sector=sector,
            respondent_company_name=respondent_company_name,
            pain_points=pain_points,
            include_debug=False,
            generation_mode=generation_mode,
            language=language,
        )

    async def debug_leaders_snapshot(
        self,
        *,
        sector: str,
        respondent_company_name: str,
        pain_points: list[dict[str, str | None]],
        language: str = "fr",
    ) -> dict:
        return await self._build_snapshot(
            sector=sector,
            respondent_company_name=respondent_company_name,
            pain_points=pain_points,
            include_debug=True,
            generation_mode="debug",
            language=language,
        )

    async def _build_snapshot(
        self,
        *,
        sector: str,
        respondent_company_name: str,
        pain_points: list[dict[str, str | None]],
        include_debug: bool,
        generation_mode: str,
        language: str = "fr",
    ) -> dict:
        """Research the sector's leaders and assemble the report's benchmark section.

        Returns an "unsupported" snapshot rather than raising when the benchmark cannot run at
        all -- an unconfigured sector or a missing search key are both normal states, and the
        reason is shown to the reader.
        """
        sector_key = self._resolve_sector_key(sector)
        if sector_key is None:
            return self._unsupported_snapshot(
                f"Semantic leaders are not yet configured for sector '{sector}'.",
                sector=sector,
                respondent_company_name=respondent_company_name,
            )
        if not self.settings.langsearch_api_key:
            return self._unsupported_snapshot(
                "LANGSEARCH_API_KEY is not configured.",
                sector=sector,
                respondent_company_name=respondent_company_name,
            )

        # The respondent is never benchmarked against itself.
        normalized_respondent = normalize_text(respondent_company_name).lower()
        candidates = [
            candidate
            for candidate in SECTOR_LEADER_CANDIDATES.get(sector_key, ())
            if normalize_text(candidate.company_name).lower() != normalized_respondent
        ]
        candidates = await self._prioritize_candidates_via_ey(sector=sector, candidates=candidates)
        self._reset_metrics(candidates_considered=len(candidates))

        leaders, candidate_debug = await self._research_candidates(
            candidates=candidates,
            sector=sector,
            sector_key=sector_key,
            pain_points=pain_points,
            include_debug=include_debug,
            generation_mode=generation_mode,
        )
        # Best evidence first, then most evidence, then name so a re-run is reproducible.
        leaders.sort(
            key=lambda item: (
                -float(item.get("_semantic_score") or 0.0),
                -int(len(item.get("evidence_links") or [])),
                str(item.get("company_name") or ""),
            )
        )

        curated = await self._curate_shortlist(
            leaders, sector=sector, pain_points=pain_points, language=language
        )
        curated = self._select_final_leaders(curated, pain_points=pain_points)[:_MAX_LEADERS_IN_REPORT]
        self._metrics["capability_coverage_count"] = self._capability_coverage_count(curated)

        trimmed = [_public_leader(item) for item in curated]
        ey_card = await self._generate_ey_insights_leader(
            sector=sector,
            sector_label=_sector_label(sector_key, sector),
            language=language,
        )
        if ey_card:
            trimmed.append(ey_card)

        total_mistral_calls = self._metrics.get("mistral_calls", 0)
        logger.warning(
            "benchmark snapshot built sector=%s mode=%s candidates=%s leaders=%s mistral_calls=%s",
            sector_key,
            generation_mode,
            len(candidates),
            len(trimmed),
            total_mistral_calls,
        )
        payload = {
            "supported": True,
            "sector_key": sector_key,
            "sector": sector,
            "respondent_company_name": respondent_company_name,
            "pain_points": pain_points,
            "metrics": {**self._metrics, "mistral_calls": total_mistral_calls},
            "leaders": trimmed,
        }
        if include_debug:
            payload["candidate_debug"] = candidate_debug
        return payload

    @staticmethod
    def _unsupported_snapshot(reason: str, *, sector: str, respondent_company_name: str) -> dict:
        """A snapshot saying the benchmark could not run, and why."""
        return {
            "supported": False,
            "reason": reason,
            "sector": sector,
            "respondent_company_name": respondent_company_name,
            "leaders": [],
        }

    def _reset_metrics(self, *, candidates_considered: int) -> None:
        """Start a fresh count for one snapshot. Reported alongside the result."""
        self._metrics = {
            "candidates_considered": candidates_considered,
            "candidates_evaluated": 0,
            "web_search_calls": 0,
            "rerank_calls": 0,
            "mistral_calls": 0,
            "documents_retrieved": 0,
            "documents_validated": 0,
            "documents_rejected_indirect": 0,
            "capability_coverage_count": 0,
        }

    async def _research_candidates(
        self,
        *,
        candidates: list[LeaderCandidate],
        sector: str,
        sector_key: str,
        pain_points: list[dict[str, str | None]],
        include_debug: bool,
        generation_mode: str,
    ) -> tuple[list[dict], list[dict]]:
        """Research every candidate, returning those with evidence and a note on each that failed.

        A candidate producing nothing is ordinary -- the sector shortlist is fixed, and not every
        company on it has published anything about the weakness being benchmarked.
        """
        leaders: list[dict] = []
        candidate_debug: list[dict] = []

        for candidate in candidates:
            self._metrics["candidates_evaluated"] += 1
            leader = await self._evaluate_candidate(
                candidate=candidate,
                sector=sector,
                sector_key=sector_key,
                pain_points=pain_points,
                include_debug=include_debug,
                generation_mode=generation_mode,
            )
            if not leader:
                if include_debug:
                    candidate_debug.append(
                        {
                            "company_name": candidate.company_name,
                            "selected_count": 0,
                            "reason": "candidate_returned_none",
                        }
                    )
                continue
            if include_debug and isinstance(leader.get("_debug"), dict):
                candidate_debug.append(leader["_debug"])
            if leader.get("company_name"):
                leaders.append(leader)

        return leaders, candidate_debug

    async def _curate_shortlist(
        self,
        leaders: list[dict],
        *,
        sector: str,
        pain_points: list[dict[str, str | None]],
        language: str,
    ) -> list[dict]:
        """Rewrite the top leaders' evidence, spending the assessment's model budget on the best.

        The budget is per assessment and small, so it goes to the highest-ranked leaders in order.
        Everything past it is still curated, just deterministically -- a leader below the budget
        keeps its place in the report rather than being dropped for being cheap to produce.
        """
        model_budget = max(0, int(self.settings.benchmark_max_mistral_calls_per_assessment))
        shortlist_size = min(len(leaders), max(_MIN_SHORTLIST, model_budget))

        curated: list[dict] = []
        for index, item in enumerate(leaders[:shortlist_size]):
            result = await self._curate_ranked_candidate(
                item=item,
                sector=sector,
                pain_points=pain_points,
                allow_llm=index < model_budget,
                language=language,
            )
            if result:
                curated.append(result)
        return curated

    @staticmethod
    def _capability_coverage_count(leaders: list[dict]) -> int:
        """How many distinct capabilities the shown evidence speaks to.

        The headline quality signal for a snapshot: three links about the same capability are
        weaker than three about three, however good each one is.
        """
        return len(
            {
                capability.lower()
                for leader in leaders
                for link in (leader.get("evidence_links") or [])
                if (capability := normalize_text(str(link.get("mapped_capability") or "")).strip())
            }
        )


    async def _generate_ey_insights_leader(
        self,
        *,
        sector: str,
        sector_label: str,
        language: str = "fr",
    ) -> dict | None:
        """Build the EY Industry Insights card shown alongside the real sector leaders.

        Not a competitor card: a fixed one pairing EY's own decks with whatever EY has recently
        published on this sector. The decks always ship, so the web search only fills the link
        slots they leave over.
        """
        is_french = (language or "").lower().startswith("fr")
        sector_key = self._resolve_sector_key(sector) or ""

        # The master deck always ships; a sector deck joins it when one exists.
        presentations = [_deck_card(_EY_MASTER_DECK, is_french)]
        sector_deck = _EY_SECTOR_DECKS.get(_EY_DECK_BY_SECTOR.get(sector_key, ""))
        if sector_deck:
            presentations.append(_deck_card(sector_deck, is_french))

        results = await self._search_ey_publications(
            sector_label=sector_label, slots=_EY_CARD_LINK_SLOTS - len(presentations)
        )
        curated = await self._curate_ey_links(
            results, sector=sector, target_lang="French" if is_french else "English"
        )

        leader_summary = str(curated.get("leader_summary") or "").strip()
        if not leader_summary:
            leader_summary = (
                f"EY propose des analyses stratégiques et des retours d'expérience pour le secteur {sector}."
                if is_french
                else f"EY provides strategic analysis and experience insights for the {sector} sector."
            )

        curated_by_url = {
            str(link.get("url") or "").strip(): link
            for link in (curated.get("links") or [])
            if isinstance(link, dict) and link.get("url")
        }
        evidence_links = list(presentations)
        for item in results:
            url = str(item.get("url") or "").strip()
            evidence_links.append(self._ey_evidence_link(item, curated_by_url.get(url)))

        return {
            "key": "ey-insights",
            "company_name": "Perspectives EY" if is_french else "EY Insights",
            "logo_url": "https://www.ey.com/favicon.ico",
            "leader_summary": _truncate(leader_summary, _MAX_LEADER_SUMMARY_CHARS),
            "evidence_links": evidence_links,
        }

    async def _search_ey_publications(self, *, sector_label: str, slots: int) -> list[dict]:
        """EY's own publications on this sector, at most `slots` of them.

        A failure here is not fatal: the card still has its decks, so an empty result just means
        it ships with fewer links.
        """
        if slots <= 0:
            return []
        results = []
        query = f'site:ey.com/en "{sector_label}" (customer OR client OR experience OR transformation OR strategy) english'
        logger.warning("Generating decoupled EY Insights card query=%r", query)
        try:
            results = await self._web_search(query)
        except Exception as exc:
            logger.warning("EY Insights web search failed: %s", exc)
        return (results or [])[:slots]

    async def _curate_ey_links(
        self, target_results: list[dict], *, sector: str, target_lang: str
    ) -> dict:
        """Ask the model for a card summary and a cleaned label per link.

        Purely an improvement pass. Everything it produces has a deterministic fallback at the
        call site, so a model failure costs the card some polish rather than breaking it.
        """
        if not target_results or not self.llm:
            return {}

        parsed: dict = {}
        raw_candidates = []
        for idx, item in enumerate(target_results, 1):
            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            url = str(item.get("url") or "").strip()
            raw_candidates.append(
                f"{idx}. Title: {title}\n"
                f"   Summary: {summary}\n"
                f"   URL: {url}"
            )
        evidence_lines = "\n".join(raw_candidates)

        summary_prompt = (
            f"Review these general EY publication/case study results for the {sector} sector:\n\n"
            f"{evidence_lines}\n\n"
            f"Generate a professional curated package for the EY Insights card. "
            f"Return strict JSON with this shape:\n"
            f'{{"leader_summary": "one fluid sentence under 140 characters", "links": [{{"url": "...", "label": "...", "why_relevant": "..."}}]}}\n\n'
            f"Rules:\n"
            f"- Write all text values ('leader_summary', 'label', 'why_relevant') entirely in {target_lang}.\n"
            f"- For 'leader_summary': write a one-sentence summary of the main customer experience recommendations/approaches from EY for this sector. Keep it natural, professional, and strictly under 140 characters.\n"
            f"- For each link's 'label': clean the title to be a concise, professional description of the case study/report (strictly under 80 characters). Do NOT include corporate suffixes like '| EY - Global', '| EY - US', '| EY', or branding boilerplates.\n"
            f"- For each link's 'why_relevant': write a specific, single-sentence explanation of what the article demonstrates. Do NOT include search boilerplate tagline texts (like 'the better the question the better the answer', 'building a better working world').\n"
            f"- Match each input URL exactly."
        )

        try:
            system_content = f"You are a precise business analyst. Respond entirely in {target_lang}. Output JSON only."
            response = await self.llm.gateway.chat_messages(
                [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": summary_prompt},
                ],
                rate_budget_scope="benchmark",
            )
            self._metrics["mistral_calls"] = self._metrics.get("mistral_calls", 0) + 1
            parsed = self._parse_json_object(response)
        except Exception as e:
            logger.warning("Failed to generate LLM curation for EY Insights card: %s", e)
        return parsed if isinstance(parsed, dict) else {}

    def _ey_evidence_link(self, item: dict, curated: dict | None) -> dict:
        """One search result as a card link, preferring the model's wording over the raw result.

        The fallbacks carry more weight than they look like they do: EY titles arrive with a
        country suffix and EY summaries usually open with a marketing tagline, so an uncurated
        link would otherwise read "... | EY - Global" above a sentence about building a better
        working world.
        """
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        summary = str(item.get("summary") or "").strip()
        cleaned_title = self._clean_source_title(raw_title=title, url=url)

        label = str((curated or {}).get("label") or "").strip()
        if not label:
            label = cleaned_title or title
            for suffix in _EY_TITLE_SUFFIXES:
                if label.endswith(suffix):
                    label = label[: -len(suffix)].strip()
            label = _truncate(label, _MAX_LINK_LABEL_CHARS)

        why_relevant = str((curated or {}).get("why_relevant") or "").strip()
        if not why_relevant:
            why_relevant = summary
            for phrase in _EY_TAGLINE_PHRASES:
                why_relevant = re.sub(phrase, "", why_relevant, flags=re.IGNORECASE)
            why_relevant = _truncate(why_relevant.strip(), _MAX_WHY_RELEVANT_CHARS)

        return {
            "label": label,
            "url": url,
            "source_title": cleaned_title or "EY",
            "mapped_capability": "Industry Benchmark",
            "why_relevant": why_relevant,
        }

    async def _prioritize_candidates_via_ey(
        self,
        *,
        sector: str,
        candidates: list[LeaderCandidate],
    ) -> list[LeaderCandidate]:
        """
        Queries site:ey.com to see which of our pre-configured candidates are mentioned
        in connection with customer experience/transformation in that sector.
        Returns the candidates reordered with those mentioned at the top.
        """
        query = f'site:ey.com/en ("customer experience" OR "transformation") AND "{sector}" english'
        logger.warning("Querying EY for candidate prioritization query=%r", query)
        
        try:
            ey_results = await self._web_search(query)
        except Exception as exc:
            logger.warning("EY candidate prioritization search failed: %s", exc)
            return candidates

        # Extract all text from results (title + summary)
        combined_text = ""
        for item in ey_results:
            title = str(item.get("title") or "").lower()
            summary = str(item.get("summary") or "").lower()
            combined_text += f" {title} {summary}"

        # Match candidate names (case-insensitive)
        mentioned_keys = set()
        for candidate in candidates:
            name_lower = candidate.company_name.lower()
            if name_lower in combined_text:
                mentioned_keys.add(candidate.key)
                logger.warning("EY Prioritization Match: candidate %s is mentioned in EY articles", candidate.company_name)

        # Reorder candidates: mentioned ones first, then others
        prioritized = [c for c in candidates if c.key in mentioned_keys]
        fallback = [c for c in candidates if c.key not in mentioned_keys]
        
        return prioritized + fallback

    async def _evaluate_candidate(
        self,
        *,
        candidate: LeaderCandidate,
        sector: str,
        sector_key: str,
        pain_points: list[dict[str, str | None]],
        include_debug: bool = False,
        generation_mode: str = "initial",
    ) -> dict | None:
        """Research one candidate leader and score how well the evidence found supports it.

        Search, rerank against the pain point, select the documents that genuinely evidence this
        company, then score. Returns None when nothing usable was found -- or, in debug mode, a
        payload carrying only the reason, so the debug endpoints can show why a candidate produced
        nothing.
        """
        search_queries = self._build_search_queries(
            company_name=candidate.company_name,
            domain=candidate.domain,
            search_context=candidate.search_context,
            sector=sector,
            sector_key=sector_key,
            pain_points=pain_points,
        )
        retrieved_documents = await self._web_search_candidates(
            search_queries,
            allow_fallback_query=generation_mode != "initial",
            max_docs=self.settings.benchmark_max_langsearch_docs_per_candidate,
        )
        if not retrieved_documents:
            if include_debug:
                return {"_debug": self._candidate_debug(candidate, reason="no_search_results")}
            return None

        rerank_query = self._build_rerank_query(
            company_name=candidate.company_name,
            search_context=candidate.search_context,
            sector=sector,
            sector_key=sector_key,
            pain_points=pain_points,
        )
        rerank_top_n = min(
            _RERANK_TOP_N_INITIAL if generation_mode == "initial" else _RERANK_TOP_N_REGENERATE,
            len(retrieved_documents),
        )
        reranked = await self._semantic_rerank(
            query=rerank_query,
            documents=[self._document_text_for_rerank(item) for item in retrieved_documents],
            top_n=rerank_top_n,
        )
        # The reranker is a network call that is allowed to fail; ordering by the search engine's
        # own ranking is worse but keeps the candidate in the running.
        used_fallback_rerank = not reranked
        if used_fallback_rerank:
            reranked = self._fallback_rerank_results(documents=retrieved_documents, top_n=rerank_top_n)

        found = self._select_candidate_evidence(
            reranked=reranked,
            retrieved_documents=retrieved_documents,
            company_name=candidate.company_name,
        )
        self._metrics["documents_retrieved"] = self._metrics.get("documents_retrieved", 0) + len(retrieved_documents)

        if not found.evidence:
            if include_debug:
                return {
                    "_debug": self._candidate_debug(
                        candidate,
                        reason="no_evidence_after_selection",
                        retrieved_documents=retrieved_documents,
                        reranked=reranked,
                        found=found,
                    )
                }
            return None

        score = found.score()
        payload = {
            "key": candidate.key,
            "company_name": candidate.company_name,
            "logo_url": f"https://logo.clearbit.com/{candidate.domain}",
            "search_query": search_queries[0],
            "search_queries": search_queries,
            "rerank_query": rerank_query,
            "_search_context": candidate.search_context,
            "_sector_key": sector_key,
            "leader_summary": self._fallback_leader_summary(
                company_name=candidate.company_name, links=found.evidence
            ),
            "evidence_links": found.evidence[:_EVIDENCE_LINKS_PER_LEADER],
            "_raw_links": found.evidence,
            "_semantic_score": score.total,
            "_pre_curation_score": score.total,
            "_mistral_calls": 0,
        }
        if include_debug:
            payload["_debug"] = self._candidate_debug(
                candidate,
                reason="retrieved_with_fallback_rank" if used_fallback_rerank else "retrieved_and_ranked",
                retrieved_documents=retrieved_documents,
                reranked=reranked,
                found=found,
                score=score,
            )
        return payload

    def _select_candidate_evidence(
        self,
        *,
        reranked: list[dict],
        retrieved_documents: list[dict],
        company_name: str,
    ) -> "_CandidateEvidence":
        """Turn ranked search hits into the evidence links that will back this leader.

        Four things disqualify a hit, in order of how cheap they are to check: an index the
        reranker returned that does not address a real document, a URL already used, a page that
        never actually names the company, and a near-duplicate of something already taken.
        """
        evidence: list[dict[str, str | None]] = []
        cumulative_relevance_score = 0.0
        unique_urls: set[str] = set()
        unique_domains: set[str] = set()
        semantic_dedup_cache: list[dict] = []
        semantic_dedup_skips = 0

        for result in reranked:
            index = int(result.get("index", -1))
            if index < 0 or index >= len(retrieved_documents):
                continue
            document = retrieved_documents[index]
            url = str(document.get("url") or "").strip()
            if not url or url in unique_urls:
                continue
            if not _document_names_company(document, url=url, company_name=company_name):
                continue
            if self._is_duplicate_document(semantic_dedup_cache, document):
                semantic_dedup_skips += 1
                continue

            unique_urls.add(url)
            domain = self._url_domain(url)
            if domain:
                unique_domains.add(domain)
            semantic_dedup_cache.append(document)

            relevance_score = float(result.get("relevance_score") or 0.0)
            cumulative_relevance_score += relevance_score
            evidence.append(
                {
                    "title": document.get("title"),
                    "summary": document.get("summary"),
                    "url": url,
                    "source_title": self._clean_source_title(
                        raw_title=str(document.get("title") or ""), url=url
                    ),
                    "rerank_relevance_score": relevance_score,
                }
            )
            if len(evidence) >= _MAX_EVIDENCE_PER_CANDIDATE:
                break

        return _CandidateEvidence(
            evidence=evidence,
            unique_domains=unique_domains,
            dedup_skips=semantic_dedup_skips,
            cumulative_relevance_score=cumulative_relevance_score,
        )

    def _candidate_debug(
        self,
        candidate: LeaderCandidate,
        *,
        reason: str,
        retrieved_documents: list[dict] | None = None,
        reranked: list[dict] | None = None,
        found: "_CandidateEvidence | None" = None,
        score: "_CandidateScore | None" = None,
    ) -> dict:
        """Why this candidate produced what it did, for the benchmark debug endpoints."""
        debug = {
            "company_name": candidate.company_name,
            "retrieved_count": len(retrieved_documents or []),
            "reranked_count": len(reranked or []),
            "semantic_dedup_skips": found.dedup_skips if found else 0,
            "selected_count": len(found.evidence) if found else 0,
            "reason": reason,
        }
        if score is not None:
            debug.update(
                {
                    "average_relevance_score": score.average_relevance,
                    "diversity_bonus": score.diversity_bonus,
                    "semantic_dedup_penalty": score.dedup_penalty,
                    "semantic_score": score.total,
                    "pre_curation_score": score.total,
                    "mistral_calls": 0,
                    # Only on the success path, matching what the debug endpoints already expect.
                    "rerank_debug": self._last_rerank_debug,
                }
            )
        return debug


    def _build_search_queries(
        self,
        *,
        company_name: str,
        domain: str | None = None,
        search_context: str,
        sector: str,
        sector_key: str,
        pain_points: list[dict[str, str | None]],
    ) -> list[str]:
        pain_summary = self._pain_point_summary(pain_points)
        search_focus = self._pain_point_retrieval_focus(pain_points, sector_key=sector_key)
        context = search_context.strip()
        context_clause = f" {company_name} is a {context}." if context else ""

        # Determine the CX sector terminology and sector label
        sector_lower = (sector_key or "").lower()
        if "health" in sector_lower:
            cx_term = '"patient experience" OR "patient care"'
            sector_label = "healthcare"
        elif "hospitality" in sector_lower or "travel" in sector_lower:
            cx_term = '"guest experience" OR "customer care"'
            sector_label = "hospitality"
        elif "telecom" in sector_lower:
            cx_term = '"customer experience" OR "customer care"'
            sector_label = "telecommunications"
        else:
            cx_term = '"customer experience" OR "customer care"'
            sector_label = sector

        queries: list[str] = []

        # 1. Priority 1: Forrester, Gartner, Qualtrics, Ipsos, NielsenIQ, and VoC sources
        queries.append(
            f'"{company_name}" (site:forrester.com OR site:gartner.com OR site:qualtrics.com OR site:ipsos.com OR '
            f'site:nielseniq.com OR site:nielsen.com OR site:medallia.com OR site:verint.com) '
            f'({cx_term} OR "customer feedback" OR "feedback loops" OR "customer service strategy" OR '
            f'"continuous improvement" OR "satisfaction metrics" OR "Voice of the Customer" OR "VoC")'
        )

        # 2. Priority 2: Main website of the competitor
        if domain:
            queries.append(
                f'site:{domain} ({cx_term} OR "customer feedback" OR "feedback loops" OR '
                f'"customer service strategy" OR "continuous improvement" OR "satisfaction metrics") english'
            )

        # 3. Fallback search (general web search)
        queries.append(
            f"Find public examples, case studies, or reports showing how {company_name} improves customer experience in {sector} "
            f"through {pain_summary}. Focus on concrete operating practices, customer feedback handling, issue resolution, "
            f"decision routines, or measurable service improvements.{context_clause} english"
        )

        return queries

    def _build_rerank_query(
        self,
        *,
        company_name: str,
        search_context: str,
        sector: str,
        sector_key: str,
        pain_points: list[dict[str, str | None]],
    ) -> str:
        pain_details = self._pain_point_details_formatted(pain_points)
        context_clause = f"\nCompany context: {search_context}" if search_context.strip() else ""
        return (
            f"Rank these documents by how well they show concrete evidence of what {company_name} is doing "
            f"in {self._normalized_sector_label(sector_key, sector)} to address these specific customer experience gaps.\n\n"
            f"Evaluate the documents as benchmark evidence, not as general company coverage. "
            f"Prioritize documents that show how {company_name} operates, measures, governs, or improves the capability in practice.\n\n"
            f"Use the pain-point details below as a benchmark rubric:\n"
            f"- 'What this capability means' explains the business capability being assessed\n"
            f"- 'Current practice signals to look for' lists structured practices that directly relate to the capability\n"
            f"- 'Current gap' describes what weak maturity looks like for the respondent\n"
            f"- 'Best-practice signals to reward' describes what mature benchmark behavior looks like\n\n"
            f"{pain_details}{context_clause}\n\n"
            f"When ranking, strongly prefer documents that connect one or more of the current practice or best-practice signals "
            f"to concrete operating evidence such as named workflows, ownership models, review routines, listening systems, "
            f"decision processes, improvement backlogs, or measurable outcomes.\n\n"
            f"Prefer evidence of:\n"
            f"- Operating models and team structures\n"
            f"- Formal processes, systems, or tools\n"
            f"- Measurable outcomes or capability improvements\n"
            f"- Governance or accountability structures\n"
            f"- Structured feedback, action loops, or customer-informed decisions\n"
            f"- Best-practice signals such as ownership, review cadence, root-cause work, listening systems, action tracking, and measurable service improvement\n\n"
            f"Source authority guidance:\n"
            f"- Strongly reward official company case studies, annual reports with concrete operating detail, implementation writeups, and credible third-party case studies or analyst-style coverage\n"
            f"- Moderately reward trade publications, executive interviews, and substantive industry reporting when they describe concrete customer experience practices\n"
            f"- Deprioritize generic blog posts, broad overview pages, low-substance marketing pages, academic upload portals, and pages that lack verifiable operating detail\n\n"
            f"Avoid generic claims like enhancing experience or transforming service without concrete details.\n"
            f"Demote broad report pages, infrastructure-only stories, high-level strategy pages, and generic customer-experience narratives unless they clearly describe customer experience operating practices.\n"
            f"Reward documents that clearly show how {company_name} is closing the gap between weak maturity and mature practice for one or more of these pain points."
        )

    async def _web_search_candidates(
        self,
        queries: list[str],
        *,
        allow_fallback_query: bool,
        max_docs: int,
    ) -> list[dict]:
        merged: list[dict] = []
        seen_urls: set[str] = set()
        for index, query in enumerate(queries):
            for item in await self._web_search(query):
                url = str(item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                merged.append(item)
                if len(merged) >= max_docs:
                    return merged
            if index == 0 and not allow_fallback_query and len(merged) >= min(3, max_docs):
                return merged
        return merged

    def _is_credible_source(self, url: str, title: str, summary: str | None = None) -> bool:
        """Whether a search result is worth citing in a benchmark."""
        return source_rejection_reason(url, title, summary) is None

    async def _web_search(self, query: str) -> list[dict]:
        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/web-search"
        payload = {
            "query": query,
            "summary": True,
            "count": 10,
        }
        self._metrics["web_search_calls"] = self._metrics.get("web_search_calls", 0) + 1
        try:
            data = await self._post_langsearch(endpoint=endpoint, payload=payload)
        except Exception as exc:
            logger.warning("Telecom semantic web search failed for query=%r: %s", query, exc)
            return []

        values = ((((data or {}).get("data") or {}).get("webPages") or {}).get("value")) or []
        items: list[dict] = []
        for value in values:
            title = normalize_text(str(value.get("name") or "")).strip()
            url = str(value.get("url") or "").strip()
            summary = normalize_text(str(value.get("summary") or value.get("snippet") or "")).strip()
            site_name = normalize_text(str(value.get("siteName") or "")).strip() or None
            if not title or not url:
                continue
            if not self._is_credible_source(url, title, summary):
                continue
            items.append(
                {
                    "title": title,
                    "url": url,
                    "summary": summary or None,
                    "site_name": site_name,
                }
            )
        return items

    async def _semantic_rerank(self, *, query: str, documents: list[str], top_n: int) -> list[dict]:
        """Rank search results by how well they answer the pain point, not by keyword overlap.

        A failure here is never fatal: the caller falls back to a deterministic ordering, so every
        exit records why it gave up in `_last_rerank_debug` and returns an empty list. That record
        is the only way to diagnose a rerank from the debug endpoints, which is why it is written
        at every exit rather than only on success.
        """
        if not documents:
            self._last_rerank_debug = {"status": "skipped", "reason": "no_documents"}
            return []

        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/rerank"
        requested_top_n = min(top_n, len(documents))
        self._last_rerank_debug = {
            "status": "started",
            "endpoint": endpoint,
            "document_count": len(documents),
            "requested_top_n": requested_top_n,
            "query_chars": len(query),
            "total_document_chars": sum(len(document or "") for document in documents),
            "max_document_chars": max((len(document or "") for document in documents), default=0),
        }
        self._metrics["rerank_calls"] = self._metrics.get("rerank_calls", 0) + 1

        try:
            data = await self._post_langsearch(
                endpoint=endpoint,
                payload={
                    "model": "langsearch-reranker-v1",
                    "query": query,
                    "documents": documents,
                    "top_n": requested_top_n,
                    "return_documents": False,
                },
            )
        except httpx.HTTPStatusError as exc:
            response = exc.response
            self._note_rerank(
                status="http_error",
                http_status=response.status_code if response is not None else None,
                response_body_preview=self._safe_response_preview(response.text if response is not None else ""),
            )
            logger.warning(
                "Telecom semantic rerank HTTP error status=%s body=%s query=%r",
                self._last_rerank_debug.get("http_status"),
                self._last_rerank_debug.get("response_body_preview"),
                query,
            )
            return []
        except Exception as exc:
            self._note_rerank(
                status="exception",
                exception_type=type(exc).__name__,
                exception_message=str(exc)[:500],
            )
            logger.warning("Telecom semantic rerank failed for query=%r: %s", query, exc)
            return []

        results = self._rerank_results_from(data)
        self._note_rerank(
            status="completed" if results else "empty_results",
            top_level_keys=sorted((data or {}).keys()),
            data_type=type((data or {}).get("data")).__name__ if isinstance(data, dict) else type(data).__name__,
            results_count=len(results),
        )
        if not results:
            logger.warning(
                "Telecom semantic rerank returned no results keys=%s data_type=%s document_count=%s",
                self._last_rerank_debug.get("top_level_keys"),
                self._last_rerank_debug.get("data_type"),
                len(documents),
            )
        return results

    def _note_rerank(self, **fields: object) -> None:
        """Add to the running record of the current rerank, keeping what is already there."""
        self._last_rerank_debug = {**self._last_rerank_debug, **fields}

    @staticmethod
    def _rerank_results_from(data: object) -> list[dict]:
        """Dig the ranked results out of whichever shape the provider replied in.

        Three shapes have been seen in practice -- results at the top level, nested under `data`,
        or `data` being the list itself -- so all three are accepted rather than pinning one and
        having the rerank silently return nothing when the provider changes its envelope.
        """
        if not isinstance(data, dict):
            return []
        results = data.get("results")
        if results is None:
            inner = data.get("data")
            results = inner.get("results") if isinstance(inner, dict) else inner if isinstance(inner, list) else None
        return list(results or [])


    def _safe_response_preview(self, text: str, limit: int = 500) -> str:
        compact = " ".join((text or "").split())
        return compact[:limit]

    def _fallback_rerank_results(self, *, documents: list[dict], top_n: int) -> list[dict[str, float | int]]:
        ranked_count = min(max(int(top_n or 0), 0), len(documents))
        return [
            {
                "index": index,
                "relevance_score": max(0.35, 0.72 - (index * 0.04)),
            }
            for index in range(ranked_count)
        ]

    async def _post_langsearch(self, *, endpoint: str, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.settings.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        from app.services.assessment.reporting.provider_rate_limits import (
            BenchmarkProviderUnavailable,
            get_langsearch_limiter,
        )

        limiter = get_langsearch_limiter(self.settings)

        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(self._langsearch_max_retries):
                try:
                    usage = await limiter.acquire()
                except BenchmarkProviderUnavailable as exc:
                    logger.warning(
                        "provider call skipped due to app-level quota provider=langsearch endpoint=%s reason=%s",
                        endpoint,
                        exc,
                    )
                    raise
                logger.warning(
                    "benchmark langsearch request endpoint=%s per_second=%s per_minute=%s per_day=%s",
                    endpoint,
                    usage.per_second_count,
                    usage.per_minute_count,
                    usage.per_day_count,
                )
                response = await client.post(endpoint, headers=headers, json=payload)
                if response.status_code != 429:
                    response.raise_for_status()
                    return response.json()

                await limiter.note_rate_limited()
                retry_after_header = response.headers.get("Retry-After")
                retry_after_seconds = self._parse_retry_after_seconds(retry_after_header)
                if retry_after_seconds is None:
                    retry_after_seconds = min(10.0, 2.0 * (attempt + 1))
                logger.warning(
                    "LangSearch rate limited request to %s; retrying in %.2fs (attempt %s/%s)",
                    endpoint,
                    retry_after_seconds,
                    attempt + 1,
                    self._langsearch_max_retries,
                )
                await asyncio.sleep(retry_after_seconds)

        raise httpx.HTTPStatusError(
            message="LangSearch request failed after retries due to rate limiting.",
            request=response.request,
            response=response,
        )

    def _parse_retry_after_seconds(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            seconds = float(value.strip())
        except (TypeError, ValueError):
            return None
        return seconds if seconds > 0 else None

    def _document_text(self, item: dict) -> str:
        parts = [
            f"Title: {normalize_text(str(item.get('title') or '')).strip()}",
            f"Source: {normalize_text(str(item.get('site_name') or '')).strip()}",
            f"Summary: {normalize_text(str(item.get('summary') or '')).strip()}",
            f"URL: {str(item.get('url') or '').strip()}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    def _document_text_for_rerank(self, item: dict) -> str:
        summary = normalize_text(str(item.get("summary") or "")).strip()
        if len(summary) > self._rerank_summary_char_limit:
            summary = summary[: self._rerank_summary_char_limit].rsplit(" ", 1)[0].strip() + "..."
        parts = [
            f"Title: {normalize_text(str(item.get('title') or '')).strip()}",
            f"Source: {normalize_text(str(item.get('site_name') or '')).strip()}",
            f"Summary: {summary}",
            f"URL: {str(item.get('url') or '').strip()}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    def _pain_point_summary(self, pain_points: list[dict[str, str | None]]) -> str:
        labels = [
            normalize_text(str(item.get("capability") or "")).strip()
            for item in pain_points[:3]
            if normalize_text(str(item.get("capability") or "")).strip()
        ]
        return ", ".join(labels) if labels else "customer feedback, service quality, and digital experience"

    def _pain_point_details(self, pain_points: list[dict[str, str | None]]) -> str:
        return self._pain_point_summary(pain_points)

    def _pain_point_retrieval_focus(
        self,
        pain_points: list[dict[str, str | None]],
        *,
        sector_key: str,
    ) -> str:
        parts: list[str] = []
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            phrase = self._capability_retrieval_phrase(item, sector_key=sector_key)
            if capability and phrase:
                parts.append(f"{capability}: {phrase}")
            elif capability:
                parts.append(capability)
        return ", ".join(parts) if parts else self._pain_point_summary(pain_points)

    def _capability_retrieval_phrase(self, item: dict[str, str | None], *, sector_key: str) -> str:
        capability = normalize_text(str(item.get("capability") or "")).strip().lower()
        capability_retrieval_phrases = get_capability_retrieval_phrases(sector_key)
        if capability in capability_retrieval_phrases:
            return capability_retrieval_phrases[capability]

        description = self._clean_evidence_text(str(item.get("capability_description") or ""))
        action_hints = self._clean_action_hints(str(item.get("action_hints") or ""))
        parts = [part for part in [description, action_hints] if part]
        return "; ".join(parts)

    def _pain_point_details_formatted(self, pain_points: list[dict[str, str | None]]) -> str:
        details: list[str] = []
        for idx, item in enumerate(pain_points[:3], 1):
            capability = normalize_text(str(item.get("capability") or "")).strip()
            if not capability:
                continue
            capability_description = self._clean_evidence_text(str(item.get("capability_description") or ""))
            action_hints = self._clean_action_hints(str(item.get("action_hints") or ""))
            current_gap = self._sanitized_pain_point_detail(item)
            level3_action_hints = self._clean_action_hints(str(item.get("level3_action_hints") or ""))

            parts = [f"{idx}. {capability}:"]
            if capability_description:
                parts.append(f"   What this capability means: {capability_description}")
            if action_hints:
                parts.append(f"   Current practice signals to look for: {action_hints}")
            if current_gap:
                parts.append(f"   Current gap: {current_gap}")
            if level3_action_hints:
                parts.append(f"   Best-practice signals to reward: {level3_action_hints}")
            details.append("\n".join(parts))
        return "\n".join(details) if details else "customer feedback, service quality, and digital experience"

    def _pain_point_rubric_details(self, pain_points: list[dict[str, str | None]]) -> str:
        details: list[str] = []
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            rubric_description = normalize_text(str(item.get("rubric_description") or "")).strip()
            if capability and rubric_description:
                details.append(f"{capability}: {rubric_description}")
            elif capability:
                details.append(capability)
        return "; ".join(details) if details else self._pain_point_summary(pain_points)

    def _sanitized_pain_point_detail(self, item: dict[str, str | None]) -> str:
        source = normalize_text(str(item.get("rubric_description") or item.get("rationale") or "")).strip()
        if not source:
            return ""
        source = re.sub(r"^Level\s+\d+\s*/\s*[^:]+:\s*", "", source, flags=re.IGNORECASE).strip()
        kept: list[str] = []
        for sentence in self._summary_sentences(source):
            lowered = sentence.lower()
            if lowered.startswith("the user may"):
                continue
            if "user wording" in lowered or "did not provide assessable business evidence" in lowered:
                continue
            kept.append(sentence)
        return self._clean_evidence_text(" ".join(kept).strip())

    def _summary_sentences(self, text: str) -> list[str]:
        normalized = normalize_text(text).replace("\n", " ").strip()
        if not normalized:
            return []
        return [part.strip(" -") for part in re.split(r"(?<=[\.\!\?])\s+", normalized) if part.strip(" -")]

    def _clean_evidence_text(self, text: str) -> str:
        value = normalize_text(text).replace("\n", " ").strip(" -")
        value = re.sub(r"^\s*transcript\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"^\[\s*music\s*\]\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"^\s*by\s+[a-z0-9 ,.'/-]+\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"\s+", " ", value).strip()
        return value[:280].strip(" -,:;")

    def _clean_action_hints(self, text: str) -> str:
        normalized = normalize_text(text).strip()
        if not normalized:
            return ""
        hints = [self._clean_evidence_text(part) for part in normalized.split(";")]
        cleaned = [hint for hint in hints if hint]
        return ", ".join(cleaned[:4])

    def _resolve_sector_key(self, sector: str | None) -> str | None:
        normalized = normalize_text(sector).lower().strip()
        if not normalized:
            return None
        normalized = normalized.replace("&", " and ")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
        sector_aliases = {
            "telecom": "telecom",
            "banking insurance": "banking_insurance",
            "banking and insurance": "banking_insurance",
            "retail ecommerce": "retail_ecommerce",
            "retail e commerce": "retail_ecommerce",
            "ecommerce": "ecommerce",
            "e commerce": "ecommerce",
            "retail": "retail",
            "banking": "banking",
            "insurance": "insurance",
            "healthcare": "healthcare",
            "hospitality travel": "hospitality_travel",
            "hospitality and travel": "hospitality_travel",
            "travel and hospitality": "travel",
            "travel hospitality": "travel",
            "technology": "technology",
            "saas software": "technology",
            "saas": "technology",
            "software": "technology",
            "public services": "public_services",
            "public sector": "public_sector",
            "public": "public_sector",
        }
        return sector_aliases.get(normalized)

    def _normalized_sector_label(self, sector_key: str, fallback: str) -> str:
        labels = {
            "telecom": "telecom",
            "banking_insurance": "banking and insurance",
            "retail_ecommerce": "retail and e-commerce",
            "ecommerce": "e-commerce",
            "retail": "retail",
            "banking": "banking",
            "insurance": "insurance",
            "healthcare": "healthcare",
            "hospitality_travel": "hospitality and travel",
            "travel": "travel",
            "technology": "technology",
            "public_services": "public services",
            "public_sector": "public sector",
        }
        return labels.get(sector_key, normalize_text(fallback).strip() or sector_key)


    def _url_domain(self, url: str) -> str | None:
        match = re.match(r"^https?://([^/]+)", url.strip(), flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).lower()

    def _clean_source_title(self, *, raw_title: str, url: str) -> str | None:
        title = self._clean_evidence_text(raw_title)
        title = re.sub(r"\s+\|\s+(?:pdf|home|official site|case study)$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s+-\s+(?:pdf|official site)$", "", title, flags=re.IGNORECASE).strip()
        if self._looks_like_bad_source_title(title):
            title = self._source_title_from_url(url)
        return title or None

    def _looks_like_bad_source_title(self, title: str) -> bool:
        if not title:
            return True
        lowered = title.lower()
        if len(title) < 14:
            return True
        if lowered.endswith(" repo") or lowered.endswith(" report repo"):
            return True
        if len(re.findall(r"[A-Za-z]{2,}", title)) < 3:
            return True
        return False

    def _source_title_from_url(self, url: str) -> str | None:
        path_match = re.match(r"^https?://[^/]+/(.+)$", url.strip(), flags=re.IGNORECASE)
        if not path_match:
            return None
        path = path_match.group(1).split("?", 1)[0].split("#", 1)[0].strip("/")
        if not path:
            return None
        slug = PurePosixPath(path).name
        slug = re.sub(r"\.(pdf|html?)$", "", slug, flags=re.IGNORECASE)
        slug = slug.replace("-", " ").replace("_", " ")
        slug = re.sub(r"\s+", " ", slug).strip()
        if not slug:
            return None
        return slug.title()

    async def _curate_ranked_candidate(
        self,
        *,
        item: dict,
        sector: str,
        pain_points: list[dict[str, str | None]],
        allow_llm: bool,
        language: str = "fr",
    ) -> dict | None:
        raw_links = list(item.get("_raw_links") or [])
        if not raw_links:
            return None

        curated = await self._curate_leader_package(
            company_name=str(item.get("company_name") or ""),
            sector=sector,
            pain_points=pain_points,
            raw_links=raw_links,
            allow_llm=allow_llm,
            language=language,
        )
        evidence_links = curated.get("links") or []
        if not evidence_links:
            return None

        payload = dict(item)
        payload["leader_summary"] = curated.get("leader_summary") or item.get("leader_summary")
        payload["evidence_links"] = evidence_links
        payload["_mistral_calls"] = int(curated.get("mistral_calls") or 0)
        payload["_curated_score"] = float(curated.get("curated_score") or item.get("_semantic_score") or 0.0)
        payload["_coverage_capabilities"] = list(curated.get("coverage_capabilities") or [])
        payload["_document_assessments"] = list(curated.get("document_assessments") or [])
        payload["_rejected_evidence"] = list(curated.get("rejected_evidence") or [])
        if isinstance(payload.get("_debug"), dict):
            payload["_debug"].update(
                {
                    "document_assessments": payload["_document_assessments"],
                    "rejected_evidence": payload["_rejected_evidence"],
                    "coverage_capabilities": payload["_coverage_capabilities"],
                    "curated_score": payload["_curated_score"],
                    "selected_count": len(evidence_links),
                    "mistral_calls": payload["_mistral_calls"],
                }
            )
        return payload

    async def _curate_leader_package(
        self,
        *,
        company_name: str,
        sector: str,
        pain_points: list[dict[str, str | None]],
        raw_links: list[dict[str, str | None]],
        allow_llm: bool,
        language: str = "fr",
    ) -> dict[str, object]:
        fallback_links = self._fallback_links(raw_links=raw_links, pain_points=pain_points, language=language)
        fallback_summary = self._fallback_leader_summary(company_name=company_name, links=fallback_links, language=language)
        if not raw_links:
            return {
                "leader_summary": fallback_summary,
                "links": [],
                "mistral_calls": 0,
                "curated_score": 0.0,
                "coverage_capabilities": [],
                "document_assessments": [],
                "rejected_evidence": [],
            }
        if self.llm is None or not allow_llm:
            if not allow_llm:
                logger.warning(
                    "provider call skipped due to app-level quota provider=mistral reason=max_calls_per_assessment company=%s",
                    company_name,
                )
            else:
                logger.warning(
                    "leader package curation skipped because llm_service is unavailable company=%s",
                    company_name,
                )
            return {
                "leader_summary": fallback_summary,
                "links": fallback_links,
                "mistral_calls": 0,
                "curated_score": self._fallback_curated_score(fallback_links),
                "coverage_capabilities": self._link_capability_coverage(fallback_links),
                "document_assessments": [],
                "rejected_evidence": [],
            }

        pain_details = self._pain_point_details_formatted(pain_points)
        evidence_lines = "\n".join(
            (
                f"{idx + 1}. Title: {self._clean_evidence_text(str(link.get('title') or link.get('source_title') or ''))}\n"
                f"   Summary: {self._clean_evidence_text(str(link.get('summary') or ''))}\n"
                f"   Source: {self._clean_evidence_text(str(link.get('source_title') or ''))}\n"
                f"   Best matching respondent pain point: {self._best_matching_capability(link=link, pain_points=pain_points) or 'unknown'}\n"
                f"   URL: {str(link.get('url') or '').strip()}"
            )
            for idx, link in enumerate(raw_links[:5])
        )
        strongest_gaps = ", ".join(
            capability
            for capability in [
                normalize_text(str(item.get("capability") or "")).strip()
                for item in pain_points[:2]
            ]
            if capability
        ) or "the respondent's weakest capabilities"
        prompt = (
            f"Review these benchmark evidence candidates for {company_name} in {sector}.\n\n"
            "Assess each document semantically against the respondent pain points before you decide what to keep.\n"
            "Select only evidence that directly demonstrates the capability through concrete operating proof, routines, "
            "tooling, ownership, or measured outcomes.\n"
            "Reject indirect-but-plausible evidence when the capability match is mostly inferential or when the source is "
            "strategic narrative without a clear CX mechanism.\n\n"
            f"Pain-point rubric:\n{pain_details}\n\n"
            "Before deciding what to keep, compare the documents against each other for source substance and benchmark "
            "trustworthiness. Prefer the evidence that provides clearer operating proof, stronger specificity, and more "
            "credible benchmark detail when two sources claim similar things.\n\n"
            "Return strict JSON with this shape:\n"
            '{"leader_summary":"one fluid sentence under 140 characters","document_assessments":[{"index":1,"matched_capability":"...","match_confidence":0.0,"match_reason":"...","evidence_type":"implementation case study","operating_specificity":0.0,"source_authority":0.0,"measurable_outcome_clarity":0.0,"indirectness_risk":0.0,"keep_recommendation":true,"why_relevant":"...","rewrite_label":"..."}]}\n'
            "Rules:\n"
            "- assess every document index provided\n"
            f"- leader_summary must mention the 1 to 2 strongest respondent gaps it addresses, especially among: {strongest_gaps}\n"
            "- leader_summary must be concise, fluid, and strictly under 140 characters\n"
            "- leader_summary must capture *how* tools or techniques are used in a natural sentence, rather than listing them (e.g. 'T-Mobile utilise son modèle de Team of Experts pour résoudre...', NOT 'Utilise Team of Experts, chat et téléphone')\n"
            "- Do NOT mention backend cloud architecture, AWS SageMaker, database servers, or machine learning infrastructure\n"
            "- matched_capability must match one of the respondent pain points when possible\n"
            "- match_confidence, operating_specificity, source_authority, measurable_outcome_clarity, and indirectness_risk must be numbers from 0 to 1\n"
            "- evidence_type must be one of: implementation case study, operational report, executive interview, annual/reporting disclosure, news/commentary, product/vendor case study, generic marketing / low-substance overview\n"
            "- keep_recommendation must be true only when the document directly supports the capability with concrete proof\n"
            "- source_authority should reflect benchmark trustworthiness and substance, not brand fame alone\n"
            "- when similar documents support the same claim, score the more substantive and benchmark-trustworthy one higher and reject the weaker one when appropriate\n"
            "- why_relevant must explain in one short sentence how the evidence addresses that respondent gap\n"
            "- rewrite_label must be a very light, short description strictly under 80 characters emphasizing only the concrete practice or outcome explicitly shown (e.g., 'Modèle Team of Experts pour le support client', NOT a long explanation)\n"
            "- do not invent facts, names, metrics, or governance details\n"
            "- do not upgrade a broad strategic narrative into an operating mechanism if the source does not clearly show that mechanism\n"
            "- prefer implementation case studies, concrete transformation programs, named tooling, measured outcomes, and formal operating routines when they are actually described\n\n"
            f"Evidence candidates:\n{evidence_lines}"
        )
        logger.warning(
            "leader package curation prompt metrics company=%s chars=%s pain_points=%s evidence_docs=%s",
            company_name,
            len(prompt),
            len(pain_points[:3]),
            min(len(raw_links), 5),
        )
        from app.services.assessment.reporting.provider_rate_limits import BenchmarkProviderUnavailable

        try:
            logger.warning(
                "leader package curation calling mistral company=%s documents=%s sector=%s",
                company_name,
                min(len(raw_links), 5),
                sector,
            )
            target_lang = "French" if (language or "").lower().startswith("fr") else "English"
            system_content = (
                f"You are a precise benchmark curator. Output JSON only.\n"
                f"All generated text values (like 'leader_summary', 'why_relevant', 'rewrite_label') MUST be written entirely in {target_lang}. Do NOT translate JSON keys, URLs, or company names.\n\n"
                f"CRITICAL guidelines for text summaries and labels:\n"
                f"1. Write in a fluid, natural, and user-friendly tone suitable for a professional business report. "
                f"DO NOT write dry, robotic, comma-separated lists of tools (e.g. do NOT write 'Utilise Virtual Artist, chatbots et bornes'). Instead, frame it as a meaningful sentence showing *how* they are used (e.g., 'Sephora associe son outil Virtual Artist et sa communauté Beauty Insider pour guider ses clients').\n"
                f"2. Focus strictly on customer-facing CX/support techniques (e.g., support models, digital platforms, chatbots, user forums). Do NOT mention backend cloud infrastructure, server hosting, machine learning frameworks, or data engineering tools (like AWS SageMaker, database servers).\n"
                f"3. Do NOT use generic boilerplate statements (like 'améliore la satisfaction', 'gère l\'expérience client', 'optimise la collecte de retours', or 'improves satisfaction', 'manages customer experience').\n"
                f"4. The 'leader_summary' MUST be under 140 characters."
            )
            content = await self.llm.gateway.chat_messages(
                [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {"role": "user", "content": prompt},
                ],
                rate_budget_scope="benchmark",
            )
            self._metrics["mistral_calls"] = self._metrics.get("mistral_calls", 0) + 1
            parsed = self._parse_json_object(content)
        except BenchmarkProviderUnavailable as exc:
            logger.warning("Leader package curation skipped for %s: %s", company_name, exc)
            return {"leader_summary": fallback_summary, "links": fallback_links, "mistral_calls": 0}
        except Exception as exc:
            logger.exception("Leader package curation failed for %s", company_name)
            return {"leader_summary": fallback_summary, "links": fallback_links, "mistral_calls": 0}

        raw_assessments = parsed.get("document_assessments") if isinstance(parsed, dict) else None
        scored_assessments = self._normalize_document_assessments(
            raw_assessments=raw_assessments if isinstance(raw_assessments, list) else [],
            raw_links=raw_links,
            pain_points=pain_points,
        )
        self._metrics["documents_validated"] = self._metrics.get("documents_validated", 0) + len(scored_assessments)
        self._metrics["documents_rejected_indirect"] = self._metrics.get("documents_rejected_indirect", 0) + sum(
            1 for assessment in scored_assessments if assessment.get("rejection_reason") == "indirectness_risk"
        )
        curated_links = self._select_curated_links(scored_assessments, language=language)
        rejected_evidence = [
            {
                "index": assessment.get("index"),
                "source_title": assessment.get("source_title"),
                "matched_capability": assessment.get("matched_capability"),
                "selection_score": assessment.get("selection_score"),
                "rejection_reason": assessment.get("rejection_reason"),
                "evidence_type": assessment.get("evidence_type"),
                "indirectness_risk": assessment.get("indirectness_risk"),
            }
            for assessment in scored_assessments
            if not assessment.get("selected")
        ]
        if not curated_links:
            curated_links = fallback_links

        leader_summary = self._trim_leader_summary(
            self._leader_summary_from_assessments(
                company_name=company_name,
                requested_summary=normalize_text(str((parsed or {}).get("leader_summary") or "")).strip(),
                selected_links=curated_links,
                language=language,
            )
            or fallback_summary
        )
        return {
            "leader_summary": leader_summary,
            "links": curated_links[:3],
            "mistral_calls": 1,
            "curated_score": self._curated_score(scored_assessments, curated_links),
            "coverage_capabilities": self._link_capability_coverage(curated_links),
            "document_assessments": scored_assessments,
            "rejected_evidence": rejected_evidence,
        }

    def _fallback_links(
        self,
        *,
        raw_links: list[dict[str, str | None]],
        pain_points: list[dict[str, str | None]],
        language: str = "fr",
    ) -> list[dict[str, str | None]]:
        links = []
        for link in raw_links:
            if not str(link.get("url") or "").strip():
                continue
            cap = self._best_matching_capability(link=link, pain_points=pain_points)
            if not cap:
                # Exclude links that do not align with any assessed customer experience capability
                continue
            links.append(
                {
                    "label": self._fallback_evidence_label(link, language=language),
                    "url": str(link.get("url") or ""),
                    "source_title": self._clean_source_title(
                        raw_title=str(link.get("source_title") or link.get("title") or ""),
                        url=str(link.get("url") or ""),
                    ),
                    "mapped_capability": cap,
                    "why_relevant": self._fallback_relevance_reason(link=link, pain_points=pain_points, language=language),
                }
            )
            if len(links) >= 3:
                break
        return links

    def _normalize_document_assessments(
        self,
        *,
        raw_assessments: list[dict],
        raw_links: list[dict[str, str | None]],
        pain_points: list[dict[str, str | None]],
    ) -> list[dict[str, object]]:
        assessments: list[dict[str, object]] = []
        seen_indices: set[int] = set()
        for raw_item in raw_assessments:
            if not isinstance(raw_item, dict):
                continue
            try:
                index = int(raw_item.get("index")) - 1
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(raw_links) or index in seen_indices:
                continue
            seen_indices.add(index)
            base_link = raw_links[index]
            matched_capability = self._resolve_mapped_capability(
                self._clean_evidence_text(str(raw_item.get("matched_capability") or "")),
                pain_points,
            ) or self._best_matching_capability(link=base_link, pain_points=pain_points)
            assessment = {
                "index": index + 1,
                "title": str(base_link.get("title") or ""),
                "summary": str(base_link.get("summary") or ""),
                "url": str(base_link.get("url") or ""),
                "source_title": self._clean_source_title(
                    raw_title=str(base_link.get("source_title") or base_link.get("title") or ""),
                    url=str(base_link.get("url") or ""),
                ),
                "matched_capability": matched_capability,
                "match_confidence": self._bounded_score(raw_item.get("match_confidence")),
                "match_reason": self._clean_evidence_text(str(raw_item.get("match_reason") or "")),
                "evidence_type": self._normalize_evidence_type(str(raw_item.get("evidence_type") or "")),
                "operating_specificity": self._bounded_score(raw_item.get("operating_specificity")),
                "source_authority": self._bounded_score(raw_item.get("source_authority")),
                "measurable_outcome_clarity": self._bounded_score(raw_item.get("measurable_outcome_clarity")),
                "indirectness_risk": self._bounded_score(raw_item.get("indirectness_risk")),
                "keep_recommendation": bool(raw_item.get("keep_recommendation")),
                "why_relevant": self._clean_evidence_text(str(raw_item.get("why_relevant") or "")),
                "rewrite_label": self._clean_evidence_text(str(raw_item.get("rewrite_label") or "")),
                "rerank_relevance_score": float(base_link.get("rerank_relevance_score") or 0.0),
            }
            assessment["selection_score"] = self._document_selection_score(assessment)
            assessment["rejection_reason"] = self._document_rejection_reason(assessment)
            assessment["soft_diversity_candidate"] = self._is_soft_diversity_candidate(assessment)
            assessments.append(assessment)
        self._apply_post_curation_filters(assessments)
        assessments.sort(key=lambda item: -float(item.get("selection_score") or 0.0))
        return assessments

    def _bounded_score(self, value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

    def _normalize_evidence_type(self, value: str) -> str:
        normalized = normalize_text(value).lower().strip()
        categories = (
            "implementation case study",
            "operational report",
            "executive interview",
            "annual/reporting disclosure",
            "news/commentary",
            "product/vendor case study",
            "generic marketing / low-substance overview",
        )
        for category in categories:
            if normalized == category or normalized in category:
                return category
        return "news/commentary"

    def _evidence_type_weight(self, evidence_type: str) -> float:
        weights = {
            "implementation case study": 1.0,
            "operational report": 0.9,
            "product/vendor case study": 0.82,
            "annual/reporting disclosure": 0.74,
            "executive interview": 0.68,
            "news/commentary": 0.56,
            "generic marketing / low-substance overview": 0.32,
        }
        return weights.get(evidence_type, 0.5)

    def _document_selection_score(self, assessment: dict[str, object]) -> float:
        rerank_score = max(0.0, min(1.0, float(assessment.get("rerank_relevance_score") or 0.0)))
        evidence_type_weight = self._evidence_type_weight(str(assessment.get("evidence_type") or ""))
        return (
            0.3 * float(assessment.get("match_confidence") or 0.0)
            + 0.22 * float(assessment.get("operating_specificity") or 0.0)
            + 0.14 * float(assessment.get("source_authority") or 0.0)
            + 0.1 * float(assessment.get("measurable_outcome_clarity") or 0.0)
            + 0.1 * evidence_type_weight
            + 0.08 * rerank_score
            - 0.28 * float(assessment.get("indirectness_risk") or 0.0)
        )

    def _document_rejection_reason(self, assessment: dict[str, object]) -> str | None:
        if not assessment.get("keep_recommendation"):
            return "llm_rejected"
        if not assessment.get("matched_capability"):
            return "no_capability_match"
        if float(assessment.get("match_confidence") or 0.0) < 0.62:
            return "low_capability_match"
        if float(assessment.get("operating_specificity") or 0.0) < 0.52:
            return "low_operating_specificity"
        if float(assessment.get("indirectness_risk") or 0.0) >= 0.3:
            return "indirectness_risk"
        if float(assessment.get("source_authority") or 0.0) < 0.4 and float(assessment.get("measurable_outcome_clarity") or 0.0) < 0.35:
            return "weak_authority_and_outcomes"
        if float(assessment.get("selection_score") or 0.0) < 0.53:
            return "low_selection_score"
        return None

    def _is_soft_diversity_candidate(self, assessment: dict[str, object]) -> bool:
        return (
            bool(assessment.get("matched_capability"))
            and float(assessment.get("match_confidence") or 0.0) >= 0.58
            and float(assessment.get("operating_specificity") or 0.0) >= 0.5
            and float(assessment.get("indirectness_risk") or 0.0) < 0.22
            and float(assessment.get("selection_score") or 0.0) >= 0.47
        )

    def _apply_post_curation_filters(self, assessments: list[dict[str, object]]) -> None:
        if not assessments:
            return
        self._reject_post_curation_duplicates(assessments)
        self._reject_same_capability_collapse(assessments)

    def _reject_post_curation_duplicates(self, assessments: list[dict[str, object]]) -> None:
        survivors = [item for item in assessments if item.get("rejection_reason") is None]
        if len(survivors) < 2:
            return
        for index, item in enumerate(survivors):
            if item.get("rejection_reason") is not None:
                continue
            for other in survivors[index + 1 :]:
                if other.get("rejection_reason") is not None:
                    continue
                if not self._are_near_duplicate_assessments(item, other):
                    continue
                loser = item
                winner = other
                if float(item.get("selection_score") or 0.0) >= float(other.get("selection_score") or 0.0):
                    winner = item
                    loser = other
                loser["rejection_reason"] = "post_curation_duplicate"
                logger.warning(
                    "benchmark duplicate evidence rejected kept=%s dropped=%s",
                    winner.get("url"),
                    loser.get("url"),
                )

    def _reject_same_capability_collapse(self, assessments: list[dict[str, object]]) -> None:
        survivors = [item for item in assessments if item.get("rejection_reason") is None]
        if len(survivors) < 2:
            return
        capabilities = {
            normalize_text(str(item.get("matched_capability") or "")).strip().lower()
            for item in survivors
            if normalize_text(str(item.get("matched_capability") or "")).strip()
        }
        if len(capabilities) != 1:
            return
        top_score = max(float(item.get("selection_score") or 0.0) for item in survivors)
        for item in survivors:
            if float(item.get("selection_score") or 0.0) >= top_score - 0.04:
                continue
            if (
                float(item.get("indirectness_risk") or 0.0) >= 0.18
                or float(item.get("operating_specificity") or 0.0) < 0.65
                or float(item.get("match_confidence") or 0.0) < 0.72
            ):
                item["rejection_reason"] = "collapsed_easy_capability"

    def _are_near_duplicate_assessments(self, left: dict[str, object], right: dict[str, object]) -> bool:
        left_url = str(left.get("url") or "")
        right_url = str(right.get("url") or "")
        if left_url and right_url and left_url == right_url:
            return True
        left_domain = self._url_domain(left_url)
        right_domain = self._url_domain(right_url)
        left_title = self._clean_evidence_text(str(left.get("title") or left.get("source_title") or ""))
        right_title = self._clean_evidence_text(str(right.get("title") or right.get("source_title") or ""))
        left_summary = self._clean_evidence_text(str(left.get("summary") or left.get("rewrite_label") or ""))
        right_summary = self._clean_evidence_text(str(right.get("summary") or right.get("rewrite_label") or ""))
        same_capability = (
            normalize_text(str(left.get("matched_capability") or "")).strip().lower()
            == normalize_text(str(right.get("matched_capability") or "")).strip().lower()
        )
        if left_domain and right_domain and left_domain == right_domain:
            if left_title and right_title and self._token_overlap(left_title, right_title) >= 0.72:
                return True
            if left_summary and right_summary and self._token_overlap(left_summary, right_summary) >= 0.84:
                return True
        if same_capability and left_summary and right_summary and self._token_overlap(left_summary, right_summary) >= 0.9:
            return True
        return False

    def _select_curated_links(
        self, assessments: list[dict[str, object]], language: str = "fr"
    ) -> list[dict[str, str | None]]:
        """The few evidence links shown under one leader, formatted for the report.

        Marks every assessment with whether it made the cut, because the debug endpoints report on
        the ones that did not.
        """
        selected = self._pick_diverse_links(assessments)
        selected = self._rebalance_selected_assessments(selected=selected, assessments=assessments)
        selected = self._enforce_leader_capability_diversity(selected=selected, assessments=assessments)

        for assessment in assessments:
            assessment["selected"] = assessment in selected

        return [
            self._curated_link(assessment, language=language)
            for assessment in selected
            if str(assessment.get("url") or "").strip()
        ]

    def _pick_diverse_links(self, assessments: list[dict[str, object]]) -> list[dict[str, object]]:
        """Take the best few links, nudging the pick towards covering different capabilities.

        Greedy rather than "top N by score", because the top three by score are frequently three
        articles about the same capability -- which reads as one point made three times rather than
        as evidence across the leader's practice. So a candidate whose capability is not yet
        represented gets a small bonus: enough to break a near-tie, too small to promote a link
        that is genuinely weaker.

        Candidates already rejected by the credibility filter never enter the running.
        """
        selected: list[dict[str, object]] = []
        covered_capabilities: set[str] = set()
        remaining = [item for item in assessments if item.get("rejection_reason") is None]

        while remaining and len(selected) < _MAX_CURATED_LINKS:
            best = max(
                remaining,
                key=lambda item: float(item.get("selection_score") or 0.0)
                + (
                    _NEW_CAPABILITY_BONUS
                    if str(item.get("matched_capability") or "").lower() not in covered_capabilities
                    else 0.0
                ),
            )
            selected.append(best)
            capability = normalize_text(str(best.get("matched_capability") or "")).strip().lower()
            if capability:
                covered_capabilities.add(capability)
            remaining = [item for item in remaining if item is not best]

        return selected

    def _curated_link(self, assessment: dict[str, object], *, language: str) -> dict[str, str | None]:
        """One selected assessment as the link shape the report renders.

        Every field prefers the model's rewrite and falls back to something derived from the raw
        search result, so no link is ever shown with a blank label or no stated reason.
        """
        return {
            "label": self._clean_evidence_text(str(assessment.get("rewrite_label") or ""))
            or self._fallback_evidence_label(
                {
                    "title": str(assessment.get("title") or ""),
                    "summary": str(assessment.get("summary") or ""),
                    "mapped_capability": str(assessment.get("matched_capability") or ""),
                    "source_title": str(assessment.get("source_title") or ""),
                },
                language=language,
            ),
            "url": str(assessment.get("url") or ""),
            "source_title": self._clean_source_title(
                raw_title=str(assessment.get("source_title") or ""),
                url=str(assessment.get("url") or ""),
            ),
            "mapped_capability": self._clean_evidence_text(str(assessment.get("matched_capability") or "")) or None,
            "why_relevant": self._clean_evidence_text(str(assessment.get("why_relevant") or ""))
            or self._evidence_relevance_line(assessment, language=language),
        }

    def _evidence_relevance_line(self, assessment: dict[str, object], *, language: str) -> str | None:
        """The stand-in for the model's own explanation of why a link is relevant.

        Used when the model returned nothing usable. It states the connection plainly from the
        capability and the search summary rather than leaving the link unexplained.
        """
        if (language or "").lower().startswith("fr"):
            return self._clean_evidence_text(
                f"Cet element de reference soutient {self._fr_capability_label(str(assessment.get('matched_capability') or 'le besoin identifie'))} grace a {assessment.get('summary') or 'des preuves publiques concretes'}"
            )
        return self._clean_evidence_text(
            f"This evidence supports {assessment.get('matched_capability') or 'the respondent gap'} through {assessment.get('summary') or 'concrete public proof'}"
        )

    def _link_capability_coverage(self, links: list[dict[str, str | None]]) -> list[str]:
        coverage: list[str] = []
        seen: set[str] = set()
        for link in links:
            capability = self._clean_evidence_text(str(link.get("mapped_capability") or ""))
            if not capability:
                continue
            lowered = capability.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            coverage.append(capability)
        return coverage

    def _rebalance_selected_assessments(
        self,
        *,
        selected: list[dict[str, object]],
        assessments: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if len(selected) < 2:
            return selected
        capability_counts: dict[str, int] = {}
        for item in selected:
            capability = normalize_text(str(item.get("matched_capability") or "")).strip().lower()
            if capability:
                capability_counts[capability] = capability_counts.get(capability, 0) + 1
        duplicated_capabilities = {cap for cap, count in capability_counts.items() if count > 1}
        if not duplicated_capabilities:
            return selected

        alternatives = [
            item
            for item in assessments
            if item not in selected and item.get("rejection_reason") is None
        ]
        if not alternatives:
            return selected

        for duplicate_capability in duplicated_capabilities:
            weakest_duplicate = min(
                [item for item in selected if normalize_text(str(item.get("matched_capability") or "")).strip().lower() == duplicate_capability],
                key=lambda item: float(item.get("selection_score") or 0.0),
                default=None,
            )
            if weakest_duplicate is None:
                continue
            replacement = max(
                [
                    item
                    for item in alternatives
                    if normalize_text(str(item.get("matched_capability") or "")).strip().lower() not in capability_counts
                ],
                key=lambda item: float(item.get("selection_score") or 0.0),
                default=None,
            )
            if replacement is None:
                continue
            if float(replacement.get("selection_score") or 0.0) + 0.06 >= float(weakest_duplicate.get("selection_score") or 0.0):
                selected = [replacement if item is weakest_duplicate else item for item in selected]
                capability_counts.pop(duplicate_capability, None)
                replacement_capability = normalize_text(str(replacement.get("matched_capability") or "")).strip().lower()
                if replacement_capability:
                    capability_counts[replacement_capability] = capability_counts.get(replacement_capability, 0) + 1
                alternatives = [item for item in alternatives if item is not replacement]
        return selected

    def _enforce_leader_capability_diversity(
        self,
        *,
        selected: list[dict[str, object]],
        assessments: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if len(selected) < 2:
            return selected
        selected_capabilities = {
            normalize_text(str(item.get("matched_capability") or "")).strip().lower()
            for item in selected
            if normalize_text(str(item.get("matched_capability") or "")).strip()
        }
        if len(selected_capabilities) > 1:
            return selected

        alternatives = [
            item
            for item in assessments
            if item not in selected
            and normalize_text(str(item.get("matched_capability") or "")).strip().lower() not in selected_capabilities
            and (
                item.get("rejection_reason") is None
                or (
                    item.get("soft_diversity_candidate")
                    and str(item.get("rejection_reason") or "") in {"low_selection_score", "weak_authority_and_outcomes"}
                )
            )
        ]
        if not alternatives:
            return selected

        weakest = min(selected, key=lambda item: float(item.get("selection_score") or 0.0))
        replacement = max(alternatives, key=lambda item: float(item.get("selection_score") or 0.0), default=None)
        if replacement is None:
            return selected
        if float(replacement.get("selection_score") or 0.0) + 0.09 < float(weakest.get("selection_score") or 0.0):
            return selected
        return [replacement if item is weakest else item for item in selected]

    def _curated_score(self, assessments: list[dict[str, object]], links: list[dict[str, str | None]]) -> float:
        if not links:
            return 0.0
        link_urls = {str(link.get("url") or "") for link in links if str(link.get("url") or "").strip()}
        selected_scores = [
            float(assessment.get("selection_score") or 0.0)
            for assessment in assessments
            if str(assessment.get("url") or "") in link_urls
        ]
        if selected_scores:
            return sum(selected_scores) / len(selected_scores)
        return self._fallback_curated_score(links)

    def _fallback_curated_score(self, links: list[dict[str, str | None]]) -> float:
        if not links:
            return 0.0
        coverage_bonus = min(len(self._link_capability_coverage(links)), 2) * 0.03
        return 0.52 + coverage_bonus

    def _leader_summary_from_assessments(
        self,
        *,
        company_name: str,
        requested_summary: str,
        selected_links: list[dict[str, str | None]],
        language: str = "fr",
    ) -> str | None:
        supported_capabilities = self._link_capability_coverage(selected_links)
        if requested_summary and supported_capabilities and not self._summary_looks_incomplete(requested_summary):
            if 15 <= len(requested_summary) <= 160:
                return requested_summary
        if not supported_capabilities:
            return requested_summary or None
        
        is_french = (language or "").lower().startswith("fr")
        if is_french:
            cap_labels = [self._fr_capability_label(cap) for cap in supported_capabilities]
            if len(cap_labels) == 1:
                return f"{company_name} se distingue sur {cap_labels[0]} grace a des pratiques de reference."
            return f"{company_name} se distingue sur {cap_labels[0]} et {cap_labels[1]} grace a des pratiques de reference."

        if len(supported_capabilities) == 1:
            return f"{company_name} shows concrete {supported_capabilities[0].lower()} through public benchmark evidence"
        return (
            f"{company_name} shows concrete {supported_capabilities[0].lower()} and "
            f"{supported_capabilities[1].lower()} through public benchmark evidence"
        )

    def _fr_capability_label(self, capability: str) -> str:
        key = normalize_text(capability).lower().strip()
        labels = {
            "decision-making": "la prise de decision",
            "ownership and governance": "l'ownership et la gouvernance",
            "feedback collection": "la collecte des retours clients",
            "use of insights": "l'exploitation des insights",
            "channel consistency": "la coherence multicanale",
            "journey visibility": "la visibilite des parcours",
            "measurement and continuous improvement": "la mesure et l'amelioration continue",
            "acting on pain points": "le traitement des points de douleur",
            "cx culture": "la culture CX",
        }
        return labels.get(key, capability)



    def _select_final_leaders(
        self,
        leaders: list[dict],
        *,
        pain_points: list[dict[str, str | None]],
    ) -> list[dict]:
        if len(leaders) <= 3:
            return leaders[:3]
        selected: list[dict] = []
        covered_capabilities: set[str] = set()
        target_capabilities = [
            normalize_text(str(item.get("capability") or "")).strip().lower()
            for item in pain_points[:3]
            if normalize_text(str(item.get("capability") or "")).strip()
        ]
        remaining = list(leaders)
        while remaining and len(selected) < 3:
            best = max(
                remaining,
                key=lambda item: float(item.get("_curated_score") or item.get("_semantic_score") or 0.0)
                + self._leader_diversity_bonus(
                    item=item,
                    covered_capabilities=covered_capabilities,
                    target_capabilities=target_capabilities,
                ),
            )
            selected.append(best)
            covered_capabilities.update(
                normalize_text(str(capability or "")).strip().lower()
                for capability in (best.get("_coverage_capabilities") or [])
                if normalize_text(str(capability or "")).strip()
            )
            remaining = [item for item in remaining if item is not best]
        selected.sort(
            key=lambda item: (
                -float(item.get("_curated_score") or item.get("_semantic_score") or 0.0),
                -len(item.get("_coverage_capabilities") or []),
                str(item.get("company_name") or ""),
            )
        )
        return selected[:3]

    def _leader_diversity_bonus(
        self,
        *,
        item: dict,
        covered_capabilities: set[str],
        target_capabilities: list[str],
    ) -> float:
        capabilities = [
            normalize_text(str(capability or "")).strip().lower()
            for capability in (item.get("_coverage_capabilities") or [])
            if normalize_text(str(capability or "")).strip()
        ]
        new_capabilities = [capability for capability in capabilities if capability not in covered_capabilities]
        target_bonus = sum(1 for capability in new_capabilities if capability in target_capabilities) * 0.05
        breadth_bonus = min(len(new_capabilities), 2) * 0.03
        duplicate_penalty = 0.04 if capabilities and not new_capabilities else 0.0
        return target_bonus + breadth_bonus - duplicate_penalty

    def _fallback_leader_summary(self, *, company_name: str, links: list[dict[str, str | None]], language: str = "fr") -> str | None:
        is_french = (language or "").lower().startswith("fr")
        source_title = self._clean_evidence_text(str((links[0] or {}).get("source_title") or "")) if links else ""
        if source_title:
            if is_french:
                return self._trim_leader_summary(f"{company_name} présente des éléments de référence via {source_title}.")
            return self._trim_leader_summary(f"{company_name} shows benchmark evidence through {source_title}.")
        if is_french:
            return self._trim_leader_summary(f"{company_name} présente des éléments de référence publics pour les pratiques CX.")
        return self._trim_leader_summary(f"{company_name} shows public benchmark evidence for CX practices.")


    def _summary_looks_incomplete(self, text: str) -> bool:
        cleaned = self._clean_evidence_text(text)
        if not cleaned:
            return True
        lowered = cleaned.lower()
        # English and French incomplete ending words
        incomplete_words = {
            "and", "via", "through", "with", "including", "like", "such", "as",
            "de", "des", "le", "la", "et", "à", "a", "grâce", "grace", "par",
            "pour", "sur", "avec", "dans", "comme", "du", "au", "aux", "en"
        }
        tokens = [t.strip() for t in re.split(r"[^a-zA-Z0-9àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+", lowered) if t.strip()]
        if not tokens:
            return True
        last_word = tokens[-1]
        if last_word in incomplete_words:
            return True
        if cleaned.endswith(("'", "\"", "/", "-", ":", ";", ",")):
            return True
        return False

    def _trim_leader_summary(self, text: str | None) -> str | None:
        summary = self._clean_evidence_text(text or "")
        if not summary:
            return None
        first_sentence = next((sentence for sentence in self._summary_sentences(summary) if sentence), summary)
        normalized = self._clean_evidence_text(first_sentence)
        if len(normalized) <= 160:
            return normalized
        shortened = normalized[:160].rsplit(" ", 1)[0].strip(" ,;:-")
        shortened = shortened or normalized[:160].strip(" ,;:-")
        while shortened and self._summary_looks_incomplete(shortened):
            candidate = shortened.rsplit(" ", 1)[0].strip(" ,;:-")
            if not candidate or candidate == shortened:
                break
            shortened = candidate
        return shortened or normalized[:160].strip(" ,;:-")


    def _parse_json_object(self, content: str | None) -> dict[str, object]:
        text = normalize_text(content or "").strip()
        if not text:
            return {}
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        return json.loads(text)

    def _fallback_evidence_label(self, link: dict[str, str | None], language: str = "fr") -> str:
        title = self._clean_evidence_text(str(link.get("title") or link.get("source_title") or ""))
        if title:
            if len(title) > 90:
                title = title[:90].rsplit(" ", 1)[0].strip(" ,;:-") + "..."
            return title
        summary = self._clean_evidence_text(str(link.get("summary") or ""))
        if summary:
            if len(summary) > 90:
                summary = summary[:90].rsplit(" ", 1)[0].strip(" ,;:-") + "..."
            return summary
        if (language or "").lower().startswith("fr"):
            return "Eléments de référence publics"
        return "Public benchmark evidence"

    def _best_matching_capability(
        self,
        *,
        link: dict[str, str | None],
        pain_points: list[dict[str, str | None]],
    ) -> str | None:
        text = self._clean_evidence_text(
            f"{link.get('title') or ''} {link.get('summary') or ''} {link.get('source_title') or ''}"
        ).lower()
        best_capability: str | None = None
        best_score = 0.0
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            if not capability:
                continue
            rubric = self._clean_evidence_text(
                " ".join(
                    [
                        str(item.get("capability_description") or ""),
                        str(item.get("action_hints") or ""),
                        str(item.get("level3_action_hints") or ""),
                    ]
                )
            ).lower()
            score = self._token_overlap(text, f"{capability.lower()} {rubric}")
            if score > best_score:
                best_score = score
                best_capability = capability
        return best_capability

    def _fallback_relevance_reason(
        self,
        *,
        link: dict[str, str | None],
        pain_points: list[dict[str, str | None]],
        language: str = "fr",
    ) -> str | None:
        is_french = (language or "").lower().startswith("fr")
        capability = self._best_matching_capability(link=link, pain_points=pain_points)
        if not capability:
            if is_french:
                return "Cette référence présente des pratiques sectorielles d'excellence en matière d'expérience client."
            return "This reference presents industry best practices for optimizing customer experience."

        cap_key = normalize_text(capability).lower().strip()
        if is_french:
            cap_label = self._fr_capability_label(capability)
            if "feedback" in cap_key or "retour" in cap_key:
                return f"Cette référence met en évidence des pratiques concrètes pour {cap_label}."
            elif "measure" in cap_key or "mesure" in cap_key or "improve" in cap_key:
                return f"Cette référence illustre l'évaluation des indicateurs de performance liés à {cap_label}."
            elif "decision" in cap_key:
                return f"Cette référence montre comment les insights clients soutiennent {cap_label}."
            return f"Cette référence présente des éléments de preuve à l'appui de {cap_label}."
        else:
            if "feedback" in cap_key or "retour" in cap_key:
                return f"This reference demonstrates concrete practices for {capability.lower()}."
            elif "measure" in cap_key or "mesure" in cap_key or "improve" in cap_key:
                return f"This reference illustrates key metrics and performance monitoring for {capability.lower()}."
            elif "decision" in cap_key:
                return f"This reference shows how customer evidence supports {capability.lower()}."
            return f"This reference provides evidence supporting key processes in {capability.lower()}."


    def _resolve_mapped_capability(
        self,
        raw_value: str | None,
        pain_points: list[dict[str, str | None]],
    ) -> str | None:
        normalized = normalize_text(raw_value).lower().strip()
        if not normalized:
            return None
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            if capability and normalized in capability.lower():
                return capability
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            if capability and self._token_overlap(normalized, capability.lower()) >= 0.6:
                return capability
        return None

    def _pain_point_evidence_context(self, pain_points: list[dict[str, str | None]]) -> str:
        if not pain_points:
            return "Capability gaps being benchmarked: customer feedback, service quality, and digital experience."

        lines = ["Capability gaps being benchmarked:"]
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            if not capability:
                continue
            description = self._clean_evidence_text(str(item.get("capability_description") or ""))
            gap_detail = self._sanitized_pain_point_detail(item)

            line = capability
            if description:
                line += f" - {description}"
            if gap_detail:
                line += f" Current gap: {gap_detail}"
            lines.append(line)

        if len(lines) == 1:
            return "Capability gaps being benchmarked: customer feedback, service quality, and digital experience."
        return "\n".join(lines)

    def _is_duplicate_document(self, existing_docs: list[dict], candidate: dict) -> bool:
        if not existing_docs:
            return False

        candidate_title = self._clean_evidence_text(str(candidate.get("title") or ""))
        candidate_summary = self._clean_evidence_text(str(candidate.get("summary") or ""))
        candidate_domain = self._url_domain(str(candidate.get("url") or ""))
        if not candidate_title and not candidate_summary:
            return False

        for existing in existing_docs:
            existing_title = self._clean_evidence_text(str(existing.get("title") or ""))
            existing_summary = self._clean_evidence_text(str(existing.get("summary") or ""))
            existing_domain = self._url_domain(str(existing.get("url") or ""))
            if candidate_title and existing_title and candidate_title.lower() == existing_title.lower():
                return True
            if (
                candidate_domain
                and existing_domain
                and candidate_domain == existing_domain
                and candidate_title
                and existing_title
                and self._token_overlap(candidate_title, existing_title) >= 0.75
            ):
                return True
            if candidate_summary and existing_summary and self._token_overlap(candidate_summary, existing_summary) >= 0.82:
                return True
        return False

    def _token_overlap(self, left: str, right: str) -> float:
        left_tokens = {token for token in re.split(r"[^a-z0-9]+", left.lower()) if len(token) >= 4}
        right_tokens = {token for token in re.split(r"[^a-z0-9]+", right.lower()) if len(token) >= 4}
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = len(left_tokens & right_tokens)
        baseline = max(1, min(len(left_tokens), len(right_tokens)))
        return intersection / baseline

    def _trim_to_limit(self, text: str, limit: int) -> str:
        cleaned = self._clean_evidence_text(text or "")
        if len(cleaned) <= limit:
            return cleaned
        shortened = cleaned[:limit - 3].rsplit(" ", 1)[0].strip(" ,;:-")
        if not shortened:
            shortened = cleaned[:limit - 3]
        return shortened + "..."


class TelecomSemanticLeadersService(SemanticLeadersService):
    """Backward-compatible alias for the former telecom-only leaders service."""
