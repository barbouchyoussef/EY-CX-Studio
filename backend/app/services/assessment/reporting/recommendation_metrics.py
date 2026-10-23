from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationMetrics:
    assessment_id: int
    total_capabilities: int
    pre_gated_count: int
    llm_success_count: int
    fallback_count: int
    clarification_count: int
    total_duration_ms: int
    evidence_quality_distribution: dict[str, int]

    def to_log_dict(self) -> dict[str, int | float | dict[str, int]]:
        total = max(self.total_capabilities, 1)
        return {
            "assessment_id": self.assessment_id,
            "total_capabilities": self.total_capabilities,
            "pre_gated_count": self.pre_gated_count,
            "pre_gated_pct": round((self.pre_gated_count / total) * 100, 1),
            "llm_success_count": self.llm_success_count,
            "fallback_count": self.fallback_count,
            "clarification_count": self.clarification_count,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_per_capability_ms": int(self.total_duration_ms / total),
            "evidence_quality_distribution": self.evidence_quality_distribution,
        }
