"""Turning EY search results into the benchmark card's links.

The card pairs EY's own decks with EY publications found by web search. A model pass is meant to
clean each result's title and write a relevance line, but it is optional -- no key, a failed call,
or a partial answer all leave the deterministic fallback to do the work. These tests cover that
fallback, because it is what actually ships whenever the model pass is skipped.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.assessment.reporting.telecom_semantic_leaders_service import (
    _MAX_LINK_LABEL_CHARS,
    _MAX_WHY_RELEVANT_CHARS,
    SemanticLeadersService,
    _truncate,
)


@pytest.fixture
def service():
    return SemanticLeadersService()


def result(title="EY digital transformation study", url="https://www.ey.com/en_gl/a", summary="A study."):
    return {"title": title, "url": url, "summary": summary}


# ── the model's wording wins when it is there ───────────────────────────────────────────────


def test_curated_label_and_relevance_are_used_as_given(service):
    link = service._ey_evidence_link(
        result(title="Raw title | EY - Global"),
        {"label": "Rebuilding onboarding at scale", "why_relevant": "Shows a 40% drop in churn."},
    )
    assert link["label"] == "Rebuilding onboarding at scale"
    assert link["why_relevant"] == "Shows a 40% drop in churn."


def test_a_blank_curated_field_falls_back_rather_than_shipping_empty(service):
    """A partial model answer is the common failure, not a total one."""
    link = service._ey_evidence_link(result(summary="Real summary."), {"label": "  ", "why_relevant": ""})
    assert link["label"]
    assert link["why_relevant"] == "Real summary."


# ── the fallback: strip EY's own boilerplate ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "Customer experience in telecom | EY - Global",
        "Customer experience in telecom | EY - US",
        "Customer experience in telecom | EY - UK",
        "Customer experience in telecom | EY - Taiwan",
        "Customer experience in telecom | EY",
        "Customer experience in telecom - EY",
    ],
)
def test_every_country_suffix_is_stripped_from_the_label(service, raw):
    link = service._ey_evidence_link(result(title=raw), None)
    assert link["label"] == "Customer experience in telecom"


def test_the_marketing_tagline_is_removed_from_the_relevance_line(service):
    link = service._ey_evidence_link(
        result(summary="The better the question the better the answer. Telecoms cut churn by 12%."),
        None,
    )
    assert "better the question" not in link["why_relevant"].lower()
    assert "Telecoms cut churn by 12%." in link["why_relevant"]


def test_the_working_world_tagline_is_removed_too(service):
    link = service._ey_evidence_link(result(summary="Building a better working world. Real finding here."), None)
    assert "working world" not in link["why_relevant"].lower()


def test_both_fields_are_cut_to_the_card_size(service):
    link = service._ey_evidence_link(result(title="x" * 300, summary="y" * 300), None)
    assert len(link["label"]) <= _MAX_LINK_LABEL_CHARS
    assert len(link["why_relevant"]) <= _MAX_WHY_RELEVANT_CHARS


def test_a_link_always_carries_its_url_and_benchmark_tag(service):
    link = service._ey_evidence_link(result(url="https://www.ey.com/en_gl/insights/x"), {"label": "L"})
    assert link["url"] == "https://www.ey.com/en_gl/insights/x"
    assert link["mapped_capability"] == "Industry Benchmark"
    assert link["source_title"]


# ── truncation ──────────────────────────────────────────────────────────────────────────────


def test_short_text_is_left_exactly_as_it_is():
    assert _truncate("short", 10) == "short"
    assert _truncate("exactly10!", 10) == "exactly10!"


def test_the_ellipsis_counts_against_the_limit():
    """The limit is what the card can render, so the "..." has to fit inside it."""
    assert _truncate("abcdefghijk", 10) == "abcdefg..."
    assert len(_truncate("abcdefghijk", 10)) == 10


# ── the search step ─────────────────────────────────────────────────────────────────────────


def test_no_search_runs_when_the_decks_already_fill_the_card(service):
    """Two decks leave one slot; none leaves zero, and a search for zero results is wasted."""
    async def fail(_query):
        raise AssertionError("should not search when there are no slots")

    service._web_search = fail
    assert asyncio.run(service._search_ey_publications(sector_label="Telecom", slots=0)) == []


def test_a_search_failure_costs_links_not_the_card(service):
    async def boom(_query):
        raise RuntimeError("LangSearch down")

    service._web_search = boom
    assert asyncio.run(service._search_ey_publications(sector_label="Telecom", slots=2)) == []


def test_results_are_capped_at_the_free_slots(service):
    async def five(_query):
        return [result(url=f"https://www.ey.com/{i}") for i in range(5)]

    service._web_search = five
    found = asyncio.run(service._search_ey_publications(sector_label="Telecom", slots=2))
    assert len(found) == 2
