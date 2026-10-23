from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.schemas.recommendations import (
    AssessmentTraceItem,
    AssessmentTraceResponse,
)


class AssessmentTraceService:
    """Owns assessment conversation trace retrieval."""

    def __init__(
        self,
        assessments: AssessmentRepository,
        answers: AssessmentAnswerRepository,
    ) -> None:
        self.assessments = assessments
        self.answers = answers

    async def get_trace(self, assessment_id: int, limit: int = 500, offset: int = 0) -> AssessmentTraceResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.answers.list_trace(assessment_id=assessment_id, limit=limit, offset=offset)
        items = [AssessmentTraceItem(**row) for row in rows]
        return AssessmentTraceResponse(assessment_id=assessment_id, items=items)


