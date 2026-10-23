"""All language-model access, behind one facade.

`core` is the gateway and the per-task facade, `prompts` holds every prompt, and the remaining
packages are one per task: intent, coverage, classification, conversation, reporting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "ChatTurn",
    "CompanyClassificationService",
    "CoverageDetectorService",
    "IntentRouter",
    "LLMService",
    "MemoryService",
    "MistralGateway",
    "QuestionComposerService",
    "RecommendationGeneratorService",
    "ReportSynthesisService",
    "build_company_classification_service",
    "build_coverage_detector_service",
    "build_intent_router",
    "build_llm_service",
    "build_memory_service",
    "build_mistral_gateway",
    "build_question_composer_service",
    "build_recommendation_generator_service",
    "build_report_synthesis_service",
]

if TYPE_CHECKING:
    from app.services.llm.classification.company_classification import (
        CompanyClassificationService,
        build_company_classification_service,
    )
    from app.services.llm.conversation.memory_service import MemoryService, build_memory_service
    from app.services.llm.conversation.question_composer import (
        QuestionComposerService,
        build_question_composer_service,
    )
    from app.services.llm.core.facade_service import ChatTurn, LLMService, build_llm_service
    from app.services.llm.core.gateway import MistralGateway, build_mistral_gateway
    from app.services.llm.coverage.detector import CoverageDetectorService, build_coverage_detector_service
    from app.services.llm.intent.router import IntentRouter, build_intent_router
    from app.services.llm.reporting.recommendation_generator import (
        RecommendationGeneratorService,
        build_recommendation_generator_service,
    )
    from app.services.llm.reporting.report_synthesis import ReportSynthesisService, build_report_synthesis_service


def __getattr__(name: str) -> Any:
    if name in {"ChatTurn", "LLMService", "build_llm_service"}:
        from app.services.llm.core.facade_service import ChatTurn, LLMService, build_llm_service

        return {"ChatTurn": ChatTurn, "LLMService": LLMService, "build_llm_service": build_llm_service}[name]
    if name in {"CompanyClassificationService", "build_company_classification_service"}:
        from app.services.llm.classification.company_classification import (
            CompanyClassificationService,
            build_company_classification_service,
        )

        return {
            "CompanyClassificationService": CompanyClassificationService,
            "build_company_classification_service": build_company_classification_service,
        }[name]
    if name in {"CoverageDetectorService", "build_coverage_detector_service"}:
        from app.services.llm.coverage.detector import CoverageDetectorService, build_coverage_detector_service

        return {
            "CoverageDetectorService": CoverageDetectorService,
            "build_coverage_detector_service": build_coverage_detector_service,
        }[name]
    if name in {"MistralGateway", "build_mistral_gateway"}:
        from app.services.llm.core.gateway import MistralGateway, build_mistral_gateway

        return {"MistralGateway": MistralGateway, "build_mistral_gateway": build_mistral_gateway}[name]
    if name in {"IntentRouter", "build_intent_router"}:
        from app.services.llm.intent.router import IntentRouter, build_intent_router

        return {"IntentRouter": IntentRouter, "build_intent_router": build_intent_router}[name]
    if name in {"MemoryService", "build_memory_service"}:
        from app.services.llm.conversation.memory_service import MemoryService, build_memory_service

        return {"MemoryService": MemoryService, "build_memory_service": build_memory_service}[name]
    if name in {"QuestionComposerService", "build_question_composer_service"}:
        from app.services.llm.conversation.question_composer import (
            QuestionComposerService,
            build_question_composer_service,
        )

        return {"QuestionComposerService": QuestionComposerService, "build_question_composer_service": build_question_composer_service}[name]
    if name in {"RecommendationGeneratorService", "build_recommendation_generator_service"}:
        from app.services.llm.reporting.recommendation_generator import (
            RecommendationGeneratorService,
            build_recommendation_generator_service,
        )

        return {
            "RecommendationGeneratorService": RecommendationGeneratorService,
            "build_recommendation_generator_service": build_recommendation_generator_service,
        }[name]
    if name in {"ReportSynthesisService", "build_report_synthesis_service"}:
        from app.services.llm.reporting.report_synthesis import ReportSynthesisService, build_report_synthesis_service

        return {"ReportSynthesisService": ReportSynthesisService, "build_report_synthesis_service": build_report_synthesis_service}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
