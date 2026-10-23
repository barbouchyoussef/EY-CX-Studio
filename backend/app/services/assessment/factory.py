from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_axis_memory_repository import AssessmentAxisMemoryRepository
from app.repositories.assessment_idempotency_repository import AssessmentIdempotencyRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.company_size_repository import CompanySizeRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.sector_repository import SectorRepository
from app.services.assessment.conversation.service import AssessmentConversationService
from app.services.assessment.reporting.reporting_service import (
    AssessmentReportingService,
    build_assessment_reporting_service,
)
from app.services.assessment.scoring.scoring_service import (
    AssessmentScoringService,
    build_assessment_scoring_service,
)
from app.services.assessment.lifecycle_service import AssessmentService
from app.services.assessment.state.state_service import AssessmentStateService
from app.services.llm.core.facade_service import LLMService, build_llm_service
from app.services.platform import AsyncUnitOfWork


def build_assessment_conversation_service(
    db: AsyncSession,
    llm_service: LLMService | None = None,
    scoring_service: AssessmentScoringService | None = None,
    reporting_service: AssessmentReportingService | None = None,
    settings: Settings | None = None,
) -> AssessmentConversationService:
    resolved_settings = settings or get_settings()
    assessments = AssessmentRepository(db)
    capabilities = CapabilityRepository(db)
    answers = AssessmentAnswerRepository(db)
    axis_memory = AssessmentAxisMemoryRepository(db)
    idempotency = AssessmentIdempotencyRepository(db)
    llm = llm_service or build_llm_service(settings=resolved_settings)
    uow = AsyncUnitOfWork(db)
    state = AssessmentStateService(db, capabilities)
    scoring = scoring_service or build_assessment_scoring_service(
        db,
        assessments=assessments,
        capabilities=capabilities,
        settings=resolved_settings,
    )
    reporting = reporting_service or build_assessment_reporting_service(
        db,
        llm_service=llm,
        scoring_service=scoring,
        settings=resolved_settings,
    )
    return AssessmentConversationService(
        db=db,
        assessments=assessments,
        capabilities=capabilities,
        answers=answers,
        axis_memory=axis_memory,
        idempotency=idempotency,
        llm_service=llm,
        uow=uow,
        state_service=state,
        scoring_service=scoring,
        reporting_service=reporting,
        settings=resolved_settings,
    )


def build_assessment_service(db: AsyncSession, settings: Settings | None = None) -> AssessmentService:
    resolved_settings = settings or get_settings()
    sectors = SectorRepository(db)
    sizes = CompanySizeRepository(db)
    regions = RegionRepository(db)
    companies = CompanyRepository(db)
    assessments = AssessmentRepository(db)
    capabilities = CapabilityRepository(db)
    answers = AssessmentAnswerRepository(db)
    axis_memory = AssessmentAxisMemoryRepository(db)
    idempotency = AssessmentIdempotencyRepository(db)
    llm = build_llm_service(settings=resolved_settings)
    uow = AsyncUnitOfWork(db)
    state = AssessmentStateService(db, capabilities)
    scoring = build_assessment_scoring_service(
        db,
        assessments=assessments,
        capabilities=capabilities,
        settings=resolved_settings,
    )
    reporting = build_assessment_reporting_service(
        db,
        llm_service=llm,
        scoring_service=scoring,
        settings=resolved_settings,
    )
    conversation = build_assessment_conversation_service(
        db,
        llm_service=llm,
        scoring_service=scoring,
        reporting_service=reporting,
        settings=resolved_settings,
    )
    return AssessmentService(
        db=db,
        sectors=sectors,
        sizes=sizes,
        regions=regions,
        companies=companies,
        assessments=assessments,
        capabilities=capabilities,
        answers=answers,
        axis_memory=axis_memory,
        idempotency=idempotency,
        llm_service=llm,
        uow=uow,
        state_service=state,
        conversation_service=conversation,
        reporting_service=reporting,
        settings=resolved_settings,
    )
