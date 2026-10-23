"""The running summary the conversation keeps for each axis.

One row per (assessment, axis), overwritten as the axis progresses -- `upsert` rather than insert,
because there is only ever a current summary and no reason to keep the older ones.

The summary itself is written by the LLM memory service; this only stores it. What matters here is
that it is keyed per axis and not per assessment: the composer asks for the memory of the axis it
is currently working through, so a long Manage conversation does not crowd out what was learned
during Analyze.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment_axis_memory import AssessmentAxisMemory


class AssessmentAxisMemoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, assessment_id: int, axis: str) -> AssessmentAxisMemory | None:
        axis_value = (axis or "").strip()
        if not axis_value:
            return None
        result = await self.db.execute(
            select(AssessmentAxisMemory).where(
                AssessmentAxisMemory.assessment_id == assessment_id,
                AssessmentAxisMemory.axis == axis_value,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_assessment(self, assessment_id: int) -> list[AssessmentAxisMemory]:
        result = await self.db.execute(
            select(AssessmentAxisMemory)
            .where(AssessmentAxisMemory.assessment_id == assessment_id)
            .order_by(AssessmentAxisMemory.axis.asc())
        )
        return list(result.scalars().all())

    async def upsert(self, assessment_id: int, axis: str, summary: str) -> AssessmentAxisMemory:
        axis_value = (axis or "").strip()
        if not axis_value:
            raise ValueError("axis is required")
        summary_value = (summary or "").strip()
        if not summary_value:
            raise ValueError("summary is required")

        row = await self.get(assessment_id=assessment_id, axis=axis_value)
        now = datetime.now(timezone.utc)
        if row is None:
            row = AssessmentAxisMemory(
                assessment_id=assessment_id,
                axis=axis_value,
                summary=summary_value,
                updated_at=now,
            )
            self.db.add(row)
            await self.db.flush()
            return row

        row.summary = summary_value
        row.updated_at = now
        await self.db.flush()
        return row
