from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.axis import Axis
from app.domain.constants import (
    ASSESSMENT_STATUS_COMPLETED,
    ASSESSMENT_STATUS_IN_PROGRESS,
    AXES_ORDER,
    normalize_axis_name,
)
from app.domain.errors import AssessmentStateConflictError
from app.repositories.capability_repository import CapabilityRepository
from app.schemas.assessment import NextQuestionResponse

import logging

logger = logging.getLogger(__name__)


class AssessmentStateService:
    """Owns assessment state transitions and optimistic concurrency checks."""

    MAX_QUESTIONS_PER_AXIS = 4

    def __init__(self, db: AsyncSession, capabilities: CapabilityRepository) -> None:
        self.db = db
        self.capabilities = capabilities

    def assert_expected_state(
        self,
        assessment: Any,
        expected_axis: str | None,
        expected_version: int | None,
    ) -> None:
        if expected_axis is None and expected_version is None:
            return

        current_axis = self.current_axis_name(assessment)
        if expected_axis is not None and expected_axis != current_axis:
            raise AssessmentStateConflictError(
                f"State conflict: expected_axis={expected_axis!r}, current_axis={current_axis!r}"
            )

        if expected_version is not None and int(expected_version) != int(assessment.state_version):
            raise AssessmentStateConflictError(
                f"State conflict: expected_version={expected_version}, current_version={assessment.state_version}"
            )

    def current_axis_name(self, assessment: Any) -> str:
        raw_axis = assessment.current_axis.name if assessment.current_axis is not None else AXES_ORDER[0]
        return normalize_axis_name(raw_axis) or AXES_ORDER[0]

    def response_axis(self, assessment: Any) -> str | None:
        if assessment.status != ASSESSMENT_STATUS_IN_PROGRESS:
            return None
        return self.current_axis_name(assessment)

    def bump_version(self, assessment: Any) -> None:
        assessment.state_version = int(assessment.state_version) + 1

    async def ensure_assessment_still_active(
        self,
        assessment_id: int,
        assessment: Any,
        max_extra_questions_per_axis: int,
    ) -> NextQuestionResponse | None:
        await self.advance_if_axis_complete(
            assessment_id=assessment_id,
            assessment=assessment,
            max_extra_questions_per_axis=max_extra_questions_per_axis,
        )
        if assessment.status != ASSESSMENT_STATUS_IN_PROGRESS:
            return NextQuestionResponse(status=assessment.status, message="Assessment completed")
        return None

    async def advance_if_axis_complete(
        self,
        assessment_id: int,
        assessment: Any,
        max_extra_questions_per_axis: int,
    ) -> None:
        if assessment.status != ASSESSMENT_STATUS_IN_PROGRESS:
            return

        axis = self.current_axis_name(assessment)
        axis_criteria = await self.capabilities.list_for_axis(assessment_id, axis)
        axis_completed_by_score = bool(axis_criteria and all(c["covered"] for c in axis_criteria))
        uncovered_labels = [str(c.get("label") or "") for c in axis_criteria if not c.get("covered")]
        target_questions = min(
            self.target_questions_for_axis(axis_criteria),
            self.MAX_QUESTIONS_PER_AXIS
            + min(int(assessment.current_axis_low_quality_count or 0), max_extra_questions_per_axis),
        )
        axis_completed_by_budget = bool(
            axis_criteria
            and int(assessment.current_axis_question_count or 0) >= target_questions
        )
        if not axis_completed_by_score and not axis_completed_by_budget:
            return

        completion_reason = "score_coverage" if axis_completed_by_score else "question_budget"
        logger.info(
            "Assessment axis completed",
            extra={
                "assessment_id": assessment_id,
                "axis": axis,
                "completion_reason": completion_reason,
                "axis_question_count": int(assessment.current_axis_question_count or 0),
                "target_questions": target_questions,
                "low_quality_count": int(assessment.current_axis_low_quality_count or 0),
                "covered_count": len(axis_criteria) - len(uncovered_labels),
                "total_capabilities": len(axis_criteria),
                "uncovered_capabilities": uncovered_labels,
            },
        )

        ordered_axes_result = await self.db.execute(select(Axis).order_by(Axis.sort_order.asc()))
        ordered_axes = list(ordered_axes_result.scalars().all())
        names = [(normalize_axis_name(a.name) or a.name) for a in ordered_axes]
        try:
            axis_index = names.index(axis)
        except ValueError:
            axis_index = -1
        next_axis = ordered_axes[axis_index + 1] if axis_index + 1 < len(ordered_axes) else None

        assessment.pending_followup_hint = None
        assessment.pending_question = None
        assessment.pending_options = None
        assessment.pending_focus_capability_id = None
        assessment.clarification_count = 0
        if next_axis is None:
            assessment.status = ASSESSMENT_STATUS_COMPLETED
            assessment.current_axis_id = None
            assessment.current_axis = None
            assessment.current_axis_question_count = 0
            assessment.current_axis_low_quality_count = 0
            assessment.conversation_stage = "completed"
            logger.info(
                "Assessment completed",
                extra={
                    "assessment_id": assessment_id,
                    "final_axis": axis,
                    "completion_reason": completion_reason,
                },
            )
        else:
            assessment.current_axis_id = next_axis.id
            assessment.current_axis = next_axis
            assessment.current_axis_question_count = 0
            assessment.current_axis_low_quality_count = 0
            assessment.conversation_stage = "intro"
            logger.info(
                "Advancing assessment axis",
                extra={
                    "assessment_id": assessment_id,
                    "previous_axis": axis,
                    "next_axis": normalize_axis_name(next_axis.name) or next_axis.name,
                    "completion_reason": completion_reason,
                },
            )

    def target_questions_for_axis(self, axis_capabilities: list[dict]) -> int:
        capability_count = len(axis_capabilities or [])
        if capability_count <= 3:
            return 3
        if capability_count <= 5:
            return 4
        return 5

    async def get_first_axis(self) -> Axis | None:
        result = await self.db.execute(select(Axis).order_by(Axis.sort_order.asc()).limit(1))
        return result.scalar_one_or_none()
