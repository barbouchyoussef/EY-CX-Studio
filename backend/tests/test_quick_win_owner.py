"""Turning a free-text owner hint into the job title printed beside a quick win.

Admins author the hint, so it arrives as anything from "CX" to "the digital transformation
programme steering team". The rule with real consequences is the governance override: a governance
capability is assigned to the CX lead even when the hint says operations, because "operations owns
governance" is how governance ends up owned by nobody.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.assessment.reporting.final_report_service import (
    _MAX_OWNER_WORDS,
    _QUICK_WIN_OWNER_TITLES,
    _is_governance_capability,
    ReportBuilderService,
)


@pytest.fixture
def service():
    return ReportBuilderService(
        db=None, assessments=None, capabilities=None, llm_service=None,
        benchmark_service=None, scoring_service=None, uow=None, settings=get_settings(),
    )


def owner(service, hint, capability="Feedback collection", language="en", axis="Analyze"):
    return service._normalize_quick_win_owner_label(
        raw_owner=hint, axis=axis, capability=capability, language=language
    )


def title(role, lang="en"):
    return _QUICK_WIN_OWNER_TITLES[role][lang]


# ── mapping a hint onto a standard title ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hint, role",
    [
        ("CX", "cx"), ("customer experience team", "cx"),
        ("analytics team", "insights"), ("Data science", "insights"),
        ("Service operations manager", "operations"),
        ("Support", "support"),
        ("Transformation office", "transformation"), ("programme manager", "transformation"),
        ("Marketing", "marketing"),
        ("Digital", "digital"),
        ("HR", "people"), ("training lead", "people"),
        ("Product", "product"),
    ],
)
def test_a_hint_naming_a_function_gets_that_functions_title(service, hint, role):
    assert owner(service, hint) == title(role)


def test_titles_are_rendered_in_the_report_language(service):
    assert owner(service, "Support", language="fr") == title("support", "fr")
    assert owner(service, "Support", language="en") == title("support", "en")
    assert title("support", "fr") != title("support", "en")


def test_the_first_matching_term_wins(service):
    """Order in the table is the tie-break, so a hint naming two functions is not ambiguous."""
    assert owner(service, "CX and operations") == title("cx")


# ── hints too vague to print ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("hint", ["leadership", "management", "team", "business", "company"])
def test_a_hint_that_names_no_one_falls_back(service, hint):
    """These say a person exists without saying who, which is no more useful than saying nothing."""
    assert owner(service, hint) != hint


def test_a_long_description_is_not_treated_as_a_job_title(service):
    hint = " ".join(["word"] * (_MAX_OWNER_WORDS + 1))
    assert owner(service, hint) != hint


def test_an_empty_hint_falls_back(service):
    assert owner(service, "") and owner(service, "   ")


# ── a specific hint is kept ─────────────────────────────────────────────────────────────────


def test_an_unrecognised_but_specific_hint_is_printed_as_written(service):
    assert owner(service, "Chief Customer Officer") == "Chief Customer Officer"


def test_any_mention_of_cx_maps_to_the_cx_lead(service):
    """"cx" is matched as a substring and sits first in the table, so it wins over a longer hint."""
    assert owner(service, "Head of CX") == title("cx")
    assert owner(service, "CX ops") == title("cx")


# ── the governance override ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "capability", ["Ownership and governance", "Governance", "Decision-making", "decision making"]
)
def test_governance_capabilities_are_recognised(capability):
    assert _is_governance_capability(capability) is True


def test_a_non_governance_capability_is_not(service):
    assert _is_governance_capability("Feedback collection") is False


def test_governance_goes_to_the_cx_lead_when_the_hint_names_no_function(service):
    assert owner(service, "leadership", capability="Governance") == title("cx")
    assert owner(service, "", capability="Governance") == title("cx")


def test_governance_is_taken_off_operations(service):
    """The rule with teeth: operations "owning" governance is how it ends up owned by nobody."""
    assert owner(service, "Operations", capability="Ownership and governance") == title("cx")


def test_governance_leaves_other_named_functions_alone(service):
    """Deliberate is deliberate -- only the operations reading is overridden."""
    assert owner(service, "Digital", capability="Governance") == title("digital")
    assert owner(service, "Insights", capability="Governance") == title("insights")


def test_a_non_governance_capability_keeps_operations(service):
    assert owner(service, "Operations", capability="Feedback collection") == title("operations")
