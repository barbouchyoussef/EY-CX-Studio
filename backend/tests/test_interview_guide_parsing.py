"""Turning a model's guide JSON into question items.

This was a closure defined inside a `try` block in the middle of a 203-line function, so none of
it could be tested. It exists because the model does not return one stable shape: field names vary
between runs and `follow_up` arrives as either a string or a list. Those are the cases below.
"""

from __future__ import annotations

import pytest

from app.services.assessment.reporting.reporting_service import _parse_question_items


def test_reads_the_standard_shape():
    items = _parse_question_items([
        {"question": "How do you collect feedback?", "rationale": "Establishes the baseline",
         "follow_up": "Which channels?"},
    ])
    assert len(items) == 1
    assert items[0].question == "How do you collect feedback?"
    assert items[0].rationale == "Establishes the baseline"
    assert items[0].follow_up == "Which channels?"


def test_accepts_the_alternative_field_names():
    """The model alternates between these without warning, so both are read."""
    items = _parse_question_items([{"question_text": "Who owns CX?", "reason": "Ownership matters"}])
    assert items[0].question == "Who owns CX?"
    assert items[0].rationale == "Ownership matters"


def test_accepts_why_as_a_rationale():
    items = _parse_question_items([{"question": "Q", "why": "because"}])
    assert items[0].rationale == "because"


def test_a_follow_up_list_becomes_a_bulleted_string():
    """`follow_up` comes back as a list often enough that flattening it is not optional."""
    items = _parse_question_items([
        {"question": "Q", "follow_up": ["Which channels?", "How often?"]},
    ])
    assert items[0].follow_up == "- Which channels?\n- How often?"


def test_empty_entries_in_a_follow_up_list_are_dropped():
    items = _parse_question_items([{"question": "Q", "follow_up": ["Only this", "", None]}])
    assert items[0].follow_up == "- Only this"


def test_a_question_with_no_text_is_dropped():
    """Rendering it would put an empty row in the consultant's guide."""
    items = _parse_question_items([
        {"question": "", "rationale": "orphan"},
        {"question": "   ", "rationale": "whitespace only"},
        {"question": "Real question"},
    ])
    assert [i.question for i in items] == ["Real question"]


def test_missing_optional_fields_become_empty_strings():
    items = _parse_question_items([{"question": "Q"}])
    assert items[0].rationale == ""
    assert items[0].follow_up == ""


def test_whitespace_is_trimmed():
    items = _parse_question_items([{"question": "  Q  ", "rationale": "\n R \n"}])
    assert items[0].question == "Q"
    assert items[0].rationale == "R"


def test_a_missing_section_yields_no_questions():
    """A section the model omitted must not raise -- the guide renders with that part empty."""
    assert _parse_question_items(None) == []


def test_a_non_list_payload_yields_no_questions():
    """Seen in practice: the model returns an object or a string where a list was asked for."""
    assert _parse_question_items({"question": "Q"}) == []
    assert _parse_question_items("introduction_questions") == []


def test_non_dict_entries_are_skipped_without_losing_the_rest():
    items = _parse_question_items(["a bare string", {"question": "Real"}, None])
    assert [i.question for i in items] == ["Real"]


# ── the profile survives a round trip ───────────────────────────────────────────────────────
#
# It did not. `InterviewGuideResponse` carried no `profile` at all, so opening a saved guide gave
# the client nothing to send back, and its autosave (`g.profile || profile`) fell through to the
# form's default of "CEO". Reopening a Marketing or IT Lead interview and touching it silently
# relabelled it -- which is how an interview whose questions open by asking about the Marketing
# Director's role came to be filed under CEO.

import json  # noqa: E402

from app.schemas.interview_guide import (  # noqa: E402
    GenerateInterviewGuideRequest,
    InterviewGuideResponse,
    SaveInterviewGuideRequest,
)
from app.services.assessment.reporting.reporting_service import (  # noqa: E402
    _CompanyProfile,
    _parse_guide_response,
)
from fastapi import HTTPException


def _guide_json() -> str:
    return json.dumps({
        "executive_summary": "A summary.", "unanswered_areas": [],
        "introduction_questions": [
            {"question": "Tell me about your role as Marketing Director.",
             "rationale": "Sets context", "follow_up": ""}
        ],
        "manage_questions": [], "analyze_questions": [],
        "improve_questions": [], "closure_questions": [],
    })


def test_incomplete_guide_is_rejected_instead_of_returning_empty_sections():
    req = GenerateInterviewGuideRequest(company_name="Acme", profile="CEO", language="en")
    with pytest.raises(HTTPException) as error:
        _parse_guide_response(
            json.dumps({"executive_summary": "Summary", "unanswered_areas": []}),
            req,
            _CompanyProfile(name="Acme", sector=None, size=None, region=None),
        )
    assert error.value.status_code == 502


def test_guide_with_no_questions_is_rejected():
    req = GenerateInterviewGuideRequest(company_name="Acme", profile="CEO", language="en")
    payload = {
        "executive_summary": "Summary",
        "unanswered_areas": [],
        "introduction_questions": [], "manage_questions": [],
        "analyze_questions": [], "improve_questions": [], "closure_questions": [],
    }
    with pytest.raises(HTTPException):
        _parse_guide_response(
            json.dumps(payload), req,
            _CompanyProfile(name="Acme", sector=None, size=None, region=None),
        )


def test_a_generated_guide_knows_who_it_is_for():
    """Its first autosave stores this, so it must not rely on the client's form default."""
    req = GenerateInterviewGuideRequest(company_name="Acme", profile="Marketing", language="en")
    guide = _parse_guide_response(_guide_json(), req, _CompanyProfile(name="Acme", sector=None, size=None, region=None))
    assert guide.profile == "Marketing"


def test_the_response_schema_can_carry_a_profile():
    """The field the client reads back. Optional, because guides stored before it exists have
    none in their payload -- the GET fills it from the guide's own column."""
    assert "profile" in InterviewGuideResponse.model_fields
    assert InterviewGuideResponse.model_fields["profile"].default is None


def test_saving_still_requires_a_profile():
    """Nothing here should let a save land without one and inherit a default instead."""
    assert SaveInterviewGuideRequest.model_fields["profile"].is_required()
