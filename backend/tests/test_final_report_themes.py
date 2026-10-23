"""Choosing what the maturity report presents as strengths and pain points.

Extracted from a 318-line function where it had no coverage. The rule worth pinning is the
fallback: when nothing scored Advanced, the report does not show an empty strengths section --
it falls back to the best-evidenced Established capabilities, ranked by confidence, because with
nothing outstanding to show, how well-supported a claim is decides which is worth making.
"""

from __future__ import annotations

from app.schemas.final_report import FinalReportCapabilityItem
from app.services.assessment.reporting.final_report_service import (
    _MAX_THEMES,
    _axis_short_copy,
    _select_report_themes,
)


def capability(band: str, name: str = "Feedback collection", confidence: float | None = None):
    return FinalReportCapabilityItem(
        axis="Analyze", capability=name, maturity_band=band,
        assessment_status="assessed", confidence=confidence,
    )


# ── strengths ───────────────────────────────────────────────────────────────────────────────


def test_advanced_capabilities_are_the_strengths():
    themes = _select_report_themes([capability("Advanced", "A"), capability("Basic", "B")])
    assert [t.capability for t in themes.strengths] == ["A"]


def test_established_capabilities_are_ignored_when_something_is_advanced():
    """Established is a fallback, not a supplement -- mixing them would flatten the distinction."""
    themes = _select_report_themes([capability("Advanced", "A"), capability("Established", "E")])
    assert [t.capability for t in themes.strengths] == ["A"]


def test_it_falls_back_to_the_best_evidenced_established_capabilities():
    themes = _select_report_themes([
        capability("Established", "low", confidence=0.2),
        capability("Established", "high", confidence=0.9),
        capability("Established", "mid", confidence=0.5),
    ])
    assert [t.capability for t in themes.strengths] == ["high", "mid", "low"]


def test_a_missing_confidence_ranks_last_rather_than_crashing():
    themes = _select_report_themes([
        capability("Established", "unknown", confidence=None),
        capability("Established", "known", confidence=0.4),
    ])
    assert [t.capability for t in themes.strengths] == ["known", "unknown"]


def test_no_strengths_at_all_is_an_empty_list():
    themes = _select_report_themes([capability("Basic", "B")])
    assert themes.strengths == []


# ── pain points ─────────────────────────────────────────────────────────────────────────────


def test_basic_capabilities_are_the_pain_points():
    themes = _select_report_themes([capability("Basic", "B"), capability("Advanced", "A")])
    assert [t.capability for t in themes.pain_points] == ["B"]


# ── counts vs what is shown ─────────────────────────────────────────────────────────────────


def test_only_three_are_shown_but_the_full_count_is_reported():
    """The summary says how many the assessment found; the body shows at most three."""
    themes = _select_report_themes([capability("Basic", f"B{i}") for i in range(7)])
    assert len(themes.pain_points) == _MAX_THEMES
    assert len(themes.pain_candidates) == 7


def test_the_established_fallback_is_also_capped():
    themes = _select_report_themes([
        capability("Established", f"E{i}", confidence=i / 10) for i in range(6)
    ])
    assert len(themes.strengths) == _MAX_THEMES
    assert len(themes.strength_candidates) == _MAX_THEMES


def test_a_theme_carries_the_capability_forward_intact():
    source = FinalReportCapabilityItem(
        axis="Manage", capability="Ownership", maturity_band="Basic",
        assessment_status="assessed", rationale="No single owner",
        recommendation="Appoint one", priority="high",
    )
    theme = _select_report_themes([source]).pain_points[0]
    assert (theme.axis, theme.capability, theme.rationale, theme.recommendation, theme.priority) == (
        "Manage", "Ownership", "No single owner", "Appoint one", "high",
    )


# ── hero copy lookup ────────────────────────────────────────────────────────────────────────


def test_axis_copy_differs_by_role_and_language():
    strongest_en = _axis_short_copy("Manage", "strongest", "en")
    priority_en = _axis_short_copy("Manage", "priority", "en")
    assert strongest_en and priority_en and strongest_en != priority_en
    assert _axis_short_copy("Manage", "strongest", "fr") != strongest_en


def test_axis_copy_is_case_insensitive():
    assert _axis_short_copy("ANALYZE", "priority", "en") == _axis_short_copy("analyze", "priority", "en")


def test_an_unknown_axis_has_no_copy_rather_than_raising():
    """"N/A" is a real axis value when nothing has been scored."""
    assert _axis_short_copy("N/A", "strongest", "en") is None
    assert _axis_short_copy(None, "strongest", "en") is None
