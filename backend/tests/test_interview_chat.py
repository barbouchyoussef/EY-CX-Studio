"""Interview-guide chatbot: shared engine with a LIVE-guide injection context source.

The distinguishing behaviour is freshness -- the guide is injected from what the caller passes,
so the assistant reasons over the consultant's current edits. Answer notes are available so it
can interpret responses. Chat persists per saved guide id.
"""

from __future__ import annotations

import asyncio

from app.schemas.interview_guide import InterviewGuideQuestionItem, InterviewGuideResponse
from app.services.assessment import interview_chat, interview_chat_store


def _guide(**over) -> InterviewGuideResponse:
    base = dict(
        id=7, company_name="Ooredoo", language="English",
        executive_summary="Client is mid-maturity on CX.",
        unanswered_areas=["data governance"],
        introduction_questions=[InterviewGuideQuestionItem(
            id="q1", question="How do you gather feedback?", rationale="baseline", follow_up="",
            isAnswered=True, answerNote="They use monthly NPS surveys only.",
        )],
        manage_questions=[], analyze_questions=[], improve_questions=[], closure_questions=[],
    )
    base.update(over)
    return InterviewGuideResponse(**base)


def test_guide_context_carries_answers_and_gaps():
    ctx = interview_chat.guide_to_context(_guide())
    assert "monthly NPS surveys only" in ctx  # answer notes available to interpret
    assert "data governance" in ctx  # unanswered areas
    assert "ANSWERED" in ctx and "RECORDED ANSWER/NOTES" in ctx  # unambiguous answer status


def test_a_note_without_the_answered_flag_still_counts_as_answered():
    # Guard the exact screenshot bug: a consultant typed a note; even if isAnswered lags, the
    # presence of a note must surface as an answer, never "not answered".
    g = _guide()
    g.introduction_questions[0].isAnswered = False  # flag not set, but a note exists
    ctx = interview_chat.guide_to_context(g)
    assert "STATUS: ANSWERED" in ctx
    assert "not yet answered" not in ctx


def test_chat_injects_the_current_guide_and_reflects_edits():
    captured = {}

    async def fake_llm(system, user):
        captured["user"] = user
        return "Relying only on monthly NPS misses transactional signal. [Interview Guide]"

    out = asyncio.run(interview_chat.chat_with_guide(_guide(), "interpret the feedback answer", llm_fn=fake_llm))
    assert "Current interview guide" in captured["user"]
    assert "monthly NPS surveys only" in captured["user"]
    assert out["sources"] == [interview_chat.GUIDE_SOURCE]

    # An edited/deleted question is reflected because the guide is passed in, not loaded:
    edited = _guide(introduction_questions=[])  # user deleted the only question
    async def fake2(system, user):
        captured["user2"] = user
        return "No questions remain in Introduction."
    asyncio.run(interview_chat.chat_with_guide(edited, "what's in intro?", llm_fn=fake2))
    assert "monthly NPS surveys only" not in captured["user2"]  # the deleted answer is gone


def test_orion_is_injected_only_when_the_question_asks_for_it():
    from types import SimpleNamespace

    captured = {}

    async def fake_llm(system, user):
        captured["user"] = user
        return "ok"

    orion = [SimpleNamespace(question="Rate your feedback maturity", answer="Advanced — structured NPS everywhere")]

    # Cross-reference question ("match", "self-assessment") -> Orion IS injected.
    asyncio.run(interview_chat.chat_with_guide(
        _guide(), "does the feedback answer match the self-assessment?",
        orion_trace_items=orion, llm_fn=fake_llm,
    ))
    assert "monthly NPS surveys only" in captured["user"]  # guide is always present
    assert "Advanced — structured NPS everywhere" in captured["user"]  # Orion pulled in
    assert "ORION self-assessment conversation" in captured["user"]

    # Ordinary interpretation question -> guide only, Orion stays out (keeps the turn lean).
    asyncio.run(interview_chat.chat_with_guide(
        _guide(), "interpret the feedback answer", orion_trace_items=orion, llm_fn=fake_llm,
    ))
    assert "monthly NPS surveys only" in captured["user"]  # guide present
    assert "Advanced — structured NPS everywhere" not in captured["user"]  # Orion NOT injected


def test_chat_persists_per_guide(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_chat_store, "_DIR", str(tmp_path / "ichat"))
    assert interview_chat_store.load_chat(7) == []
    interview_chat_store.append_chat(7, [
        {"id": "1", "role": "user", "text": "interpret feedback"},
        {"id": "2", "role": "assistant", "text": "Only NPS.", "sources": ["Interview Guide"]},
    ])
    interview_chat_store.append_chat(7, [{"id": "3", "role": "user", "text": "and next?"}])
    loaded = interview_chat_store.load_chat(7)
    assert [m["id"] for m in loaded] == ["1", "2", "3"]
    interview_chat_store.delete_chat(7)
    assert interview_chat_store.load_chat(7) == []
