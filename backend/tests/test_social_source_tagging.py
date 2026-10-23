"""Facebook source tagging: page vs keyword must survive into the report verbatims."""

from __future__ import annotations

from app.schemas.scraping import (
    PlatformResult,
    ReviewClassification,
    ScrapedReview,
    ThemeVerbatim,
)
from app.services.scraping.analytics import collect_verbatims


def _review(text, source, theme="billing"):
    return ScrapedReview(
        platform="Facebook", text=text, source=source,
        classification=ReviewClassification(sentiment="negative", confidence=0.9, themes=[theme]),
    )


def test_scraped_review_and_verbatim_have_source_field():
    assert "source" in ScrapedReview.model_fields
    assert "source" in ThemeVerbatim.model_fields


def test_collect_verbatims_propagates_source():
    platform = PlatformResult(
        platform="Facebook", status="success", review_count=2,
        reviews=[
            _review("Charged twice on my official page complaint", "page"),
            _review("Saw a keyword mention about billing", "keyword"),
        ],
    )
    verbatims = collect_verbatims([platform], ["billing"])
    sources = {v.source for v in verbatims}
    assert sources == {"page", "keyword"}, "each verbatim keeps where it came from"
    # And the mapping is per-review, not lost/flattened.
    page_v = [v for v in verbatims if "official page" in v.text.lower()]
    assert page_v and page_v[0].source == "page"
