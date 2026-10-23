"""Cross-reference briefing: the Orion self-assessment vs. the follow-up interview.

Light, one-shot analysis (not a chat). It compares what the client claimed during the automated
Orion maturity self-assessment against what the consultant recorded in the interview, surfacing a
few insights and any inconsistencies. Only meaningful when the guide was generated from an
assessment that actually has an Orion conversation.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.core.config import get_settings
from app.core.text_normalization import repair_encoding
from app.schemas.interview_guide import InterviewGuideResponse
from app.services.llm.core.gateway import build_mistral_gateway

logger = logging.getLogger(__name__)

INSIGHTS_SYSTEM_PROMPT = """You are a customer-experience consultant writing up what an interview
revealed, for the colleague who will use it.

You have TWO sources about the same client:
1) SELF-ASSESSMENT (Orion): what the client said when they scored themselves, before the interview.
2) FOLLOW-UP INTERVIEW: the questions the consultant asked and the answers recorded.

The point of this write-up is what the two together show that neither shows alone. A client who
scores themselves rarely describes their own gaps accurately, so where the interview and the
self-assessment disagree is usually the most useful thing on the page.

WHO YOU ARE WRITING FOR
Another consultant. They want the substance and they will not read around jargon. They will skim
this before a meeting.

WRITE LIKE THIS
- Plain, direct language. Short sentences, one idea each.
- No consulting filler. Never "leverage", "synergies", "holistic", "strategic imperative",
  "going forward", "at a high level". Say the thing.
- Quote the person when their own words make the point better than a summary would. Keep quotes
  short and mark them clearly.
- Ground everything in the material. Never invent an answer the client did not give.
- Say each point once. No preamble, no closing offer of further help.
- Write in the guide's language.

USE THESE SECTIONS, with markdown `##` headings, in this order:

## What this interview covered
Two or three sentences: who was interviewed and their role, the ground the conversation covered,
and how complete it is (roughly how many questions were answered). If coverage is thin, say so
here plainly rather than implying more than you have.

## What the interview confirms
Where the interview backs up what the client claimed when they scored themselves. Name the topic
and both sides briefly. This matters because a confirmed weakness is one the client already
accepts, which makes it far easier to act on.

## Where the two disagree
The most valuable section. Where the interview CONTRADICTS the self-assessment, or where the
detail is clearly worse than the score suggested. Name both sides: what was claimed, what the
interview actually says. If there is genuinely no disagreement, write exactly
"Nothing contradicts the self-assessment." and never invent one to fill the space.

## What we learned that the self-assessment missed
What the interview surfaced that the scoring exercise never asked about or could not reach. This
is where a real conversation earns its keep -- named systems, specific incidents, who actually
owns what, and what people work around.

## What to ask next
Two to four threads still open, each one line: the question, and why it matters. Practical
enough that a colleague could pick it up in the next conversation.

If there is no self-assessment conversation to compare against, say so in one line at the top,
skip the two comparison sections, and write the rest from the interview alone."""


def _orion_history(trace_items: list) -> str:
    lines: list[str] = []
    for item in trace_items:
        q = repair_encoding(str(getattr(item, "question", "") or "")).strip()
        a = repair_encoding(str(getattr(item, "answer", "") or "")).strip()
        if q:
            lines.append(f"Orion: {q}")
        if a:
            lines.append(f"Client: {a}")
    return "\n".join(lines)


def _interview_answers(guide: InterviewGuideResponse) -> tuple[str, int, int]:
    """Return (serialized answered Q&A, answered_count, total_count)."""
    sections = (
        guide.introduction_questions, guide.manage_questions, guide.analyze_questions,
        guide.improve_questions, guide.closure_questions,
    )
    lines: list[str] = []
    answered = 0
    total = 0
    for items in sections:
        for q in items:
            total += 1
            note = (q.answerNote or "").strip()
            if note:
                answered += 1
                lines.append(f"- Q: {q.question}\n  A: {note}")
    body = "\n".join(lines) if lines else "(No interview answers recorded yet.)"
    return body, answered, total


def _default_llm() -> Callable[[str, str], Awaitable[str]]:
    gateway = build_mistral_gateway(get_settings())

    async def _llm(system_prompt: str, user_prompt: str) -> str:
        return await gateway.chat_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )

    return _llm


async def generate_insights(
    guide: InterviewGuideResponse,
    trace_items: list,
    *,
    llm_fn: Callable[[str, str], Awaitable[str]] | None = None,
) -> str:
    """Produce the cross-reference briefing markdown."""
    orion = _orion_history(trace_items)
    interview, answered, total = _interview_answers(guide)

    user_prompt = (
        f"CLIENT: {guide.company_name} (language: {guide.language})\n\n"
        f"=== SELF-ASSESSMENT (Orion) CONVERSATION ===\n{orion or '(none)'}\n\n"
        f"=== FOLLOW-UP INTERVIEW — recorded answers ({answered} of {total} questions answered) ===\n"
        f"{interview}\n\n"
        "Write the cross-reference briefing now."
    )
    llm = llm_fn or _default_llm()
    from app.services.observability.llm_metrics import llm_context

    with llm_context(feature="interview.insights", kind="run"):
        text = await llm(INSIGHTS_SYSTEM_PROMPT, user_prompt)
    return repair_encoding(text)
