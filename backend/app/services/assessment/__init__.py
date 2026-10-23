"""The maturity diagnostic: a guided conversation that scores nine CX capabilities.

Split by phase -- `conversation` runs the interview, `scoring` grades answers, `state` tracks
progress, `reporting` builds the final report and its competitor benchmark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "AnswerFlowService",
    "AssessmentConversationService",
    "AssessmentReportingService",
    "AssessmentScoringService",
    "AssessmentService",
    "AssessmentStateService",
    "BenchmarkEvidenceSignal",
    "BenchmarkQueryContext",
    "BenchmarkService",
    "MemorySyncService",
    "QuestionFlowService",
    "build_assessment_conversation_service",
    "build_assessment_reporting_service",
    "build_assessment_scoring_service",
    "build_assessment_service",
    "build_answer_flow_service",
    "build_memory_sync_service",
    "build_question_flow_service",
]

if TYPE_CHECKING:
    from app.services.assessment.conversation.answer_flow_service import AnswerFlowService, build_answer_flow_service
    from app.services.assessment.reporting.benchmark_service import (
        BenchmarkEvidenceSignal,
        BenchmarkQueryContext,
        BenchmarkService,
    )
    from app.services.assessment.conversation.memory_sync_service import MemorySyncService, build_memory_sync_service
    from app.services.assessment.conversation.question_flow_service import QuestionFlowService, build_question_flow_service
    from app.services.assessment.conversation.service import AssessmentConversationService
    from app.services.assessment.reporting.reporting_service import AssessmentReportingService, build_assessment_reporting_service
    from app.services.assessment.scoring.scoring_service import AssessmentScoringService, build_assessment_scoring_service
    from app.services.assessment.state.state_service import AssessmentStateService
    from app.services.assessment.lifecycle_service import AssessmentService
    from app.services.assessment.factory import build_assessment_conversation_service, build_assessment_service


def __getattr__(name: str) -> Any:
    if name in {"AnswerFlowService", "build_answer_flow_service"}:
        from app.services.assessment.conversation.answer_flow_service import AnswerFlowService, build_answer_flow_service

        return {"AnswerFlowService": AnswerFlowService, "build_answer_flow_service": build_answer_flow_service}[name]
    if name in {"BenchmarkEvidenceSignal", "BenchmarkQueryContext", "BenchmarkService"}:
        from app.services.assessment.reporting.benchmark_service import (
            BenchmarkEvidenceSignal,
            BenchmarkQueryContext,
            BenchmarkService,
        )

        return {
            "BenchmarkEvidenceSignal": BenchmarkEvidenceSignal,
            "BenchmarkQueryContext": BenchmarkQueryContext,
            "BenchmarkService": BenchmarkService,
        }[name]
    if name in {"MemorySyncService", "build_memory_sync_service"}:
        from app.services.assessment.conversation.memory_sync_service import MemorySyncService, build_memory_sync_service

        return {"MemorySyncService": MemorySyncService, "build_memory_sync_service": build_memory_sync_service}[name]
    if name in {"QuestionFlowService", "build_question_flow_service"}:
        from app.services.assessment.conversation.question_flow_service import QuestionFlowService, build_question_flow_service

        return {"QuestionFlowService": QuestionFlowService, "build_question_flow_service": build_question_flow_service}[name]
    if name in {"build_assessment_conversation_service", "build_assessment_service"}:
        from app.services.assessment.factory import build_assessment_conversation_service, build_assessment_service

        return {
            "build_assessment_conversation_service": build_assessment_conversation_service,
            "build_assessment_service": build_assessment_service,
        }[name]
    if name in {"AssessmentConversationService"}:
        from app.services.assessment.conversation.service import AssessmentConversationService

        return AssessmentConversationService
    if name in {"AssessmentReportingService", "build_assessment_reporting_service"}:
        from app.services.assessment.reporting.reporting_service import AssessmentReportingService, build_assessment_reporting_service

        return {
            "AssessmentReportingService": AssessmentReportingService,
            "build_assessment_reporting_service": build_assessment_reporting_service,
        }[name]
    if name in {"AssessmentScoringService", "build_assessment_scoring_service"}:
        from app.services.assessment.scoring.scoring_service import AssessmentScoringService, build_assessment_scoring_service

        return {
            "AssessmentScoringService": AssessmentScoringService,
            "build_assessment_scoring_service": build_assessment_scoring_service,
        }[name]
    if name in {"AssessmentStateService"}:
        from app.services.assessment.state.state_service import AssessmentStateService

        return {
            "AssessmentStateService": AssessmentStateService,
        }[name]
    if name in {"AssessmentService"}:
        from app.services.assessment.lifecycle_service import AssessmentService

        return AssessmentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
