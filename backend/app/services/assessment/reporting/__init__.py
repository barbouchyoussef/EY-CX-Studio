"""Everything that turns a finished diagnostic into the maturity report, including the
competitor benchmark -- by far the most expensive work the assessment does.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "AssessmentReportingService",
    "build_assessment_reporting_service",
    "AssessmentTraceService",
    "RecommendationService",
    "ReportBuilderService",
    "BenchmarkQueryContext",
    "BenchmarkEvidenceSignal",
    "BenchmarkService",
    "EvidenceQuality",
    "EvidenceQualityCalculator",
    "MaturityLevelCache",
    "RecommendationMetrics",
    "SemanticLeadersService",
]


_EXPORTS: dict[str, tuple[str, str]] = {
    "AssessmentReportingService": (
        "app.services.assessment.reporting.reporting_service",
        "AssessmentReportingService",
    ),
    "build_assessment_reporting_service": (
        "app.services.assessment.reporting.reporting_service",
        "build_assessment_reporting_service",
    ),
    "AssessmentTraceService": (
        "app.services.assessment.reporting.trace_service",
        "AssessmentTraceService",
    ),
    "RecommendationService": (
        "app.services.assessment.reporting.recommendation_service",
        "RecommendationService",
    ),
    "ReportBuilderService": (
        "app.services.assessment.reporting.final_report_service",
        "ReportBuilderService",
    ),
    "BenchmarkQueryContext": (
        "app.services.assessment.reporting.benchmark_service",
        "BenchmarkQueryContext",
    ),
    "BenchmarkEvidenceSignal": (
        "app.services.assessment.reporting.benchmark_service",
        "BenchmarkEvidenceSignal",
    ),
    "BenchmarkService": (
        "app.services.assessment.reporting.benchmark_service",
        "BenchmarkService",
    ),
    "EvidenceQuality": (
        "app.services.assessment.reporting.evidence_quality",
        "EvidenceQuality",
    ),
    "EvidenceQualityCalculator": (
        "app.services.assessment.reporting.evidence_quality",
        "EvidenceQualityCalculator",
    ),
    "MaturityLevelCache": (
        "app.services.assessment.reporting.maturity_level_cache",
        "MaturityLevelCache",
    ),
    "RecommendationMetrics": (
        "app.services.assessment.reporting.recommendation_metrics",
        "RecommendationMetrics",
    ),
    "SemanticLeadersService": (
        "app.services.assessment.reporting.semantic_leaders_service",
        "SemanticLeadersService",
    ),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
