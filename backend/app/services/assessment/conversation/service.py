from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_axis_memory_repository import AssessmentAxisMemoryRepository
from app.repositories.assessment_idempotency_repository import AssessmentIdempotencyRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.schemas.assessment import AnswerResponse, NextQuestionResponse
from app.services.assessment.conversation.answer_flow_service import build_answer_flow_service
from app.services.assessment.conversation.memory_sync_service import build_memory_sync_service
from app.services.assessment.conversation.question_flow_service import build_question_flow_service
from app.services.assessment.reporting.reporting_service import AssessmentReportingService
from app.services.assessment.scoring.scoring_service import AssessmentScoringService
from app.services.assessment.state.state_service import AssessmentStateService
from app.services.platform import idempotent_request
from app.services.llm.core.facade_service import ChatTurn, LLMService
from app.services.platform import AsyncUnitOfWork

class AssessmentConversationService:
    """Owns the CX assessment conversation loop and LLM orchestration."""

    def __init__(
        self,
        db: AsyncSession,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        answers: AssessmentAnswerRepository,
        axis_memory: AssessmentAxisMemoryRepository,
        idempotency: AssessmentIdempotencyRepository,
        llm_service: LLMService,
        uow: AsyncUnitOfWork,
        state_service: AssessmentStateService,
        scoring_service: AssessmentScoringService,
        reporting_service: AssessmentReportingService,
        settings: Settings,
    ) -> None:
        self.db = db
        self.assessments = assessments
        self.capabilities = capabilities
        self.answers = answers
        self.axis_memory = axis_memory
        self.idempotency = idempotency
        self.llm = llm_service
        self.uow = uow
        self.state = state_service
        self.scoring = scoring_service
        self.reporting = reporting_service
        self.settings = settings
        self.question_flow = build_question_flow_service(
            assessments=self.assessments,
            capabilities=self.capabilities,
            axis_memory=self.axis_memory,
            llm_service=self.llm,
            state_service=self.state,
            build_chat_history=self._build_chat_history,
            max_extra_questions_per_axis=lambda: self.max_extra_questions_per_axis,
            max_clarifications_per_focus=lambda: self.max_clarifications_per_focus,
            max_insufficient_evidence_retries=lambda: self.max_insufficient_evidence_retries,
        )
        self.memory_sync = build_memory_sync_service(
            axis_memory=self.axis_memory,
            llm_service=self.llm,
            next_question=self.question_flow._next_question,
        )
        self.answer_flow = build_answer_flow_service(
            assessments=self.assessments,
            capabilities=self.capabilities,
            answers=self.answers,
            llm_service=self.llm,
            state_service=self.state,
            scoring_service=self.scoring,
            reporting_service=self.reporting,
            question_flow_service=self.question_flow,
            max_extra_questions_per_axis=lambda: self.max_extra_questions_per_axis,
            max_clarifications_per_focus=lambda: self.max_clarifications_per_focus,
            max_insufficient_evidence_retries=lambda: self.max_insufficient_evidence_retries,
            schedule_axis_memory_update=self.memory_sync.schedule_axis_memory_update,
            schedule_next_question_prefetch=self.memory_sync.schedule_next_question_prefetch,
            cancel_scheduled_axis_memory_update=self.memory_sync.cancel_scheduled_axis_memory_update,
            cancel_scheduled_next_question_prefetch=self.memory_sync.cancel_scheduled_next_question_prefetch,
            finalize_parallel_llm_tasks=self.memory_sync.finalize_parallel_llm_tasks,
        )

    @property
    def max_extra_questions_per_axis(self) -> int:
        return self.settings.chat_max_extra_questions_per_axis

    @property
    def max_clarifications_per_focus(self) -> int:
        return self.settings.chat_max_clarifications_per_focus

    @property
    def max_insufficient_evidence_retries(self) -> int:
        return self.settings.chat_max_insufficient_evidence_retries

    async def next_question(self, assessment_id: int) -> NextQuestionResponse | None:
        from app.services.observability.llm_metrics import llm_context

        with llm_context(feature="assessment.question", kind="run", ref_kind="assessment", ref_id=assessment_id):
            async with self.uow:
                return await self.question_flow.next_question(assessment_id)

    @idempotent_request
    async def submit_answer(
        self,
        assessment_id: int,
        answer: str,
        idempotency_key: str | None = None,
        expected_axis: str | None = None,
        expected_version: int | None = None,
    ) -> AnswerResponse | None:
        from app.services.observability.llm_metrics import llm_context

        with llm_context(feature="assessment.answer", kind="run", ref_kind="assessment", ref_id=assessment_id):
            return await self.answer_flow.submit_answer(
                assessment_id=assessment_id,
                answer=answer,
                expected_axis=expected_axis,
                expected_version=expected_version,
            )


    async def _build_chat_history(self, assessment_id: int) -> list[ChatTurn]:
        history_messages = await self.answers.list_recent(
            assessment_id,
            limit=self.settings.llm_max_history_turns,
        )
        history: list[ChatTurn] = []
        for message in reversed(history_messages):
            history.append(ChatTurn(role="assistant", content=message.question))
            history.append(ChatTurn(role="user", content=message.answer))
        return history


def build_assessment_conversation_service(
    db: AsyncSession,
    llm_service: LLMService | None = None,
    scoring_service: AssessmentScoringService | None = None,
    reporting_service: AssessmentReportingService | None = None,
    settings: Settings | None = None,
) -> AssessmentConversationService:
    from app.services.assessment.factory import build_assessment_conversation_service as _build

    return _build(
        db=db,
        llm_service=llm_service,
        scoring_service=scoring_service,
        reporting_service=reporting_service,
        settings=settings,
    )
