"""What a project's interview report is built from: its interviews, and the Orion assessments
behind them.

Kept apart from the report itself so the gathering can be tested against a database and the
report logic can be tested against plain dictionaries.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_normalization import repair_encoding
from app.db.models.assessment_answer import AssessmentAnswer
from app.db.models.assessment_score import AssessmentScore
from app.db.models.axis import Axis
from app.db.models.capability import Capability
from app.db.models.interview_guide import InterviewGuide
from app.db.models.maturity_level import MaturityLevel
from app.db.models.project import ProjectArtifact

logger = logging.getLogger(__name__)


_QUESTION_KEYS = (
    "introduction_questions", "manage_questions", "analyze_questions",
    "improve_questions", "closure_questions",
)


def _answers(payload: dict) -> tuple[list[dict], int, int]:
    """Every answered question in a guide, with the count answered out of the total.

    The total counts questions asked, not questions answered, because an interview where 6 of 21
    questions came back is a materially different piece of evidence from one where 21 did -- and
    the report has to be able to say so.
    """
    rows: list[dict] = []
    answered = total = 0
    for key in _QUESTION_KEYS:
        for q in (payload.get(key) or []):
            if not isinstance(q, dict):
                continue
            total += 1
            note = repair_encoding(str(q.get("answerNote") or "")).strip()
            if note:
                answered += 1
                rows.append({
                    "section": key.replace("_questions", ""),
                    "question": repair_encoding(str(q.get("question") or "")).strip(),
                    "answer": note,
                })
    return rows, answered, total


async def _guide_ids(db: AsyncSession, project_id: int) -> list[int]:
    """The interview guides attached to the project, oldest first.

    `ref_id` is a string column shared by every artifact kind, so a non-numeric value is possible
    (desk-research sessions use hex ids under the same column) and is skipped rather than raising.
    """
    rows = await db.execute(
        select(ProjectArtifact.ref_id)
        .where(ProjectArtifact.project_id == project_id,
               ProjectArtifact.kind == "interview_guide")
        .order_by(ProjectArtifact.id)
    )
    ids: list[int] = []
    for (ref,) in rows.all():
        try:
            ids.append(int(str(ref)))
        except (TypeError, ValueError):
            logger.warning("Skipping non-numeric interview_guide ref %r on project %s",
                           ref, project_id)
    return ids


async def _scores(db: AsyncSession, assessment_id: int) -> list[dict]:
    """The capability levels this assessment produced, with the axis and capability names.

    Only rows that actually got a level are returned: an unscored capability is not evidence of
    anything, and showing it as a blank row invites it to be read as a zero.
    """
    rows = await db.execute(
        select(Axis.name, Capability.name, MaturityLevel.level_number,
               MaturityLevel.label, AssessmentScore.justification)
        .join(Capability, Capability.id == AssessmentScore.capability_id)
        .join(Axis, Axis.id == Capability.axis_id)
        .join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id)
        .where(AssessmentScore.assessment_id == assessment_id)
        .order_by(Axis.sort_order, Capability.sort_order)
    )
    return [
        {"axis": axis, "capability": cap, "level": level, "level_label": label,
         "justification": repair_encoding(str(justification or "")).strip()}
        for axis, cap, level, label, justification in rows.all()
    ]


async def _conversation(db: AsyncSession, assessment_id: int) -> list[dict]:
    rows = await db.execute(
        select(AssessmentAnswer.question, AssessmentAnswer.answer)
        .where(AssessmentAnswer.assessment_id == assessment_id)
        .order_by(AssessmentAnswer.id)
    )
    return [
        {"question": repair_encoding(str(q or "")).strip(),
         "answer": repair_encoding(str(a or "")).strip()}
        for q, a in rows.all()
    ]


async def gather(db: AsyncSession, project_id: int) -> tuple[list[dict], list[dict], str]:
    """Return (interviews, assessments, company) for a project.

    Assessments are DEDUPLICATED: interviews in a project are usually generated from the same
    Orion assessment, and counting it twice would both inflate the "self-assessments" figure and
    feed the model the same conversation two times over.
    """
    interviews: list[dict] = []
    assessment_ids: list[int] = []

    for guide_id in await _guide_ids(db, project_id):
        row = await db.get(InterviewGuide, guide_id)
        if row is None:      # detached or deleted since it was attached
            continue
        payload = dict(row.payload or {})
        answers, answered, total = _answers(payload)
        interviews.append({
            "id": row.id,
            "company_name": row.company_name,
            "profile": row.profile,
            "language": row.language,
            "assessment_id": row.assessment_id,
            "answers": answers,
            "answered": answered,
            "total": total,
            "insights_markdown": (row.insights or {}).get("markdown") if row.insights else None,
            "cx_findings": list(row.cx_findings or []),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
        if row.assessment_id is not None and row.assessment_id not in assessment_ids:
            assessment_ids.append(row.assessment_id)

    assessments = [
        {"id": aid, "conversation": await _conversation(db, aid), "scores": await _scores(db, aid)}
        for aid in assessment_ids
    ]

    company = next((iv["company_name"] for iv in interviews if iv["company_name"]), "This client")
    return interviews, assessments, company
