"""Covers when a time axis is drawn at all.

Measured on real runs before this existed: a national telco with 232 collected reviews
averaged ~7 a month, so a monthly line would have swung between 33% and 100% on samples of
three -- rendering sampling noise as a collapse and recovery. The rule is therefore that the
data decides, and 'no chart' is a valid, common outcome.
"""

from __future__ import annotations

from app.schemas.scraping import PlatformResult, ReviewClassification, ScrapedReview
from app.services.scraping.analytics import compute_trend


def _review(date: str, sentiment: str = "negative", rating: float = 2.0) -> ScrapedReview:
    r = ScrapedReview(platform="Google Maps", text="…", rating=rating, date=date)
    r.classification = ReviewClassification(sentiment=sentiment, confidence=0.9, themes=[])
    return r


def _platforms(reviews: list[ScrapedReview]) -> list[PlatformResult]:
    return [PlatformResult(platform="Google Maps", status="success",
                           review_count=len(reviews), reviews=reviews)]


def _month(year: int, month: int, n: int, sentiment: str = "negative", rating: float = 2.0):
    return [_review(f"{year}-{month:02d}-15T10:00:00Z", sentiment, rating) for _ in range(n)]


def test_a_history_too_thin_even_for_quarters_produces_no_trend_at_all():
    """Two reviews a month pools to six a quarter -- still below the floor, so nothing is
    drawn. (Five a month would pool to fifteen and legitimately qualify: coarsening is a
    real fix, not a loophole.)"""
    reviews: list[ScrapedReview] = []
    for month in range(1, 13):
        reviews += _month(2026, month, 2)
    assert compute_trend(_platforms(reviews)) is None


def test_no_reviews_produces_no_trend():
    assert compute_trend(_platforms([])) is None


def test_reviews_without_dates_produce_no_trend():
    reviews = [ScrapedReview(platform="Google Maps", text="…", rating=3.0) for _ in range(80)]
    assert compute_trend(_platforms(reviews)) is None


def test_a_dense_monthly_history_is_plotted_monthly():
    reviews: list[ScrapedReview] = []
    for month in range(1, 7):
        reviews += _month(2026, month, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    assert trend.granularity == "month"
    assert len(trend.points) == 6
    assert all(p.negative_pct is not None for p in trend.points)


def test_a_history_too_thin_monthly_is_pooled_into_quarters():
    """Six a month cannot carry a percentage; eighteen a quarter can."""
    reviews: list[ScrapedReview] = []
    for month in range(1, 13):
        reviews += _month(2026, month, 6)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    assert trend.granularity == "quarter"
    assert all(p.negative_pct is not None for p in trend.points)


def test_a_period_below_the_sample_floor_is_left_blank_not_guessed():
    reviews = _month(2026, 1, 20) + _month(2026, 2, 2) + _month(2026, 3, 20) + _month(2026, 4, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    if trend.granularity == "month":
        february = next(p for p in trend.points if p.period == "2026-02")
        assert february.negative_pct is None, "n=2 must not be plotted as a point"
        assert february.reviews == 2, "but the period still reports its real volume"


def test_the_axis_starts_where_the_line_can_be_drawn():
    """Leading periods with a stray review are collection tail, not brand history."""
    reviews = _month(2024, 1, 1) + _month(2024, 6, 1)
    for month in range(1, 7):
        reviews += _month(2026, month, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    assert trend.points[0].period.startswith("2026"), "the 2024 strays must be trimmed"


def test_a_gap_between_two_measured_periods_is_kept():
    """A real quiet period is information; silently closing the gap is not."""
    reviews = _month(2026, 1, 20) + _month(2026, 2, 0) + _month(2026, 3, 20) + _month(2026, 4, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    if trend.granularity == "month":
        periods = [p.period for p in trend.points]
        assert "2026-02" in periods, "the quiet month must still occupy the axis"


def test_rating_can_carry_the_trend_when_sentiment_cannot():
    """Ratings need no classification, so their sample is the larger one."""
    reviews: list[ScrapedReview] = []
    for month in range(1, 7):
        # Rated but never classified -- the classification cap leaves reviews in this state.
        reviews += [
            ScrapedReview(platform="Google Maps", text="", rating=4.0,
                          date=f"2026-{month:02d}-15T10:00:00Z")
            for _ in range(20)
        ]
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    assert trend.has_rating is True
    assert trend.has_sentiment is False
    assert all(p.avg_rating == 4.0 for p in trend.points)


def test_a_malformed_date_does_not_break_the_series():
    reviews = [_review("not-a-date") for _ in range(5)]
    for month in range(1, 7):
        reviews += _month(2026, month, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    assert len(trend.points) == 6


def test_the_computed_percentage_is_correct():
    reviews = _month(2026, 1, 15, "negative") + _month(2026, 1, 5, "positive")
    for month in (2, 3):
        reviews += _month(2026, month, 20)
    trend = compute_trend(_platforms(reviews))
    assert trend is not None
    january = next(p for p in trend.points if p.period.startswith("2026-01") or p.period == "2026-Q1")
    if january.period == "2026-01":
        assert january.negative_pct == 75.0
        assert january.classified_count == 20
