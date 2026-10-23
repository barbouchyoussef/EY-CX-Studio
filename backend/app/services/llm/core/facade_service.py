"""The single entry point every assessment feature uses to talk to a language model.

`LLMService` exposes one method per task -- generate a question, route an intent, detect coverage,
classify a company, write recommendations -- rather than a generic "call the model". Callers pass
domain arguments and receive parsed results; prompt text, response parsing and provider choice all
stay behind this boundary.

That boundary is what makes the rest of the system testable and observable. A feature can be
tested by substituting this service, and because every call funnels through here it is also the
seam where usage is metered into `llm_calls` -- which is why the issue-log module, which does not
go through this facade, is the one feature with no recorded token usage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.services.llm.classification.company_classification import (
    CompanyClassificationService,
    build_company_classification_service,
)
from app.services.llm.conversation.memory_service import MemoryService, build_memory_service
from app.services.llm.conversation.question_composer import (
    QuestionComposerService,
    build_question_composer_service,
)
from app.services.llm.core.gateway import MistralGateway, build_mistral_gateway
from app.services.llm.coverage.detector import CoverageDetectorService, build_coverage_detector_service
from app.services.llm.intent.router import IntentRouter, build_intent_router
from app.services.llm.reporting.recommendation_generator import (
    RecommendationGeneratorService,
    build_recommendation_generator_service,
)
from app.services.llm.reporting.report_synthesis import ReportSynthesisService, build_report_synthesis_service
from app.services.llm.utils import async_lru_cache, clean_memory_text, clean_single_text, extract_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str

class LLMService:
    def __init__(
        self,
        settings: Settings,
        gateway: MistralGateway | None = None,
        intent_router: IntentRouter | None = None,
        coverage_detector: CoverageDetectorService | None = None,
        question_composer: QuestionComposerService | None = None,
        memory_service: MemoryService | None = None,
        recommendation_generator: RecommendationGeneratorService | None = None,
        report_synthesis: ReportSynthesisService | None = None,
        company_classification: CompanyClassificationService | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or build_mistral_gateway(settings=settings)
        self.intent_router = intent_router or build_intent_router(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_text=clean_single_text,
        )
        self.coverage_detector = coverage_detector or build_coverage_detector_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            extract_json=extract_json,
            is_negative_evidence_answer=self.intent_router.is_negative_evidence_answer,
        )
        self.question_composer = question_composer or build_question_composer_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_text=clean_single_text,
            clean_memory_text=clean_memory_text,
        )
        self.memory_service = memory_service or build_memory_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_memory_text=clean_memory_text,
        )
        self.recommendation_generator = recommendation_generator or build_recommendation_generator_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_text=clean_single_text,
            extract_json=extract_json,
        )
        self.report_synthesis = report_synthesis or build_report_synthesis_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_text=clean_single_text,
            extract_json=extract_json,
        )
        self.company_classification = company_classification or build_company_classification_service(
            settings=settings,
            chat_messages=self.gateway.chat_messages,
            clean_text=clean_single_text,
            extract_json=extract_json,
        )

    @async_lru_cache(maxsize=128)
    async def generate_question(
        self,
        axis: str,
        missing: list[str],
        history: list[ChatTurn],
        sector: str,
        latest_user_answer: str | None = None,
        transition_topic: str | None = None,
        related_topics: list[str] | None = None,
        memory_summary: str | None = None,
        axis_description: str | None = None,
        axis_question_guidelines: str | None = None,
        question_guidelines: list[str] | None = None,
        maturity_rubrics: list[dict] | None = None,
        conversation_stage: str = "intro",
        ask_evidence: bool = False,
        helper_mode: bool = False,
        prompt_profile: str = "consultant_guided",
        language: str = "fr",
    ) -> tuple[str, list[str]]:
        return await self.question_composer.generate_question(
            axis=axis,
            missing=missing,
            history=history,
            sector=sector,
            latest_user_answer=latest_user_answer,
            transition_topic=transition_topic,
            related_topics=related_topics,
            memory_summary=memory_summary,
            axis_description=axis_description,
            axis_question_guidelines=axis_question_guidelines,
            question_guidelines=question_guidelines,
            maturity_rubrics=maturity_rubrics,
            conversation_stage=conversation_stage,
            ask_evidence=ask_evidence,
            helper_mode=helper_mode,
            prompt_profile=prompt_profile,
            language=language,
        )

    async def route_user_intent(self, text: str, previous_question: str | None = None) -> str:
        return await self.intent_router.route(text, previous_question=previous_question)

    def _fast_route_intent(self, text: str, previous_question: str | None = None) -> str | None:
        return self.intent_router.fast_route(text, previous_question=previous_question)

    def _normalize_fast_intent_text(self, text: str) -> str:
        return self.intent_router.normalize_fast_intent_text(text)

    def _is_negative_evidence_answer(self, text: str) -> bool:
        return self.intent_router.is_negative_evidence_answer(text)

    def is_negative_evidence_answer(self, text: str) -> bool:
        return self.intent_router.is_negative_evidence_answer(text)

    def _is_negative_evidence_text(self, normalized_text: str) -> bool:
        return self.intent_router.is_negative_evidence_text(normalized_text)

    def _is_confusion_request_text(self, normalized_text: str) -> bool:
        return self.intent_router.is_confusion_request_text(normalized_text)

    async def generate_clarification_question(
        self,
        axis: str,
        latest_user_answer: str,
        hint: str | None,
        sector: str | None = None,
        company_scope: str | None = None,
        missing_topic: str | None = None,
        history: list[ChatTurn] | None = None,
        concerned_question: str | None = None,
        language: str = "fr",
    ) -> str:
        return await self.question_composer.generate_clarification_question(
            axis=axis,
            latest_user_answer=latest_user_answer,
            hint=hint,
            sector=sector,
            company_scope=company_scope,
            missing_topic=missing_topic,
            history=history or [],
            concerned_question=concerned_question,
            language=language,
        )

    async def update_axis_memory(
        self,
        axis: str,
        current_summary: str | None,
        new_answer: str,
        covered_labels: list[str],
    ) -> str:
        return await self.memory_service.update_axis_memory(
            axis=axis,
            current_summary=current_summary,
            new_answer=new_answer,
            covered_labels=covered_labels,
        )

    async def detect_coverage(
        self,
        answer: str,
        criteria: list[dict],
        rubrics_by_capability: dict[int, list[dict]] | None = None,
    ) -> dict:
        return await self.coverage_detector.detect_coverage(
            answer=answer,
            criteria=criteria,
            rubrics_by_capability=rubrics_by_capability,
        )

    @async_lru_cache(maxsize=64)
    async def classify_company(self, company_name: str, sector_options: list[dict], size_options: list[dict]) -> dict:
        return await self.company_classification.classify_company(company_name, sector_options, size_options)

    async def generate_recommendation(
        self,
        axis: str,
        capability: str,
        maturity_label: str,
        confidence: float | None,
        justification: str | None,
        recommendation_guideline: str | None,
        priority_hint: str | None,
        business_impact: str | None,
        tone_hint: str | None,
        supporting_notes: str | None = None,
        language: str = "fr",
    ) -> str:
        return await self.recommendation_generator.generate_recommendation(
            axis=axis,
            capability=capability,
            maturity_label=maturity_label,
            confidence=confidence,
            justification=justification,
            recommendation_guideline=recommendation_guideline,
            priority_hint=priority_hint,
            business_impact=business_impact,
            tone_hint=tone_hint,
            supporting_notes=supporting_notes,
            language=language,
        )

    async def generate_recommendations_batch(
        self,
        assessment_id: int,
        items: list[dict[str, Any]],
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        return await self.recommendation_generator.generate_recommendations_batch(
            assessment_id=assessment_id,
            items=items,
            language=language,
            max_actions_per_capability=max_actions_per_capability,
            tone=tone,
            max_words_per_capability=max_words_per_capability,
        )

    @async_lru_cache(maxsize=32)
    async def generate_report_synthesis(
        self,
        company_name: str,
        overall_maturity_band: str,
        overall_score_percent: float,
        strongest_axis: str,
        priority_axis: str,
        strengths_count: int,
        pain_points_count: int,
        axes: list[dict[str, Any]],
        strengths: list[dict[str, Any]],
        pain_points: list[dict[str, Any]],
        language: str = "fr",
    ) -> dict[str, str | None]:
        return await self.report_synthesis.generate_report_synthesis(
            company_name=company_name,
            overall_maturity_band=overall_maturity_band,
            overall_score_percent=overall_score_percent,
            strongest_axis=strongest_axis,
            priority_axis=priority_axis,
            strengths_count=strengths_count,
            pain_points_count=pain_points_count,
            axes=axes,
            strengths=strengths,
            pain_points=pain_points,
            language=language,
        )

    async def is_confusion_signal(self, answer: str) -> bool:
        return (await self.route_user_intent(answer)) == "CONFUSION"

    async def is_social_signal(self, answer: str) -> bool:
        return False

    async def is_resume_signal(self, answer: str) -> bool:
        return (await self.route_user_intent(answer)) == "RESUME"

    async def is_process_meta_signal(self, answer: str) -> bool:
        return (await self.route_user_intent(answer)) == "CONFUSION"


def build_llm_service(
    settings: Settings | None = None,
    gateway: MistralGateway | None = None,
    intent_router: IntentRouter | None = None,
    coverage_detector: CoverageDetectorService | None = None,
    question_composer: QuestionComposerService | None = None,
    memory_service: MemoryService | None = None,
    recommendation_generator: RecommendationGeneratorService | None = None,
    report_synthesis: ReportSynthesisService | None = None,
    company_classification: CompanyClassificationService | None = None,
) -> LLMService:
    resolved_settings = settings or get_settings()
    return LLMService(
        settings=resolved_settings,
        gateway=gateway,
        intent_router=intent_router,
        coverage_detector=coverage_detector,
        question_composer=question_composer,
        memory_service=memory_service,
        recommendation_generator=recommendation_generator,
        report_synthesis=report_synthesis,
        company_classification=company_classification,
    )
