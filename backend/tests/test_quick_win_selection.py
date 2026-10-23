"""Choosing the handful of quick wins the maturity report proposes.

Two rules worth pinning, neither of which had coverage. A capability only qualifies when an admin
authored a quick-win guideline for the exact level it scored -- the template mechanism exists so
the report never invents an action. And selection deliberately overrides the ranking to spread the
wins across axes, because the weakest axis produces the easiest wins and a pure ranking would put
four fixes to the same part of the business in front of the client.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.schemas.final_report import FinalReportCapabilityItem
from app.services.assessment.reporting.final_report_service import (
    _MAX_QUICK_WINS,
    _maturity_band_key,
    ReportBuilderService,
)


@pytest.fixture
def service():
    """Only the pure selection methods are exercised, so the collaborators stay unused."""
    return ReportBuilderService(
        db=None, assessments=None, capabilities=None, llm_service=None,
        benchmark_service=None, scoring_service=None, uow=None, settings=get_settings(),
    )


def candidate(capability_id: int, axis: str, score: float):
    return {"capability_id": capability_id, "axis": axis, "quick_win_rank_score": score}


# ── spreading across axes ───────────────────────────────────────────────────────────────────


def test_a_short_list_is_returned_whole(service):
    given = [candidate(i, "Analyze", i) for i in range(_MAX_QUICK_WINS)]
    assert service._spread_quick_wins_across_axes(given) == given


def test_the_best_of_each_axis_is_taken_before_any_axis_gets_a_second(service):
    """Ranked best-first, the top three all sit in Analyze; two of them must give way."""
    ranked = [
        candidate(1, "Analyze", 1.0),
        candidate(2, "Analyze", 2.0),
        candidate(3, "Analyze", 3.0),
        candidate(4, "Manage", 4.0),
        candidate(5, "Improve", 5.0),
    ]
    picked = service._spread_quick_wins_across_axes(ranked)
    assert [c["capability_id"] for c in picked] == [1, 4, 5, 2]


def test_axis_names_are_matched_regardless_of_case_or_spacing(service):
    ranked = [
        candidate(1, "Analyze", 1.0),
        candidate(2, " analyze ", 2.0),
        candidate(3, "ANALYZE", 3.0),
        candidate(4, "Manage", 4.0),
        candidate(5, "Improve", 5.0),
    ]
    picked = service._spread_quick_wins_across_axes(ranked)
    assert [c["capability_id"] for c in picked] == [1, 4, 5, 2]


def test_remaining_slots_fall_back_to_the_ranking(service):
    """With only two axes available, the spread pass runs out and the ranking finishes the job."""
    ranked = [
        candidate(1, "Analyze", 1.0),
        candidate(2, "Manage", 2.0),
        candidate(3, "Analyze", 3.0),
        candidate(4, "Manage", 4.0),
        candidate(5, "Analyze", 5.0),
    ]
    picked = service._spread_quick_wins_across_axes(ranked)
    assert [c["capability_id"] for c in picked] == [1, 2, 3, 4]


def test_never_more_than_the_cap(service):
    ranked = [candidate(i, f"Axis{i}", float(i)) for i in range(12)]
    assert len(service._spread_quick_wins_across_axes(ranked)) == _MAX_QUICK_WINS


def test_no_capability_is_proposed_twice(service):
    ranked = [candidate(1, "Analyze", 1.0), candidate(2, "Manage", 2.0), candidate(3, "Improve", 3.0),
              candidate(4, "Manage", 4.0), candidate(5, "Analyze", 5.0)]
    picked = service._spread_quick_wins_across_axes(ranked)
    ids = [c["capability_id"] for c in picked]
    assert len(ids) == len(set(ids))


# ── qualifying as a candidate ───────────────────────────────────────────────────────────────


def scored_row(**overrides):
    base = {"id": 7, "maturity_level_id": 2, "assessment_status": "assessed", "label": "Feedback collection"}
    return {**base, **overrides}


@pytest.fixture
def qualifying(service):
    """A row that qualifies, plus the three lookups it is resolved against."""
    item = FinalReportCapabilityItem(
        capability_id=7, axis="Analyze", capability="Feedback collection",
        maturity_band="Basic", assessment_status="assessed", confidence=0.9,
        rationale="Surveys are sent but never read.",
    )
    return {
        "capability_item_by_id": {7: item},
        "maturity_number_by_id": {2: 2},
        "template_by_key": {(7, 2): {"quick_win_guideline": "Route detractors to an owner.",
                                     "after_text": "Detractors answered within 48h.",
                                     "owner_hint": "CX lead", "timeline_hint": "30 days"}},
    }


def test_a_fully_specified_row_becomes_a_candidate(service, qualifying):
    got = service._quick_win_candidate(scored_row(), **qualifying)
    assert got is not None
    assert got["capability_id"] == 7
    assert got["quick_win_guideline"] == "Route detractors to an owner."
    assert got["owner_hint"] == "CX lead"
    assert got["confidence"] == pytest.approx(0.9)


@pytest.mark.parametrize(
    "row_change, reason",
    [
        ({"assessment_status": "not_assessed"}, "never assessed"),
        ({"assessment_status": None}, "status missing entirely"),
        ({"id": None}, "no capability recorded"),
        ({"maturity_level_id": None}, "no level recorded"),
        ({"id": 999}, "no scored item to draw wording from"),
        ({"maturity_level_id": 99}, "level number unknown"),
    ],
)
def test_a_row_missing_what_the_action_needs_is_skipped(service, qualifying, row_change, reason):
    assert service._quick_win_candidate(scored_row(**row_change), **qualifying) is None, reason


def test_no_authored_guideline_means_no_quick_win(service, qualifying):
    """The whole point of the template table: without authored copy there is nothing to propose."""
    qualifying["template_by_key"] = {(7, 2): {"after_text": "Something."}}
    assert service._quick_win_candidate(scored_row(), **qualifying) is None


def test_a_blank_guideline_counts_as_absent(service, qualifying):
    qualifying["template_by_key"] = {(7, 2): {"quick_win_guideline": "   "}}
    assert service._quick_win_candidate(scored_row(), **qualifying) is None


def test_optional_authored_fields_are_none_when_unset(service, qualifying):
    qualifying["template_by_key"] = {(7, 2): {"quick_win_guideline": "Do the thing."}}
    got = service._quick_win_candidate(scored_row(), **qualifying)
    assert got["after_text"] is None and got["owner_hint"] is None and got["timeline_hint"] is None


def test_the_rationale_falls_back_to_the_row_when_the_item_has_none(service, qualifying):
    qualifying["capability_item_by_id"][7].rationale = None
    got = service._quick_win_candidate(scored_row(justification="From the scoring pass."), **qualifying)
    assert got["rationale"] == "From the scoring pass."


# ── band labels ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label, expected",
    [
        ("Advanced", "advanced"), ("Avancé", "advanced"),
        ("Established", "established"), ("Établi", "established"), ("Intermédiaire", "established"),
        ("Basic", "basic"), ("Basique", "basic"),
        ("In progress", "unknown"), ("Not scored", "unknown"), ("", "unknown"), (None, "unknown"),
    ],
)
def test_bands_are_recognised_in_either_report_language(label, expected):
    assert _maturity_band_key(label) == expected
