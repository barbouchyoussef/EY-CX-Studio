from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.constants import ASSESSMENT_STATUS_IN_PROGRESS, normalize_axis_name
from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_axis_memory_repository import AssessmentAxisMemoryRepository
from app.repositories.assessment_idempotency_repository import AssessmentIdempotencyRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.company_size_repository import CompanySizeRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.sector_repository import SectorRepository
from app.schemas.admin import AssessmentListItem, AssessmentsListResponse
from app.schemas.assessment import (
    AnswerResponse,
    AssessmentResponse,
    AxisProgress,
    CompanyInfo,
    NextQuestionResponse,
)
from app.schemas.assessment_memory import AssessmentMemoryResponse, AxisMemoryItem
from app.schemas.capability_status import CapabilitiesStatusResponse, CapabilityHighlightsResponse, CapabilityStatusItem
from app.schemas.conversation import MessageItem, MessagesResponse
from app.schemas.final_report import FinalReportResponse
from app.schemas.recommendations import (
    AssessmentRecommendationsResponse,
    AssessmentTraceResponse,
    BatchRecommendationGenerateResponse,
    RecommendationOutputsResponse,
)
from app.services.assessment.conversation.service import AssessmentConversationService
from app.services.assessment.reporting.reporting_service import AssessmentReportingService
from app.services.assessment.state.state_service import AssessmentStateService
from app.services.llm.core.facade_service import LLMService
from app.services.platform import AsyncUnitOfWork


class AssessmentService:
    """Compatibility facade for assessment lifecycle and read-only status endpoints."""

    PROMPT_PROFILES = {"consultant_guided"}

    def __init__(
        self,
        db: AsyncSession,
        sectors: SectorRepository,
        sizes: CompanySizeRepository,
        regions: RegionRepository,
        companies: CompanyRepository,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        answers: AssessmentAnswerRepository,
        axis_memory: AssessmentAxisMemoryRepository,
        idempotency: AssessmentIdempotencyRepository,
        llm_service: LLMService,
        uow: AsyncUnitOfWork,
        state_service: AssessmentStateService,
        conversation_service: AssessmentConversationService,
        reporting_service: AssessmentReportingService,
        settings: Settings,
    ) -> None:
        self.db = db
        self.sectors = sectors
        self.sizes = sizes
        self.regions = regions
        self.companies = companies
        self.assessments = assessments
        self.capabilities = capabilities
        self.answers = answers
        self.axis_memory = axis_memory
        self.idempotency = idempotency
        self.llm = llm_service
        self.uow = uow
        self.state = state_service
        self.conversation = conversation_service
        self.reporting = reporting_service
        self.settings = settings

    async def start_assessment(
        self,
        company_name: str,
        sector_label: str | None,
        company_size_label: str | None,
        region: str | None = None,
        prompt_profile: str | None = None,
        language: str = "fr",
    ):
        async with self.uow:
            selected_profile = (prompt_profile or "consultant_guided").strip()
            if selected_profile == "llm_reasoning_light":
                selected_profile = "consultant_guided"
            if selected_profile not in self.PROMPT_PROFILES:
                raise ValueError(f"Unsupported prompt_profile: {selected_profile}")
            sector, size = await self._resolve_company_profile(
                company_name=company_name,
                sector_code=sector_label,
                company_size_code=company_size_label,
            )
            region_row = await self.regions.get_by_code_or_name(region)
            company = await self.companies.create(
                name=company_name,
                sector_id=sector.id,
                size_id=size.id,
                region_id=getattr(region_row, "id", None),
            )
            first_axis = await self.state.get_first_axis()

            assessment = await self.assessments.create(
                company_id=company.id,
                status=ASSESSMENT_STATUS_IN_PROGRESS,
                current_axis_id=first_axis.id if first_axis is not None else None,
                prompt_profile=selected_profile,
                language=language,
            )
            await self.assessments.initialize_scores(assessment.id)
            return assessment

    async def get_assessment(self, assessment_id: int) -> AssessmentResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None

        progress_map = await self.capabilities.get_axis_progress(assessment_id)
        progress = [AxisProgress(axis=axis, covered=covered, total=total) for axis, (covered, total) in progress_map.items()]

        company = assessment.company
        sector_label = getattr(company.sector, "name", "Unknown")
        size_label = getattr(company.company_size, "name", "Unknown")
        region_label = getattr(getattr(company, "region_ref", None), "name", None)
        current_axis_name = normalize_axis_name(assessment.current_axis.name) if assessment.current_axis is not None else None

        return AssessmentResponse(
            id=assessment.id,
            status=assessment.status,
            current_axis=current_axis_name,
            state_version=int(assessment.state_version),
            overall_maturity_band=assessment.overall_maturity_band,
            company=CompanyInfo(id=company.id, name=company.name, sector=sector_label, size=size_label, region=region_label),
            progress=progress,
        )

    async def get_memory(self, assessment_id: int) -> AssessmentMemoryResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.axis_memory.list_for_assessment(assessment_id=assessment_id)
        items = [
            AxisMemoryItem(axis=str(row.axis), summary=str(row.summary), updated_at=row.updated_at)
            for row in rows
        ]
        return AssessmentMemoryResponse(assessment_id=assessment_id, items=items)

    async def list_assessments(
        self,
        limit: int = 50,
        offset: int = 0,
        region_code: str | None = None,
    ) -> AssessmentsListResponse:
        rows = await self.assessments.list_assessments(limit=limit, offset=offset, region_code=region_code)
        items: list[AssessmentListItem] = []
        for assessment in rows:
            company = assessment.company
            items.append(
                AssessmentListItem(
                    id=assessment.id,
                    status=assessment.status,
                    current_axis=normalize_axis_name(assessment.current_axis.name) if assessment.current_axis is not None else None,
                    company_name=company.name,
                    sector=getattr(company.sector, "name", ""),
                    size=getattr(company.company_size, "name", ""),
                    region=getattr(getattr(company, "region_ref", None), "name", None),
                    overall_maturity_band=assessment.overall_maturity_band,
                    created_at=assessment.created_at,
                    updated_at=assessment.updated_at,
                )
            )
        return AssessmentsListResponse(items=items, limit=limit, offset=offset)

    async def get_messages(self, assessment_id: int, limit: int = 200, offset: int = 0) -> MessagesResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.answers.list_for_assessment(assessment_id, limit=limit, offset=offset)
        items: list[MessageItem] = []
        for message in rows:
            items.append(
                MessageItem(
                    id=(message.id * 2) - 1,
                    role="assistant",
                    axis=None,
                    content=message.question,
                    created_at=message.created_at,
                )
            )
            items.append(
                MessageItem(
                    id=(message.id * 2),
                    role="user",
                    axis=None,
                    content=message.answer,
                    created_at=message.created_at,
                )
            )
        return MessagesResponse(assessment_id=assessment_id, items=items)

    async def get_capabilities_status(self, assessment_id: int, axis: str | None = None) -> CapabilitiesStatusResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        canonical_axis = normalize_axis_name(axis) if axis else None
        rows = await self.capabilities.list_all_for_assessment(assessment_id, axis_name=canonical_axis)
        items = [CapabilityStatusItem(**row) for row in rows]
        return CapabilitiesStatusResponse(assessment_id=assessment_id, axis=canonical_axis, items=items)

    async def get_capability_highlights(
        self,
        assessment_id: int,
        axis: str | None = None,
        limit: int = 6,
    ) -> CapabilityHighlightsResponse | None:
        status = await self.get_capabilities_status(assessment_id=assessment_id, axis=axis)
        if status is None:
            return None

        covered_items = [item for item in status.items if item.covered]
        if not covered_items:
            covered_items = [item for item in status.items if item.assessed]

        return CapabilityHighlightsResponse(
            assessment_id=assessment_id,
            axis=status.axis,
            total_highlights=len(covered_items),
            items=covered_items[:limit],
        )

    async def next_question(self, assessment_id: int) -> NextQuestionResponse | None:
        return await self.conversation.next_question(assessment_id)

    async def submit_answer(
        self,
        assessment_id: int,
        answer: str,
        idempotency_key: str | None = None,
        expected_axis: str | None = None,
        expected_version: int | None = None,
    ) -> AnswerResponse | None:
        return await self.conversation.submit_answer(
            assessment_id=assessment_id,
            answer=answer,
            idempotency_key=idempotency_key,
            expected_axis=expected_axis,
            expected_version=expected_version,
        )

    async def get_recommendations(self, assessment_id: int) -> AssessmentRecommendationsResponse | None:
        return await self.reporting.get_recommendations(assessment_id=assessment_id)

    async def generate_recommendations_batch(
        self,
        assessment_id: int,
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> BatchRecommendationGenerateResponse | None:
        return await self.reporting.generate_recommendations_batch(
            assessment_id=assessment_id,
            language=language,
            max_actions_per_capability=max_actions_per_capability,
            tone=tone,
            max_words_per_capability=max_words_per_capability,
        )

    async def get_trace(self, assessment_id: int, limit: int = 500, offset: int = 0) -> AssessmentTraceResponse | None:
        return await self.reporting.get_trace(
            assessment_id=assessment_id,
            limit=limit,
            offset=offset,
        )

    async def get_recommendation_outputs(self, assessment_id: int) -> RecommendationOutputsResponse | None:
        return await self.reporting.get_recommendation_outputs(
            assessment_id=assessment_id
        )

    async def get_final_report(self, assessment_id: int) -> FinalReportResponse | None:
        return await self.reporting.get_final_report(assessment_id=assessment_id)

    async def _resolve_company_profile(self, company_name: str, sector_code: str | None, company_size_code: str | None):
        if sector_code and company_size_code:
            sector = await self.sectors.get_by_code(sector_code)
            size = await self.sizes.get_by_code(company_size_code)
            if sector is None:
                raise ValueError(f"Unknown sector code: {sector_code!r}")
            if size is None:
                raise ValueError(f"Unknown company_size code: {company_size_code!r}")
            return sector, size

        sector_options = [{"code": sector.code, "label": sector.name} for sector in await self.sectors.list_options()]
        size_options = [{"code": size.code, "label": size.name} for size in await self.sizes.list_options()]
        if not sector_options or not size_options:
            raise ValueError("Sector/company size options are empty in DB; seed reference tables first.")

        classification = await self.llm.classify_company(company_name, sector_options, size_options)
        sector = await self.sectors.get_or_create_by_code(classification["sector_code"], label=classification["sector_code"])
        size = await self.sizes.get_or_create_by_code(
            classification["company_size_code"],
            label=classification["company_size_code"],
        )
        return sector, size
