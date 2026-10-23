from typing import Any

import logging
from dataclasses import dataclass

from fastapi import HTTPException

from app.services.llm.failover import (
    complete_with_failover,
    gemini_completion,
    openai_completion,
)
from app.services.llm.prompts.templates import build_interview_guide_prompt, language_directive
from app.services.llm.utils import extract_json
from app.services.observability.llm_metrics import llm_context

logger = logging.getLogger(__name__)


from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.constants import ASSESSMENT_STATUS_COMPLETED
from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.schemas.final_report import FinalReportResponse
from app.schemas.recommendations import (
    AssessmentRecommendationsResponse,
    AssessmentTraceResponse,
    BatchRecommendationGenerateResponse,
    RecommendationOutputsResponse,
)
from sqlalchemy import select
from app.db.models.interview_guide import InterviewGuide
from app.schemas.interview_guide import (
    InterviewGuideResponse,
    InterviewGuideQuestionItem,
    GenerateInterviewGuideRequest,
    SaveInterviewGuideRequest,
)
from app.services.assessment.reporting.benchmark_service import BenchmarkService
from app.services.assessment.reporting.recommendation_service import RecommendationService
from app.services.assessment.reporting.final_report_service import ReportBuilderService
from app.services.assessment.reporting.trace_service import AssessmentTraceService
from app.services.assessment.scoring.scoring_service import (
    AssessmentScoringService,
    build_assessment_scoring_service,
)
from app.services.llm.core.facade_service import LLMService, build_llm_service
from app.services.platform import AsyncUnitOfWork


@dataclass(frozen=True)
class _GuideContext:
    """What the diagnostic already established about the client, as prompt-ready text."""

    assessed_capabilities: str = ""
    gaps: str = ""
    conversation: str = ""


@dataclass(frozen=True)
class _CompanyProfile:
    """Who the guide is about. Request values take precedence over the linked assessment."""

    name: str
    sector: str
    size: str
    region: str


def _named(entity: Any, attr: str = "name", default: str = "N/A") -> str:
    """A related record's display name, tolerating the relation being absent."""
    return getattr(entity, attr, default) if entity is not None else default


def _build_guide_messages(
    req: GenerateInterviewGuideRequest, company: "_CompanyProfile", context: "_GuideContext"
) -> tuple[str, str]:
    """The system and user prompts. Optional sections appear only when there is something to say."""
    system_content = (
        build_interview_guide_prompt(req.profile, req.language, req.custom_profile_description)
        + language_directive(req.language)
    )

    parts = [
        f"Company Name: {company.name}\n"
        f"Sector: {company.sector}\n"
        f"Size: {company.size}\n"
        f"Region: {company.region}\n"
        f"Language: {req.language}\n"
        f"Target Stakeholder Profile: {req.profile}\n"
    ]
    if req.custom_profile_description:
        parts.append(f"Target Stakeholder Custom Specifications: {req.custom_profile_description}\n")
    if req.custom_context:
        parts.append(f"Consultant Custom Context/Focus: {req.custom_context}\n")
    if context.assessed_capabilities:
        parts.append(f"\nAssessed Capabilities & Maturity Levels:\n{context.assessed_capabilities}\n")
    if context.gaps:
        parts.append(f"\nUnassessed Capabilities / Gaps:\n{context.gaps}\n")
    if context.conversation:
        parts.append(f"\nConversation History with Orion Bot:\n{context.conversation}\n")
    else:
        parts.append(
            "\nNo prior conversation history exists. Generate the guide from scratch based on "
            "the company profile and custom context.\n"
        )
    parts.append("\nGenerate the structured Client Interview Guide JSON:")
    return system_content, "".join(parts)


def _parse_question_items(items: Any) -> list[InterviewGuideQuestionItem]:
    """One section's questions, tolerating the several shapes the model returns.

    Field names vary between runs (`question`/`question_text`, `rationale`/`reason`/`why`), and
    `follow_up` comes back as either a string or a list. A question with no text is dropped
    rather than rendered as an empty row.
    """
    if not isinstance(items, list):
        return []

    parsed: list[InterviewGuideQuestionItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("question") or item.get("question_text") or "").strip()
        if not text:
            continue
        rationale = str(item.get("rationale") or item.get("reason") or item.get("why") or "").strip()
        follow_up = item.get("follow_up") or item.get("followup") or ""
        if isinstance(follow_up, list):
            follow_up = "\n".join(f"- {str(entry).strip()}" for entry in follow_up if entry)
        parsed.append(
            InterviewGuideQuestionItem(
                question=text, rationale=rationale, follow_up=str(follow_up).strip()
            )
        )
    return parsed


def _parse_guide_response(
    raw_response: str, req: GenerateInterviewGuideRequest, company: "_CompanyProfile"
) -> InterviewGuideResponse:
    """Turn the model's JSON into the response schema, or fail with a message the client can read."""
    try:
        payload = extract_json(raw_response)
        if not isinstance(payload, dict):
            raise ValueError("Interview guide output must be a JSON object")

        executive_summary = str(payload.get("executive_summary") or "").strip()
        unanswered_areas = payload.get("unanswered_areas", [])
        if not executive_summary:
            raise ValueError("Interview guide is missing executive_summary")
        if not isinstance(unanswered_areas, list):
            raise ValueError("Interview guide unanswered_areas must be a list")

        section_keys = (
            "introduction_questions",
            "manage_questions",
            "analyze_questions",
            "improve_questions",
            "closure_questions",
        )
        missing_sections = [key for key in section_keys if key not in payload]
        if missing_sections:
            raise ValueError(
                "Interview guide is missing sections: " + ", ".join(missing_sections)
            )
        sections = {
            key: _parse_question_items(payload.get(key))
            for key in section_keys
        }
        question_count = sum(len(items) for items in sections.values())
        if question_count == 0:
            raise ValueError("Interview guide contains no valid questions")

        return InterviewGuideResponse(
            assessment_id=req.assessment_id,
            company_name=company.name,
            # Carried through so a freshly generated guide already knows who it is for, and its
            # first autosave stores that rather than the client's form default.
            profile=req.profile,
            language=req.language,
            executive_summary=executive_summary,
            unanswered_areas=unanswered_areas,
            introduction_questions=sections["introduction_questions"],
            manage_questions=sections["manage_questions"],
            analyze_questions=sections["analyze_questions"],
            improve_questions=sections["improve_questions"],
            closure_questions=sections["closure_questions"],
        )
    except Exception as exc:
        logger.error("Error generating interview guide: %s. Raw response: %s", exc, raw_response)
        raise HTTPException(
            status_code=502,
            detail=(
                "Échec de la génération ou de la validation du guide d'entretien. Veuillez réessayer."
                if req.language.lower().startswith("fr")
                else "Failed to generate or validate the interview guide. Please try again."
            ),
        )


def _has_usable_interview_guide(raw_response: str) -> bool:
    """Return whether a provider response has enough content to be a real guide."""
    try:
        payload = extract_json(raw_response)
        if not isinstance(payload, dict) or not str(payload.get("executive_summary") or "").strip():
            return False
        keys = (
            "introduction_questions", "manage_questions", "analyze_questions",
            "improve_questions", "closure_questions",
        )
        return all(key in payload for key in keys) and any(
            _parse_question_items(payload.get(key)) for key in keys
        )
    except Exception:
        return False


class AssessmentReportingService:
    """Compatibility facade delegating to reporting sub-services."""

    def __init__(
        self,
        trace_service: AssessmentTraceService,
        recommendation_service: RecommendationService,
        report_builder_service: ReportBuilderService,
    ) -> None:
        self.trace = trace_service
        self.recommendations = recommendation_service
        self.report_builder = report_builder_service

    async def get_trace(self, assessment_id: int, limit: int = 500, offset: int = 0) -> AssessmentTraceResponse | None:
        return await self.trace.get_trace(assessment_id=assessment_id, limit=limit, offset=offset)

    async def get_recommendations(self, assessment_id: int) -> AssessmentRecommendationsResponse | None:
        return await self.recommendations.get_recommendations(assessment_id=assessment_id)

    async def generate_recommendations_batch(
        self,
        assessment_id: int,
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> BatchRecommendationGenerateResponse | None:
        return await self.recommendations.generate_recommendations_batch(
            assessment_id=assessment_id,
            language=language,
            max_actions_per_capability=max_actions_per_capability,
            tone=tone,
            max_words_per_capability=max_words_per_capability,
        )

    async def get_recommendation_outputs(self, assessment_id: int) -> RecommendationOutputsResponse | None:
        return await self.recommendations.get_recommendation_outputs(assessment_id=assessment_id)

    async def get_final_report(
        self,
        assessment_id: int,
        refresh_synthesis: bool = False,
    ) -> FinalReportResponse | None:
        assessment = await self._prepare_completed_report_artifacts(assessment_id)
        if assessment is None:
            return None
        return await self.report_builder.get_final_report(
            assessment_id=assessment_id,
            refresh_synthesis=refresh_synthesis,
        )

    async def _prepare_completed_report_artifacts(self, assessment_id: int) -> Any | None:
        assessment = await self.report_builder.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        if str(getattr(assessment, "status", "")) != ASSESSMENT_STATUS_COMPLETED:
            return assessment

        outputs = await self.recommendations.get_recommendation_outputs(assessment_id=assessment_id)
        if (
            outputs is None
            or not outputs.items
            or getattr(assessment, "overall_maturity_level_id", None) is None
            or not getattr(assessment, "overall_maturity_band", None)
        ):
            await self.recommendations.finalize_completed_assessment(
                assessment_id=assessment_id,
                assessment=assessment,
            )

        await self.report_builder.prepare_leaders_snapshot_generation(
            assessment_id=assessment_id,
            assessment=assessment,
        )
        return assessment

    async def _call_moonshot(self, messages: list[dict[str, str]]) -> str:
        import httpx
        import time
        from app.core.config import get_settings
        from app.services.observability.llm_metrics import log_llm_call

        settings = get_settings()
        api_key = settings.moonshot_api_key
        model = settings.moonshot_model
        base_url = settings.moonshot_base_url

        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "temperature": 1.0,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        timeout_val = settings.llm_request_timeout_seconds
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            log_llm_call(provider="moonshot", model=model, ok=False, error=str(exc),
                         latency_ms=int((time.monotonic() - start) * 1000), input_messages=messages)
            raise
        content = data["choices"][0]["message"]["content"]
        log_llm_call(provider="moonshot", model=model, ok=True,
                     latency_ms=int((time.monotonic() - start) * 1000),
                     usage=data.get("usage"), input_messages=messages, output_text=content)
        return content

    async def get_interview_guide(self, req: GenerateInterviewGuideRequest) -> InterviewGuideResponse | None:
        """Generate a stakeholder interview guide, grounded in a past assessment when there is one.

        Five steps, each below: what we know about the client, who the guide is for, the prompt,
        the model call, and turning the reply into the response schema.
        """
        assessment = None
        if req.assessment_id is not None:
            assessment = await self.report_builder.assessments.get_by_id(req.assessment_id)

        context = await self._interview_guide_context(req.assessment_id, assessment)
        company = self._resolve_company_profile(req, assessment)
        system_content, user_content = _build_guide_messages(req, company, context)
        raw_response = await self._request_interview_guide(system_content, user_content)
        return _parse_guide_response(raw_response, req, company)

    async def _interview_guide_context(
        self, assessment_id: int | None, assessment: Any | None
    ) -> "_GuideContext":
        """What the diagnostic already established: scored capabilities, gaps, and the transcript.

        A missing or unreadable assessment is not fatal -- the guide is still generated, just
        without grounding -- but it is logged, because a guide that quietly ignores the
        diagnostic looks identical to one that used it.
        """
        if assessment_id is None or assessment is None:
            return _GuideContext()

        assessed_lines: list[str] = []
        gap_lines: list[str] = []
        try:
            capabilities = await self.report_builder.capabilities.list_all_for_assessment(assessment_id)
            for item in capabilities:
                axis = str(item.get("axis", "")).upper()
                code = item.get("code", "")
                label = item.get("label", "")
                status = item.get("assessment_status", "not_assessed")
                level = item.get("maturity_level_id")
                if status == "assessed" and level is not None:
                    assessed_lines.append(
                        f"- [{axis}] {code}: {label} - Assessed Level {level}\n"
                        f"  Justification/Evidence: {item.get('rationale') or ''}"
                    )
                else:
                    gap_lines.append(f"- [{axis}] {code}: {label} ({str(status).replace('_', ' ')})")
        except Exception:
            logger.warning(
                "Could not load capabilities for assessment %s; generating the guide without "
                "assessment grounding.", assessment_id, exc_info=True,
            )

        conversation = ""
        trace = await self.trace.get_trace(assessment_id=assessment_id)
        if trace and trace.items:
            turns: list[str] = []
            for item in trace.items:
                turns.append(f"Orion Bot: {item.question}")
                turns.append(f"Client: {item.answer}")
            conversation = "\n".join(turns)

        return _GuideContext(
            assessed_capabilities="\n".join(assessed_lines),
            gaps="\n".join(gap_lines),
            conversation=conversation,
        )

    @staticmethod
    def _resolve_company_profile(
        req: GenerateInterviewGuideRequest, assessment: Any | None
    ) -> "_CompanyProfile":
        """Request values win; a linked assessment fills whatever the consultant left blank."""
        company = getattr(assessment, "company", None) if assessment is not None else None
        return _CompanyProfile(
            name=req.company_name or (getattr(company, "name", "Client") if company else "Client"),
            sector=req.sector or _named(getattr(company, "sector", None)),
            size=req.size or _named(getattr(company, "company_size", None), attr="label"),
            region=req.region or _named(getattr(company, "region_ref", None)),
        )

    async def _request_interview_guide(self, system_content: str, user_content: str) -> str:
        """Ask a model for the guide, trying Moonshot first only when it is actually configured.

        Moonshot was the original choice for this prompt, so it keeps priority -- but it is
        skipped rather than called and failed when no key is set. Everything else goes through
        the shared Mistral -> OpenAI -> Gemini loop, so one provider being down no longer costs
        the consultant their guide.
        """
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        async def _mistral(system_prompt: str, user_prompt: str) -> str | None:
            # The gateway retries internally with backoff on 429/5xx.
            output = await self.report_builder.llm.gateway.chat_messages(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            if not _has_usable_interview_guide(output):
                logger.warning("Mistral returned an incomplete interview guide; continuing failover.")
                return None
            return output

        async def _validated_fallback(provider, system_prompt: str, user_prompt: str) -> str | None:
            output = await provider(system_prompt, user_prompt)
            if not output or not _has_usable_interview_guide(output):
                logger.warning("Fallback provider returned an incomplete interview guide; continuing failover.")
                return None
            return output

        with llm_context(feature="interview.generate", kind="run"):
            raw_response = ""
            if (get_settings().moonshot_api_key or "").strip():
                try:
                    raw_response = await self._call_moonshot(messages)
                except Exception as exc:
                    logger.warning("Moonshot call failed (%s); falling through to the provider loop.", exc)
                    raw_response = ""

            if not raw_response.strip():
                    raw_response = await complete_with_failover(
                        system_content,
                        user_content,
                        providers=[
                            ("Mistral", _mistral),
                            ("OpenAI", lambda s, u: _validated_fallback(openai_completion, s, u)),
                            ("Gemini", lambda s, u: _validated_fallback(gemini_completion, s, u)),
                        ],
                        label="interview.generate",
                    )

        if raw_response.startswith("Error: All LLM providers unavailable"):
            raise RuntimeError(raw_response)
        return raw_response

    async def debug_competitive_first_layer(
        self,
        assessment_id: int,
        competitor_name: str | None = None,
    ) -> dict[str, Any] | None:
        return await self.report_builder.debug_competitive_first_layer(
            assessment_id=assessment_id,
            competitor_name=competitor_name,
        )

    async def debug_telecom_semantic_leaders(self, assessment_id: int) -> dict[str, Any] | None:
        return await self.report_builder.debug_telecom_semantic_leaders(assessment_id=assessment_id)

    async def debug_telecom_discovery_leaders(self, assessment_id: int) -> dict[str, Any] | None:
        return await self.report_builder.debug_telecom_discovery_leaders(assessment_id=assessment_id)

    async def finalize_completed_assessment(self, assessment_id: int, assessment: Any) -> None:
        await self.recommendations.finalize_completed_assessment(
            assessment_id=assessment_id,
            assessment=assessment,
        )
        await self.report_builder.prepare_leaders_snapshot_generation(
            assessment_id=assessment_id,
            assessment=assessment,
        )

    async def save_interview_guide(self, req: SaveInterviewGuideRequest) -> dict[str, Any]:
        session = self.report_builder.db
        from datetime import datetime

        # Match ONLY by explicit id. Matching by (company_name, profile) used to silently
        # overwrite a prior interview for the same company+profile -- so a guide without an id
        # always creates a NEW row, letting a company have several distinct interviews.
        guide = None
        if req.id:
            result = await session.execute(
                select(InterviewGuide).where(InterviewGuide.id == req.id)
            )
            guide = result.scalar_one_or_none()

        if guide:
            # Update
            guide.assessment_id = req.assessment_id
            guide.company_name = req.company_name
            guide.profile = req.profile
            guide.language = req.language
            guide.payload = req.payload
            guide.updated_at = datetime.utcnow()
        else:
            # Insert new
            guide = InterviewGuide(
                assessment_id=req.assessment_id,
                company_name=req.company_name,
                profile=req.profile,
                language=req.language,
                payload=req.payload
            )
            session.add(guide)

        await session.commit()
        return {"status": "success", "id": guide.id}

    async def list_interview_guides(self) -> list[InterviewGuide]:
        session = self.report_builder.db
        result = await session.execute(
            select(InterviewGuide).order_by(InterviewGuide.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_saved_interview_guide(self, guide_id: int) -> InterviewGuide | None:
        session = self.report_builder.db
        result = await session.execute(
            select(InterviewGuide).where(InterviewGuide.id == guide_id)
        )
        return result.scalar_one_or_none()


def build_assessment_reporting_service(
    db: AsyncSession,
    llm_service: LLMService | None = None,
    benchmark_service: BenchmarkService | None = None,
    scoring_service: AssessmentScoringService | None = None,
    settings: Settings | None = None,
) -> AssessmentReportingService:
    settings = settings or get_settings()
    assessments = AssessmentRepository(db)
    answers = AssessmentAnswerRepository(db)
    capabilities = CapabilityRepository(db)
    llm = llm_service or build_llm_service(settings=settings)
    benchmarks = benchmark_service or BenchmarkService(db=db)
    uow = AsyncUnitOfWork(db)
    scoring = scoring_service or build_assessment_scoring_service(
        db,
        assessments=assessments,
        capabilities=capabilities,
        settings=settings,
    )

    trace_service = AssessmentTraceService(
        assessments=assessments,
        answers=answers,
    )
    recommendation_service = RecommendationService(
        db=db,
        assessments=assessments,
        capabilities=capabilities,
        llm_service=llm,
        scoring_service=scoring,
        uow=uow,
        settings=settings,
    )
    report_builder = ReportBuilderService(
        db=db,
        assessments=assessments,
        capabilities=capabilities,
        llm_service=llm,
        benchmark_service=benchmarks,
        scoring_service=scoring,
        uow=uow,
        settings=settings,
    )
    return AssessmentReportingService(
        trace_service=trace_service,
        recommendation_service=recommendation_service,
        report_builder_service=report_builder,
    )
