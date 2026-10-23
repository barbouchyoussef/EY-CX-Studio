"""Model calls that produce report prose: synthesis and recommendations.
"""

from app.services.llm.reporting.recommendation_generator import (
    RecommendationGeneratorService,
    build_recommendation_generator_service,
)
from app.services.llm.reporting.report_synthesis import ReportSynthesisService, build_report_synthesis_service

__all__ = [
    "RecommendationGeneratorService",
    "ReportSynthesisService",
    "build_recommendation_generator_service",
    "build_report_synthesis_service",
]
