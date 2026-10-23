"""Covers topic momentum: which complaint categories gain or lose share over time.

The discipline mirrors the trend line's. A movement is only shown when each half of the
history carries a real sample -- comparing a category's share across two handfuls of reviews
would report noise as a rising problem, which is exactly what a CX report must not do.
"""

from __future__ import annotations

from app.schemas.scraping import PlatformResult, ReviewClassification, ScrapedReview
from app.services.scraping.analytics import compute_topic_momentum


def _review(date: str, complaint: str | None, sentiment: str = "negative") -> ScrapedReview:
    r = ScrapedReview(platform="Google Maps", text="…", rating=2.0, date=date)
    r.classification = ReviewClassification(
        sentiment=sentiment, confidence=0.9, themes=[], complaint_category=complaint
    )
    return r


def _platforms(reviews: list[ScrapedReview]) -> list[PlatformResult]:
    return [PlatformResult(platform="Google Maps", status="success",
                           review_count=len(reviews), reviews=reviews)]


def _run(earlier: list[str | None], recent: list[str | None]):
    """Build a history with a clean date gap between the two halves and compute momentum."""
    reviews = [_review(f"2025-02-{i % 27 + 1:02d}T10:00:00Z", c) for i, c in enumerate(earlier)]
    reviews += [_review(f"2026-06-{i % 27 + 1:02d}T10:00:00Z", c) for i, c in enumerate(recent)]
    return compute_topic_momentum(_platforms(reviews))


def test_a_thin_history_yields_no_momentum():
    """Below the per-half floor, a comparison is noise -- so there is none."""
    m = _run(["Wait times and delays"] * 10, ["Wait times and delays"] * 10)
    assert m is None


def test_a_rising_category_is_detected():
    earlier = (["Wait times and delays"] * 4) + (["Pricing, billing and fees"] * 21)
    recent = (["Wait times and delays"] * 15) + (["Pricing, billing and fees"] * 10)
    m = _run(earlier, recent)
    assert m is not None
    wait = next(i for i in m.items if i.label == "Wait times and delays")
    assert wait.direction == "rising"
    assert wait.recent_share > wait.earlier_share
    assert wait.earlier_count == 4 and wait.recent_count == 15


def test_a_falling_category_is_detected():
    earlier = (["Pricing, billing and fees"] * 18) + (["Wait times and delays"] * 7)
    recent = (["Pricing, billing and fees"] * 3) + (["Wait times and delays"] * 22)
    m = _run(earlier, recent)
    pricing = next(i for i in m.items if i.label == "Pricing, billing and fees")
    assert pricing.direction == "falling"
    assert pricing.delta < 0


def test_a_small_shift_reads_as_stable():
    # 12/25 vs 13/25 -> +4 points, inside the stable band.
    earlier = (["Wait times and delays"] * 12) + (["Pricing, billing and fees"] * 13)
    recent = (["Wait times and delays"] * 13) + (["Pricing, billing and fees"] * 12)
    m = _run(earlier, recent)
    wait = next(i for i in m.items if i.label == "Wait times and delays")
    assert wait.direction == "stable"


def test_the_catch_all_other_is_excluded():
    earlier = (["Other"] * 12) + (["Wait times and delays"] * 13)
    recent = (["Other"] * 3) + (["Wait times and delays"] * 22)
    m = _run(earlier, recent)
    assert all(i.label.lower() != "other" for i in m.items)


def test_a_category_below_the_mention_floor_is_dropped():
    # 'Reliability and outages' appears once in total -- not enough to claim a movement.
    earlier = (["Wait times and delays"] * 24) + (["Reliability and outages"])
    recent = ["Wait times and delays"] * 25
    m = _run(earlier, recent)
    assert all(i.label != "Reliability and outages" for i in m.items)


def test_shares_are_of_the_whole_half_not_just_complaints():
    """Denominator is every classified review in the half, so a share is 'of all feedback'."""
    earlier = (["Wait times and delays"] * 5) + ([None] * 20)  # 25 classified, 5 complaints
    recent = (["Wait times and delays"] * 10) + ([None] * 15)  # 25 classified, 10 complaints
    m = _run(earlier, recent)
    wait = next(i for i in m.items if i.label == "Wait times and delays")
    assert wait.earlier_share == 20.0  # 5 / 25
    assert wait.recent_share == 40.0   # 10 / 25


def test_reviews_without_dates_are_ignored():
    reviews = [_review("2025-02-10T00:00:00Z", "Wait times and delays") for _ in range(25)]
    reviews += [_review("2026-06-10T00:00:00Z", "Wait times and delays") for _ in range(25)]
    reviews += [ScrapedReview(platform="Google Maps", text="x", rating=1.0)]  # no date
    m = compute_topic_momentum(_platforms(reviews))
    assert m is not None
    assert m.earlier_total + m.recent_total == 50


def test_items_are_ordered_by_size_of_movement():
    earlier = (["Wait times and delays"] * 3) + (["Pricing, billing and fees"] * 10) + (["Staff and customer relations"] * 12)
    recent = (["Wait times and delays"] * 14) + (["Pricing, billing and fees"] * 8) + (["Staff and customer relations"] * 3)
    m = _run(earlier, recent)
    deltas = [abs(i.delta) for i in m.items]
    assert deltas == sorted(deltas, reverse=True)
