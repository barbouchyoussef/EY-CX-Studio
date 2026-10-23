"""Deterministic aggregation over classified reviews.

Everything in this module is plain arithmetic: no LLM is involved. The numbers it
produces are what the report quotes as fact, and they are also what gets fed into the
report prompt so the narrative is written against real distributions instead of an
unordered set of theme names.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from app.schemas.scraping import (
    PlatformResult,
    PlatformSentiment,
    RatingDistribution,
    RatingSentimentCheck,
    ReportEvidence,
    ScrapedReview,
    SentimentBreakdown,
    ThemeFrequency,
    ThemeVerbatim,
    TopicMomentum,
    TopicMovement,
    TrendPoint,
    TrendSeries,
)

logger = logging.getLogger(__name__)

# A theme mentioned once or twice in a large corpus is noise, not a pattern. Themes below
# this share are still counted but never promoted into the ranked lists.
_MIN_THEME_SHARE_PCT = 3.0
_MAX_RANKED_THEMES = 8
_MAX_VERBATIMS_PER_THEME = 3
_VERBATIM_MAX_CHARS = 320


# A time axis is only drawn when the data can carry one. A percentage needs a real sample
# behind it, and two points are a comparison rather than a trend -- measured on live runs,
# a national telco with 232 collected reviews still averaged ~7 per month, which would have
# swung the line between 33% and 100% on samples of three.
_TREND_MIN_SAMPLE = 10
_TREND_MIN_POINTS = 3
_TREND_MAX_MONTHS = 12
_TREND_MAX_QUARTERS = 8

_MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _classified(reviews: list[ScrapedReview]) -> list[ScrapedReview]:
    return [r for r in reviews if r.classification]


def _sentiment_split(reviews: list[ScrapedReview]) -> tuple[int, int, int]:
    pos = sum(1 for r in reviews if r.classification.sentiment == "positive")
    neu = sum(1 for r in reviews if r.classification.sentiment == "neutral")
    neg = sum(1 for r in reviews if r.classification.sentiment == "negative")
    return pos, neu, neg


def compute_sentiment(reviews: list[ScrapedReview]) -> SentimentBreakdown | None:
    """Sentiment split over the classified subset of `reviews`."""
    classified = _classified(reviews)
    total = len(classified)
    if total == 0:
        return None
    pos, neu, neg = _sentiment_split(classified)
    return SentimentBreakdown(
        positive_pct=round(pos / total * 100, 1),
        neutral_pct=round(neu / total * 100, 1),
        negative_pct=round(neg / total * 100, 1),
        classified_count=total,
    )


def compute_overall_sentiment(platforms: list[PlatformResult]) -> SentimentBreakdown | None:
    return compute_sentiment([r for p in platforms for r in p.reviews])


def _avg_rating(reviews: list[ScrapedReview]) -> float | None:
    rated = [r.rating for r in reviews if r.rating is not None]
    return round(sum(rated) / len(rated), 2) if rated else None


def compute_platform_sentiment(platforms: list[PlatformResult]) -> list[PlatformSentiment]:
    """Per-channel sentiment, so the report can say which channel is actually bleeding."""
    out: list[PlatformSentiment] = []
    for platform in platforms:
        if platform.status != "success" or not platform.reviews:
            continue
        breakdown = compute_sentiment(platform.reviews)
        if breakdown is None:
            continue
        out.append(
            PlatformSentiment(
                platform=platform.platform,
                positive_pct=breakdown.positive_pct,
                neutral_pct=breakdown.neutral_pct,
                negative_pct=breakdown.negative_pct,
                classified_count=breakdown.classified_count,
                review_count=platform.review_count,
                avg_rating=_avg_rating(platform.reviews),
                summary_stat=platform.summary_stat,
                reply_rate_pct=platform.reply_rate_pct,
            )
        )
    # Worst channel first: that is the one the consultant needs to look at.
    out.sort(key=lambda p: p.negative_pct, reverse=True)
    return out


def compute_rating_distribution(platforms: list[PlatformResult]) -> RatingDistribution | None:
    """Star distribution across every rated review, all channels combined."""
    buckets: Counter[int] = Counter()
    for platform in platforms:
        for review in platform.reviews:
            if review.rating is None:
                continue
            star = int(round(review.rating))
            if 1 <= star <= 5:
                buckets[star] += 1
    total = sum(buckets.values())
    if total == 0:
        return None
    return RatingDistribution(
        one=buckets[1],
        two=buckets[2],
        three=buckets[3],
        four=buckets[4],
        five=buckets[5],
        total=total,
        average=round(sum(star * n for star, n in buckets.items()) / total, 2),
    )


def _rank(
    counter: Counter[str],
    negative_counter: Counter[str],
    total: int,
    *,
    apply_floor: bool,
    platform_counter: dict[str, Counter[str]] | None = None,
) -> list[ThemeFrequency]:
    ranked: list[ThemeFrequency] = []
    for label, count in counter.most_common():
        share = round(count / total * 100, 1)
        if apply_floor and share < _MIN_THEME_SHARE_PCT and len(ranked) >= 3:
            # Keep at least the top 3 even in a small corpus, then apply the noise floor.
            break
        by_platform = dict((platform_counter or {}).get(label, Counter()).most_common())
        ranked.append(
            ThemeFrequency(
                label=label,
                count=count,
                share_pct=share,
                negative_pct=round(negative_counter[label] / count * 100, 1) if count else 0.0,
                by_platform=by_platform,
            )
        )
        if len(ranked) >= _MAX_RANKED_THEMES:
            break
    return ranked


def compute_theme_frequencies(platforms: list[PlatformResult]) -> list[ThemeFrequency]:
    """Themes ranked by how often they actually come up, with the share of mentions that
    are negative -- which is what separates 'talked about' from 'a problem'."""
    classified = _classified([r for p in platforms for r in p.reviews])
    if not classified:
        return []
    counts: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    per_platform: dict[str, Counter[str]] = defaultdict(Counter)
    for review in classified:
        # A theme repeated inside one review still only counts once for that review.
        for theme in set(review.classification.themes or []):
            counts[theme] += 1
            per_platform[theme][review.platform] += 1
            if review.classification.sentiment == "negative":
                negative[theme] += 1
    return _rank(counts, negative, len(classified), apply_floor=True, platform_counter=per_platform)


def compute_complaint_frequencies(platforms: list[PlatformResult]) -> list[ThemeFrequency]:
    """Complaint categories ranked by volume, as a share of negative reviews.

    Each category also records which channels it surfaced on: knowing that billing
    complaints cluster on Trustpilot while queueing complaints cluster on Google Maps is
    what turns a ranked list into something a consultant can act on.
    """
    classified = _classified([r for p in platforms for r in p.reviews])
    negatives = [r for r in classified if r.classification.sentiment == "negative"]
    if not negatives:
        return []
    counts: Counter[str] = Counter()
    per_platform: dict[str, Counter[str]] = defaultdict(Counter)
    for review in negatives:
        category = review.classification.complaint_category
        if category:
            counts[category] += 1
            per_platform[category][review.platform] += 1
    if not counts:
        return []
    # Every complaint here is by definition negative, so negative share is always 100%.
    return _rank(
        counts, counts.copy(), len(negatives), apply_floor=False, platform_counter=per_platform
    )


def _shorten(text: str) -> str:
    clean = " ".join(text.split())
    if len(clean) <= _VERBATIM_MAX_CHARS:
        return clean
    return clean[: _VERBATIM_MAX_CHARS - 1].rstrip() + "…"


def collect_verbatims(
    platforms: list[PlatformResult],
    labels: list[str],
) -> list[ThemeVerbatim]:
    """Pull real customer quotes backing each ranked label.

    Evidence is what makes the report defensible in front of a client, so each quote keeps
    its channel, rating and date rather than being flattened into an anonymous string.
    """
    by_label: dict[str, list[ThemeVerbatim]] = defaultdict(list)
    wanted = {label.lower() for label in labels}

    for platform in platforms:
        for review in platform.reviews:
            if not review.classification:
                continue
            tags = set(review.classification.themes or [])
            if review.classification.complaint_category:
                tags.add(review.classification.complaint_category)
            for tag in tags:
                if tag.lower() not in wanted:
                    continue
                if len(by_label[tag]) >= _MAX_VERBATIMS_PER_THEME:
                    continue
                by_label[tag].append(
                    ThemeVerbatim(
                        label=tag,
                        platform=platform.platform,
                        text=_shorten(review.text),
                        rating=review.rating,
                        date=review.date,
                        sentiment=review.classification.sentiment,
                        url=review.url,
                        source=review.source,
                    )
                )

    # Preserve the ranking order the caller asked for.
    ordered: list[ThemeVerbatim] = []
    for label in labels:
        ordered.extend(by_label.get(label, []))
    return ordered


def _parse_year_month(raw: str | None) -> tuple[int, int] | None:
    """Year and month out of an ISO-ish timestamp, or None if it isn't one."""
    if not raw or len(raw) < 7:
        return None
    try:
        year, month = int(raw[0:4]), int(raw[5:7])
    except ValueError:
        return None
    if not (1900 < year < 2200 and 1 <= month <= 12):
        return None
    return year, month


def _bucket_index(year: int, month: int, granularity: str) -> int:
    """Absolute bucket number, so consecutive periods differ by exactly one."""
    return year * 12 + (month - 1) if granularity == "month" else year * 4 + (month - 1) // 3


def _bucket_label(index: int, granularity: str) -> tuple[str, str]:
    if granularity == "month":
        year, month = divmod(index, 12)
        return f"{year}-{month + 1:02d}", f"{_MONTH_NAMES[month]} {year}"
    year, quarter = divmod(index, 4)
    return f"{year}-Q{quarter + 1}", f"Q{quarter + 1} {year}"


def _build_series(reviews: list[ScrapedReview], granularity: str) -> TrendSeries | None:
    """Bucket reviews by period and keep only the metrics each bucket can support.

    Every bucket in the range is emitted, including empty ones, so the axis stays evenly
    spaced -- a line that silently skips a quiet month misrepresents the gap. A metric is
    left null where its sample is too small, which renders as a break rather than a
    confident-looking point.
    """
    span = _TREND_MAX_MONTHS if granularity == "month" else _TREND_MAX_QUARTERS
    dated: dict[int, list[ScrapedReview]] = defaultdict(list)
    for review in reviews:
        parsed = _parse_year_month(review.date)
        if parsed is None:
            continue
        dated[_bucket_index(*parsed, granularity)].append(review)

    if not dated:
        return None

    newest = max(dated)
    indices = [i for i in range(newest - span + 1, newest + 1)]

    points: list[TrendPoint] = []
    for index in indices:
        bucket = dated.get(index, [])
        classified = _classified(bucket)
        rated = [r.rating for r in bucket if r.rating is not None]
        period, label = _bucket_label(index, granularity)
        negative = sum(1 for r in classified if r.classification.sentiment == "negative")
        positive = sum(1 for r in classified if r.classification.sentiment == "positive")
        neutral = sum(1 for r in classified if r.classification.sentiment == "neutral")
        big_enough = len(classified) >= _TREND_MIN_SAMPLE
        points.append(
            TrendPoint(
                period=period,
                label=label,
                reviews=len(bucket),
                classified_count=len(classified),
                negative_pct=(round(negative / len(classified) * 100, 1) if big_enough else None),
                positive_pct=(round(positive / len(classified) * 100, 1) if big_enough else None),
                neutral_pct=(round(neutral / len(classified) * 100, 1) if big_enough else None),
                avg_rating=(
                    round(sum(rated) / len(rated), 2) if len(rated) >= _TREND_MIN_SAMPLE else None
                ),
            )
        )

    has_sentiment = sum(1 for p in points if p.negative_pct is not None) >= _TREND_MIN_POINTS
    has_rating = sum(1 for p in points if p.avg_rating is not None) >= _TREND_MIN_POINTS
    if not (has_sentiment or has_rating):
        return None

    # The axis starts and ends where the line can actually be drawn. Periods before the
    # first plottable point are collection tail, not brand history, and leading blanks make
    # a four-point chart look like a collapse from nothing. Gaps in the middle are kept:
    # those are real quiet periods between two measured ones.
    def has_metric(point: TrendPoint) -> bool:
        return point.negative_pct is not None or point.avg_rating is not None

    first = next(i for i, p in enumerate(points) if has_metric(p))
    last = len(points) - next(i for i, p in enumerate(reversed(points)) if has_metric(p))
    return TrendSeries(
        granularity=granularity,
        points=points[first:last],
        has_sentiment=has_sentiment,
        has_rating=has_rating,
        min_sample=_TREND_MIN_SAMPLE,
    )


def _plottable(series: TrendSeries) -> int:
    return sum(1 for p in series.points if p.negative_pct is not None or p.avg_rating is not None)


def compute_reply_rate(platforms: list[PlatformResult]) -> tuple[float | None, int]:
    """One reply rate across the channels that expose it, and the base it rests on.

    Only some channels report replies (Trustpilot does, Google Maps does not in our
    pipeline), so the base is returned alongside: a 0% on eight reviews must not be shown
    as if it covered all two hundred. A simple average would also let a three-review
    channel swing the headline as hard as a two-hundred-review one, so it is weighted by
    review count.
    """
    weighted = 0.0
    total = 0
    for platform in platforms:
        if platform.reply_rate_pct is None:
            continue
        n = len(platform.reviews) or platform.review_count
        if n <= 0:
            continue
        weighted += platform.reply_rate_pct * n
        total += n
    return (round(weighted / total, 1) if total else None, total)


# Below this, "how often rating and comment disagree" is a fraction of too little to state.
_RATING_SENTIMENT_MIN = 10


def compute_rating_sentiment_check(
    platforms: list[PlatformResult],
) -> RatingSentimentCheck | None:
    """How often the star rating and the written sentiment point opposite ways."""
    high_neg = 0
    low_pos = 0
    both = 0
    for platform in platforms:
        for review in platform.reviews:
            if review.classification is None or review.rating is None:
                continue
            both += 1
            sentiment = review.classification.sentiment
            if review.rating >= 4 and sentiment == "negative":
                high_neg += 1
            elif review.rating <= 2 and sentiment == "positive":
                low_pos += 1
    if both < _RATING_SENTIMENT_MIN:
        return None
    mismatch = high_neg + low_pos
    return RatingSentimentCheck(
        both_count=both,
        high_rating_negative=high_neg,
        low_rating_positive=low_pos,
        mismatch_count=mismatch,
        mismatch_pct=round(mismatch / both * 100, 1),
    )


def compute_trend(platforms: list[PlatformResult]) -> TrendSeries | None:
    """A time axis, but only when the collected reviews can honestly support one.

    Both granularities are built and the better-covered one wins, rather than taking the
    first that clears the floor: monthly is the period a reader expects, but on a real run
    it produced three plotted points against nine blank months, which reads as a broken
    chart. Coarsening to quarters pools those same reviews into periods that each carry a
    real sample. When neither reaches half coverage there is no trend section at all --
    the correct outcome, since most single businesses receive single-digit reviews a month
    and drawing that as a line turns sampling noise into an apparent collapse or recovery.
    """
    reviews = [r for p in platforms for r in p.reviews]
    candidates = [
        series
        for series in (_build_series(reviews, "month"), _build_series(reviews, "quarter"))
        if series is not None and series.points and _plottable(series) / len(series.points) >= 0.5
    ]
    if not candidates:
        return None
    # Most plotted points wins; monthly breaks the tie, being the finer detail.
    return max(candidates, key=lambda s: (_plottable(s), s.granularity == "month"))


# Momentum splits the history into two halves and compares them, rather than plotting many
# thin periods. Two solid samples say "this is growing" more honestly than a dozen noisy
# points -- and single businesses simply do not get enough reviews for the finer view.
_MOMENTUM_MIN_WINDOW = 20  # classified reviews required in EACH half
_MOMENTUM_MIN_MENTIONS = 4  # combined mentions before a category is worth showing
_MOMENTUM_MIN_PER_SIDE = 3  # AND at least this many in each half -- see below
_MOMENTUM_STABLE_BAND = 4.0  # within +/- this many points of change reads as flat
# Candidate window lengths, in months, tried shortest-first: the tightest comparison that
# still has a real sample on both sides is the most actionable one.
_MOMENTUM_WINDOWS = (3, 6, 12)
_MOMENTUM_MAX_ITEMS = 6


def _month_label(year_month: tuple[int, int]) -> str:
    year, month = year_month
    return f"{_MONTH_NAMES[month - 1]} {year}"


def compute_topic_momentum(platforms: list[PlatformResult]) -> "TopicMomentum | None":
    """Which complaint categories are gaining or losing share of customer feedback.

    Every other section is a snapshot; this is the one axis that says whether a problem is
    growing or fading. The dated, classified reviews are split into an earlier and a recent
    half of equal size, and each category's share of feedback is compared between them.
    Below a real per-half sample it returns nothing, for the same reason the trend line
    does: a shift measured on a handful of reviews is noise dressed up as a movement.
    """
    dated = [
        r
        for p in platforms
        for r in p.reviews
        if r.classification and _parse_year_month(r.date) is not None
    ]
    if len(dated) < 2 * _MOMENTUM_MIN_WINDOW:
        return None
    dated.sort(key=lambda r: r.date)  # ISO-8601 strings sort chronologically

    # Split by TIME, not by review count. Splitting a sorted list in half gives two equal
    # samples over wildly unequal periods -- on real runs here, eight years against one month
    # -- because the collectors are recency-biased. Comparing those measures when reviews were
    # collected, not how complaints moved. Two equal-length windows ending at the most recent
    # month are comparable by construction.
    def _months_between(a: tuple[int, int], b: tuple[int, int]) -> int:
        return (b[0] - a[0]) * 12 + (b[1] - a[1])

    latest = max(ym for ym in (_parse_year_month(r.date) for r in dated) if ym is not None)

    earlier: list[ScrapedReview] = []
    recent: list[ScrapedReview] = []
    window = 0
    # Prefer the tightest window that still carries a real sample on both sides: a 3-month
    # comparison is far more actionable than a 12-month one, but only if the data supports it.
    for candidate in _MOMENTUM_WINDOWS:
        rec, earl = [], []
        for r in dated:
            ym = _parse_year_month(r.date)
            if ym is None:
                continue
            age = _months_between(ym, latest)  # 0 = the most recent month
            if 0 <= age < candidate:
                rec.append(r)
            elif candidate <= age < 2 * candidate:
                earl.append(r)
        if len(rec) >= _MOMENTUM_MIN_WINDOW and len(earl) >= _MOMENTUM_MIN_WINDOW:
            earlier, recent, window = earl, rec, candidate
            break

    if not window:
        logger.info(
            "momentum: skipped — no equal-length window carries %d classified reviews on both sides",
            _MOMENTUM_MIN_WINDOW,
        )
        return None

    # The residual bucket has no interpretable movement: "Other rose 4 points" tells a reader
    # nothing to act on. Skip it (English taxonomy and the legacy French one alike).
    _catch_all = {"other", "autre"}

    def _counts(reviews: list[ScrapedReview]) -> Counter[str]:
        tally: Counter[str] = Counter()
        for r in reviews:
            category = r.classification.complaint_category
            if category and category.strip().lower() not in _catch_all:
                tally[category] += 1
        return tally

    e_counts, r_counts = _counts(earlier), _counts(recent)
    # Share denominator is the whole half, not just its complaints: "12% of all feedback is
    # now about delivery" is both better anchored and more legible than a share of negatives,
    # whose denominator swings with overall sentiment.
    items: list[TopicMovement] = []
    for label in set(e_counts) | set(r_counts):
        ec, rc = e_counts[label], r_counts[label]
        # Both a combined floor and a per-side one. The combined test alone let a category
        # through on its history: 14 mentions then 1 passed, and was drawn as a 24-point
        # collapse when the recent evidence was a single review.
        if ec + rc < _MOMENTUM_MIN_MENTIONS or min(ec, rc) < _MOMENTUM_MIN_PER_SIDE:
            continue
        es = round(ec / len(earlier) * 100, 1)
        rs = round(rc / len(recent) * 100, 1)
        delta = round(rs - es, 1)
        direction = (
            "rising" if delta > _MOMENTUM_STABLE_BAND
            else "falling" if delta < -_MOMENTUM_STABLE_BAND
            else "stable"
        )
        items.append(
            TopicMovement(
                label=label,
                earlier_count=ec,
                recent_count=rc,
                earlier_share=es,
                recent_share=rs,
                delta=delta,
                direction=direction,
            )
        )
    if not items:
        return None
    # Biggest movers first; ties broken by current size so the larger problem leads.
    items.sort(key=lambda i: (abs(i.delta), i.recent_share), reverse=True)
    del items[_MOMENTUM_MAX_ITEMS:]

    def _window_label(reviews: list[ScrapedReview]) -> str:
        yms = [ym for ym in (_parse_year_month(r.date) for r in reviews) if ym is not None]
        lo, hi = min(yms), max(yms)
        return _month_label(lo) if lo == hi else f"{_month_label(lo)} – {_month_label(hi)}"

    return TopicMomentum(
        earlier_label=_window_label(earlier),
        recent_label=_window_label(recent),
        earlier_total=len(earlier),
        recent_total=len(recent),
        items=items,
    )


def build_evidence(platforms: list[PlatformResult]) -> ReportEvidence:
    """Everything the report states as a number, computed once, in one place."""
    themes = compute_theme_frequencies(platforms)
    complaints = compute_complaint_frequencies(platforms)
    all_reviews = [r for p in platforms for r in p.reviews]
    collected = sum(p.review_count for p in platforms)
    classified_count = len(_classified(all_reviews))
    with_text = sum(1 for r in all_reviews if r.text.strip())
    reply_rate, reply_base = compute_reply_rate(platforms)

    return ReportEvidence(
        reviews_collected=collected,
        reviews_with_text=with_text,
        reviews_classified=classified_count,
        overall_sentiment=compute_overall_sentiment(platforms),
        platform_sentiment=compute_platform_sentiment(platforms),
        rating_distribution=compute_rating_distribution(platforms),
        top_themes=themes,
        top_complaints=complaints,
        verbatims=collect_verbatims(
            platforms,
            [t.label for t in complaints[:4]] + [t.label for t in themes[:4]],
        ),
        trend=compute_trend(platforms),
        momentum=compute_topic_momentum(platforms),
        reply_rate_pct=reply_rate,
        reply_rate_base=reply_base,
        rating_sentiment=compute_rating_sentiment_check(platforms),
    )
