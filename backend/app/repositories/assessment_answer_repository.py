"""Every answer a client gave, in the order they gave it.

Answers are append-only. Re-scoring a capability adds a new row rather than editing the old one,
so the transcript stays a record of the conversation as it actually happened -- which is what the
report quotes from and what an audit of a score follows back.

`list_recent` feeds the model its short-term context; `list_trace` is the diagnostic view that
joins each answer to what it was scored against, for working out why a capability landed where it
did.
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants import normalize_axis_name
from app.db.models.assessment_answer import AssessmentAnswer
from app.db.models.capability import Capability
from app.db.models.axis import Axis
from app.db.models.assessment_score import AssessmentScore
from app.db.models.capability_quick_win_template import CapabilityQuickWinTemplate


class AssessmentAnswerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, assessment_id: int, question: str, answer: str, capability_id: int | None = None
    ) -> AssessmentAnswer:
        row = AssessmentAnswer(assessment_id=assessment_id, capability_id=capability_id, question=question, answer=answer)
        self.db.add(row)
        await self.db.flush()
        return row

    async def list_recent(self, assessment_id: int, limit: int = 20) -> list[AssessmentAnswer]:
        result = await self.db.execute(
            select(AssessmentAnswer)
            .where(AssessmentAnswer.assessment_id == assessment_id)
            .order_by(desc(AssessmentAnswer.id))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_for_assessment(self, assessment_id: int, limit: int = 200, offset: int = 0) -> list[AssessmentAnswer]:
        result = await self.db.execute(
            select(AssessmentAnswer)
            .where(AssessmentAnswer.assessment_id == assessment_id)
            .order_by(AssessmentAnswer.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_trace(self, assessment_id: int, limit: int = 500, offset: int = 0) -> list[dict]:
        result = await self.db.execute(self._trace_statement(assessment_id, limit, offset))
        rows = result.all()
        return [
            {
                "capability_id": int(capability_id) if capability_id is not None else None,
                "capability_code": capability_code,
                "axis": normalize_axis_name(str(axis_name)) if axis_name is not None else None,
                "question": question,
                "answer": answer,
                "created_at": created_at,
                "maturity_level_id": int(maturity_level_id) if maturity_level_id is not None else None,
                "confidence": float(confidence) if confidence is not None else None,
                "justification": justification,
                "recommendation_guideline": recommendation_guideline,
                "priority_hint": priority_hint,
            }
            for (
                capability_id,
                capability_code,
                axis_name,
                question,
                answer,
                created_at,
                maturity_level_id,
                confidence,
                justification,
                recommendation_guideline,
                priority_hint,
            ) in rows
        ]

    def _trace_statement(
        self,
        assessment_id: int,
        limit: int,
        offset: int,
    ):
        statement = (
            select(
                AssessmentAnswer.capability_id,
                Capability.code,
                Axis.name,
                AssessmentAnswer.question,
                AssessmentAnswer.answer,
                AssessmentAnswer.created_at,
                AssessmentScore.maturity_level_id,
                AssessmentScore.confidence,
                AssessmentScore.justification,
                CapabilityQuickWinTemplate.quick_win_guideline,
                CapabilityQuickWinTemplate.timeline_hint,
            )
            .outerjoin(Capability, Capability.id == AssessmentAnswer.capability_id)
            .outerjoin(Axis, Axis.id == Capability.axis_id)
            .outerjoin(
                AssessmentScore,
                (AssessmentScore.assessment_id == AssessmentAnswer.assessment_id)
                & (AssessmentScore.capability_id == AssessmentAnswer.capability_id),
            )
            .outerjoin(
                CapabilityQuickWinTemplate,
                (CapabilityQuickWinTemplate.capability_id == AssessmentAnswer.capability_id)
                & (CapabilityQuickWinTemplate.maturity_level_id == AssessmentScore.maturity_level_id)
                & (CapabilityQuickWinTemplate.active.is_(True)),
            )
        )
        return (
            statement.where(AssessmentAnswer.assessment_id == assessment_id)
            .order_by(AssessmentAnswer.id.asc())
            .offset(offset)
            .limit(limit)
        )
