"""Cross-reference insights: Orion self-assessment vs. interview answers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.schemas.interview_guide import InterviewGuideQuestionItem, InterviewGuideResponse
from app.services.assessment import interview_insights


def _guide():
    return InterviewGuideResponse(
        id=5, assessment_id=9, company_name="telecom", language="English",
        executive_summary="", unanswered_areas=[],
        introduction_questions=[
            InterviewGuideQuestionItem(id="1", question="How mature is your feedback loop?", rationale="", follow_up="",
                                       isAnswered=True, answerNote="We barely collect feedback, mostly ad hoc."),
            InterviewGuideQuestionItem(id="2", question="Do you segment customers?", rationale="", follow_up=""),
        ],
        manage_questions=[], analyze_questions=[], improve_questions=[], closure_questions=[],
    )


def test_interview_answers_counts_only_answered():
    body, answered, total = interview_insights._interview_answers(_guide())
    assert answered == 1 and total == 2
    assert "barely collect feedback" in body


def test_insights_combine_both_sources_and_detect_inconsistency():
    trace = [SimpleNamespace(question="Rate your feedback maturity", answer="Advanced — structured NPS everywhere")]
    captured = {}

    async def fake_llm(system, user):
        captured["user"] = user
        return "**Inconsistencies**\n- Self-assessment claimed advanced NPS; interview says feedback is ad hoc."

    out = asyncio.run(interview_insights.generate_insights(_guide(), trace, llm_fn=fake_llm))
    # Both sources reached the model, with the answered-count signal.
    assert "Advanced — structured NPS everywhere" in captured["user"]  # Orion side
    assert "barely collect feedback" in captured["user"]  # interview side
    assert "1 of 2 questions answered" in captured["user"]
    assert "ad hoc" in out
