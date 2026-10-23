"""Extract issue-log findings from a stakeholder interview.

Unlike social (structured analytics) and desk research (documents), the interview material is free
prose -- the consultant's answer notes plus the cross-reference **insights** briefing. So findings
need a light LLM pass. Emits the shared Finding shape (see app/services/cx_findings.py)."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from app.core.config import get_settings
from app.services.cx_findings import CX_DIMENSIONS, finding
from app.services.llm.core.gateway import build_mistral_gateway
from app.services.llm.utils import extract_json

logger = logging.getLogger(__name__)

_DIMS = "\n".join(f"- {d}" for d in CX_DIMENSIONS)

FINDINGS_SYSTEM_PROMPT = f"""You are an EY CX analyst turning a stakeholder-interview into structured issue-log findings.

You are given: (1) the cross-reference INSIGHTS briefing (what the interview revealed vs. the client's
prior self-assessment), and (2) the consultant's recorded interview answers. Extract the distinct,
material findings and map EACH to exactly ONE CX capability dimension (copy the label exactly):
{_DIMS}

For each finding output an object with:
- "dimension": one of the labels above.
- "type": "friction" | "strength" | "gap" | "opportunity" | "conflict"  (use "conflict" when the
  interview contradicts what the client claimed in the self-assessment).
- "severity": "low" | "medium" | "high" | "critical" for friction/gap; else null.
- "title": short label (<= 10 words).
- "description": one clear sentence -- the finding and its implication.
- "evidence": the interview observation / paraphrased quote it rests on.
- "source_document": "Stakeholder interview".

Ground every finding strictly in the material provided; never invent a client statement. If the
interview has little content, return few findings rather than padding.

Output ONLY valid JSON, no markdown/prose/code fences:
{{"findings": [ {{"dimension": "...", "type": "...", "severity": "...", "title": "...", "description": "...", "evidence": "...", "source_document": "Stakeholder interview"}} ]}}
"""

_SECTION_KEYS = (
    "introduction_questions", "manage_questions", "analyze_questions",
    "improve_questions", "closure_questions",
)


def _answered_qa(guide: dict) -> str:
    """Serialize the answered questions (question + the consultant's note) from a guide payload."""
    lines: list[str] = []
    for key in _SECTION_KEYS:
        for q in guide.get(key, []) or []:
            note = (q.get("answerNote") or "").strip()
            if note:
                lines.append(f"- Q: {q.get('question','')}\n  A: {note}")
    return "\n".join(lines)


async def extract_interview_findings(
    guide: dict,
    insights_markdown: str | None,
    language: str = "English",
    llm_fn: Callable[[list], Awaitable[str]] | None = None,
) -> list[dict]:
    """Map an interview's insights + answer notes onto CX Findings for the issue log."""
    qa = _answered_qa(guide)
    insights = (insights_markdown or "").strip()
    if not qa and not insights:
        return []  # nothing recorded yet

    user = (
        f"Language: {language}\nClient: {guide.get('company_name','')}\n\n"
        f"=== CROSS-REFERENCE INSIGHTS ===\n{insights or '(none generated)'}\n\n"
        f"=== INTERVIEW ANSWERS ===\n{qa or '(no answers recorded)'}\n\n"
        "Output the interview findings JSON now."
    )
    messages = [{"role": "system", "content": FINDINGS_SYSTEM_PROMPT}, {"role": "user", "content": user}]

    llm = llm_fn or (lambda m: build_mistral_gateway(get_settings()).chat_messages(m))
    from app.services.observability.llm_metrics import llm_context

    with llm_context(feature="interview.findings", kind="run"):
        raw = await llm(messages)

    try:
        data = extract_json(raw)
        items = data.get("findings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception:
        logger.warning("interview findings: JSON parse failed")
        return []

    out: list[dict] = []
    for f in items:
        if not isinstance(f, dict) or not str(f.get("description", "")).strip():
            continue
        out.append(finding(
            dimension=str(f.get("dimension", "")).strip(),
            type=str(f.get("type", "")).strip().lower(),
            severity=str(f.get("severity", "") or "").strip().lower() or None,
            title=str(f.get("title", "")).strip(),
            description=str(f.get("description", "")).strip(),
            evidence=str(f.get("evidence", "")).strip(),
            source_document="Stakeholder interview",
        ))
    return out
