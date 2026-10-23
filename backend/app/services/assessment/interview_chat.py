"""Interview-guide chatbot: shared agentic engine with a live-guide injection context source.

The distinguishing requirement here is *freshness*: the consultant edits, adds, and deletes
questions and records answers live in the browser. So the guide is injected from what the client
SENDS on each turn -- not loaded from disk -- which means the assistant always reasons over the
guide exactly as it stands right now, edits and all. It interprets answers, flags gaps, and
suggests follow-ups. The plan → gather → answer loop and <ModuleChat> front-end are shared.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.core.config import get_settings
from app.core.text_normalization import repair_encoding
from app.schemas.interview_guide import InterviewGuideQuestionItem, InterviewGuideResponse
from app.services.llm.core.gateway import build_mistral_gateway
from app.services.rag import engine

logger = logging.getLogger(__name__)

GUIDE_SOURCE = "Interview Guide"

INTERVIEW_CHAT_SYSTEM_PROMPT = """You are the EY CX Interview Assistant — a senior customer-experience
consultant helping a colleague run and interpret a client interview.

You are given the CURRENT interview guide: its sections, each question with its rationale and
follow-up, whether it has been answered, and the consultant's answer notes. This reflects the
guide AS IT STANDS RIGHT NOW — including any questions the consultant has just edited, added, or
deleted.

You may ALSO be given the client's prior ORION SELF-ASSESSMENT conversation — what they claimed
during the automated CX maturity self-assessment that this guide was generated from. When it is
present, use it: compare interview answers against what they claimed earlier, and flag mismatches.

How to help:
- Interpret answers: from a question's answer notes, explain what the response reveals about the
  client's CX maturity, risks, or gaps; flag contradictions or anything worth probing further.
- Cross-reference with the Orion self-assessment when relevant ("does this match what they said
  earlier?", "what did they claim about X in the assessment?").
- Suggest follow-up questions and what to ask next, grounded in what has and hasn't been answered.
- Answer questions about the guide's content, coverage, and the still-unanswered areas.
- Greetings/small talk → reply briefly; no analysis needed.
- Base everything strictly on the guide provided. If a question wasn't asked or answered, say so —
  never invent a client response.
- Cite the guide as [Interview Guide]; answer in the guide's language.

STYLE — this matters:
- Be CONCISE. Lead with the answer in the first sentence; cut throat-clearing and preamble.
- Say each thing ONCE. No repetition, no restating the question back, no summarizing what you
  just said.
- Prefer a few tight sentences or 2-4 short bullets over long prose. No section headers for a
  short answer.
- Do NOT end with filler like "Would you like to proceed?" or "Let me know if..." — stop when the
  point is made. Only ask a follow-up question if it genuinely needs the user's input.
"""


def _section(title: str, items: list[InterviewGuideQuestionItem]) -> str:
    if not items:
        return ""
    lines = [f"SECTION — {title}:"]
    for i, q in enumerate(items, 1):
        note = (q.answerNote or "").strip()
        answered = bool(q.isAnswered) or bool(note)
        block = f"{i}. QUESTION: {q.question}"
        if q.rationale:
            block += f"\n   Rationale: {q.rationale}"
        if q.follow_up:
            block += f"\n   Follow-up: {q.follow_up}"
        if answered and note:
            block += f'\n   STATUS: ANSWERED. CONSULTANT\'S RECORDED ANSWER/NOTES: "{note}"'
        elif answered:
            block += "\n   STATUS: marked answered, but no answer notes were recorded."
        else:
            block += "\n   STATUS: not yet answered — no answer recorded."
        lines.append(block)
    return "\n".join(lines)


def guide_to_context(guide: InterviewGuideResponse) -> str:
    """Serialize the current guide (all sections, questions, answer notes) for injection."""
    parts: list[str] = [f"COMPANY: {guide.company_name} | Language: {guide.language}"]
    if guide.executive_summary:
        parts.append(f"EXECUTIVE SUMMARY:\n{guide.executive_summary}")
    if guide.unanswered_areas:
        parts.append("UNANSWERED AREAS: " + "; ".join(guide.unanswered_areas))
    for title, items in (
        ("Introduction", guide.introduction_questions),
        ("Manage", guide.manage_questions),
        ("Analyze", guide.analyze_questions),
        ("Improve", guide.improve_questions),
        ("Closure", guide.closure_questions),
    ):
        section = _section(title, items)
        if section:
            parts.append(section)
    return "\n\n".join(parts)


def _orion_history_text(trace_items: list) -> str:
    lines: list[str] = []
    for item in trace_items or []:
        q = repair_encoding(str(getattr(item, "question", "") or "")).strip()
        a = repair_encoding(str(getattr(item, "answer", "") or "")).strip()
        if q:
            lines.append(f"Orion: {q}")
        if a:
            lines.append(f"Client: {a}")
    return "\n".join(lines)


# Terms (EN + FR) that signal the question wants the prior self-assessment, not just the guide.
# The Orion transcript can be long, so it is only injected when the question actually calls for it
# -- ordinary "interpret this answer" questions stay lean on the guide alone.
_ORION_TRIGGERS = (
    "orion", "self-assessment", "self assessment", "assessment", "earlier", "before",
    "claimed", "claim", "consistent", "inconsistent", "contradict", "match", "align",
    "auto-évaluation", "auto évaluation", "évaluation", "avant", "prétend", "affirmé",
    "cohérent", "incohérent", "contredit", "correspond", "aligne",
)


def make_guide_context_source(
    guide: InterviewGuideResponse,
    orion_trace_items: list | None = None,
) -> engine.ContextSource:
    """A context source that always injects the current interview guide, and additionally injects
    the client's prior Orion self-assessment ONLY when the question is about cross-referencing it
    (keeps ordinary interview questions lean; the dedicated cross-check lives in the Insights button)."""
    guide_ctx = f"Current interview guide:\n\n{guide_to_context(guide)}"
    orion = _orion_history_text(orion_trace_items) if orion_trace_items else ""

    async def _source(query: str, planned_queries: list[str]) -> tuple[str, list[str]]:
        parts = [guide_ctx]
        if orion:
            haystack = " ".join([query, *(planned_queries or [])]).lower()
            if any(t in haystack for t in _ORION_TRIGGERS):
                parts.append(
                    "Prior ORION self-assessment conversation (what the client claimed earlier):\n" + orion
                )
        return "\n\n".join(parts), [GUIDE_SOURCE]

    return _source


def _default_chat_llm() -> Callable[[str, str], Awaitable[str]]:
    gateway = build_mistral_gateway(get_settings())

    async def _llm(system_prompt: str, user_prompt: str) -> str:
        return await gateway.chat_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )

    return _llm


async def chat_with_guide(
    guide: InterviewGuideResponse,
    query: str,
    *,
    orion_trace_items: list | None = None,
    history: list[dict] | None = None,
    llm_fn: Callable[[str, str], Awaitable[str]] | None = None,
) -> dict:
    """Answer a question about the CURRENT interview guide via the shared agentic loop.

    When ``orion_trace_items`` is provided, the client's prior self-assessment conversation is
    injected too, so the assistant can cross-reference interview answers against it."""
    llm = llm_fn or _default_chat_llm()
    from app.services.observability.llm_metrics import llm_context

    with llm_context(feature="interview.chat", kind="assistant"):
        result = await engine.agentic_answer(
            query,
            llm,
            answer_system_prompt=INTERVIEW_CHAT_SYSTEM_PROMPT,
            context_source=make_guide_context_source(guide, orion_trace_items),
            history=history,
        )
    return {
        "answer": repair_encoding(result["answer"]),
        "sources": list(dict.fromkeys(repair_encoding(s) for s in result["sources"])),
        "used_context": result["used_context"],
    }
