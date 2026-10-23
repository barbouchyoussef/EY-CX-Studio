"""Deciding which capabilities get a recommendation and which get a question instead.

The report cannot have holes: every assessed capability leaves the batch generator with either a
recommendation or a specific question back to the client. These tests cover the two decisions that
route it -- the gate before the model call, and the assembly that pairs each capability with its
final text.

The gate is deliberately strict. A recommendation the client cannot trace back to something they
said reads as invented, and that costs more credibility than saying nothing.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.assessment.reporting.evidence_quality import EvidenceQuality
from app.services.assessment.reporting.recommendation_service import (
    RecommendationService,
    _default_clarification_question,
)


@pytest.fixture
def service():
    """Only the pure decision methods are exercised, so the collaborators stay unused."""
    return RecommendationService(
        db=None, assessments=None, capabilities=None, llm_service=None,
        scoring_service=None, uow=None, settings=get_settings(),
    )


@pytest.fixture
def floor(service):
    return service.settings.RECOMMENDATION_MIN_CONFIDENCE


def item(service, **overrides):
    """A capability that passes the gate, unless a test breaks one thing about it."""
    base = {
        "capability_id": 1,
        "axis": "Analyze",
        "capability_name": "Feedback collection",
        "confidence": 1.0,
        "evidence": ["We run an NPS survey every quarter."],
        "evidence_quality": EvidenceQuality.STRONG.value,
        "admin_guideline": None,
        "business_impact": None,
        "priority_hint": "high",
    }
    return {**base, **overrides}


# ── the gate ────────────────────────────────────────────────────────────────────────────────


def test_a_well_evidenced_capability_passes(service):
    assert service._too_thin_to_recommend(item(service)) is False


def test_an_unscored_capability_is_held_back(service):
    assert service._too_thin_to_recommend(item(service, confidence=None)) is True


def test_confidence_below_the_floor_is_held_back(service, floor):
    assert service._too_thin_to_recommend(item(service, confidence=floor - 0.01)) is True


def test_confidence_exactly_at_the_floor_passes(service, floor):
    """The floor is a minimum, not an exclusive bound."""
    assert service._too_thin_to_recommend(item(service, confidence=floor)) is False


def test_no_evidence_is_held_back_however_confident_the_score(service):
    assert service._too_thin_to_recommend(item(service, confidence=1.0, evidence=[])) is True


def test_weak_evidence_is_held_back(service):
    assert service._too_thin_to_recommend(
        item(service, evidence_quality=EvidenceQuality.WEAK.value)
    ) is True


def test_a_missing_quality_rating_counts_as_weak(service):
    """Absent means unrated, and an unrated capability is not one to advise on."""
    assert service._too_thin_to_recommend(item(service, evidence_quality=None)) is True


# ── splitting the batch ─────────────────────────────────────────────────────────────────────


def test_the_gate_splits_the_batch_and_asks_about_what_it_holds_back(service):
    good = item(service, capability_id=1)
    thin = item(service, capability_id=2, evidence=[])

    pre_gated, candidates = service._gate_batch_items([good, thin], language="en")

    assert [c["capability_id"] for c in candidates] == [1]
    assert set(pre_gated) == {2}
    held = pre_gated[2]
    assert held.status == "needs_clarification"
    assert held.clarification_question
    assert held.recommendation_text is None


# ── assembling the final results ────────────────────────────────────────────────────────────


def assemble(service, items, generated=None, fallbacks=None):
    return service._assemble_batch_results(
        llm_items=items,
        pre_gated={},
        generated=generated or {},
        fallback_text_by_capability=fallbacks or {},
        maturity_level_id_by_capability={1: 3},
        language="en",
    )


def test_a_written_recommendation_is_stitched_into_one_paragraph_and_stored(service):
    generated = {
        1: {
            "status": "ok",
            "title": "Close the loop",
            "why_this": "Feedback is collected but never answered.",
            "primary_action": "Route detractors to a named owner.",
            "secondary_action": None,
            "expected_impact": "Fewer repeat complaints.",
            "evidence_used": ["NPS survey"],
        }
    }
    results, output_rows = assemble(service, [item(service)], generated=generated)

    assert results[0].status == "ok"
    for fragment in ["Close the loop", "never answered", "named owner", "repeat complaints"]:
        assert fragment in results[0].recommendation_text
    assert len(output_rows) == 1
    assert output_rows[0]["maturity_level_id"] == 3
    assert output_rows[0]["priority"] == "high"


def test_a_clarification_from_the_model_is_not_stored_as_a_finding(service):
    """A question to the client is not a report finding, so nothing is persisted for it."""
    generated = {1: {"status": "needs_clarification", "clarification_question": "Which channels?"}}
    results, output_rows = assemble(service, [item(service)], generated=generated)

    assert results[0].status == "needs_clarification"
    assert results[0].clarification_question == "Which channels?"
    assert output_rows == []


def test_a_clarification_with_no_question_still_asks_something(service):
    generated = {1: {"status": "needs_clarification"}}
    results, _ = assemble(service, [item(service)], generated=generated)
    assert results[0].clarification_question == _default_clarification_question("en")


def test_a_capability_the_model_skipped_falls_back_to_generated_text(service):
    results, output_rows = assemble(service, [item(service)], fallbacks={1: "Fallback advice."})

    assert results[0].status == "ok"
    assert results[0].recommendation_text == "Fallback advice."
    assert output_rows[0]["generated_text"] == "Fallback advice."


def test_a_capability_with_neither_model_text_nor_fallback_still_gets_something(service):
    """The report cannot show a blank recommendation, so the last resort is the admin guideline."""
    results, output_rows = assemble(
        service,
        [item(service, admin_guideline="Appoint an owner for each channel.")],
    )
    assert results[0].status == "ok"
    assert results[0].recommendation_text
    assert len(output_rows) == 1


def test_an_already_gated_capability_keeps_its_question(service):
    gated_items = [item(service)]
    pre_gated, _ = service._gate_batch_items([item(service, evidence=[])], language="en")
    results, output_rows = service._assemble_batch_results(
        llm_items=gated_items,
        pre_gated=pre_gated,
        generated={1: {"status": "ok", "title": "Ignored"}},
        fallback_text_by_capability={},
        maturity_level_id_by_capability={},
        language="en",
    )
    assert results[0].status == "needs_clarification"
    assert output_rows == []


# ── the default question ────────────────────────────────────────────────────────────────────


def test_the_default_question_follows_the_report_language():
    assert _default_clarification_question("en") != _default_clarification_question("fr")
    assert _default_clarification_question("fr-FR") == _default_clarification_question("fr")
    assert _default_clarification_question("") == _default_clarification_question("en")
