from enum import Enum

from app.core.config import Settings


class EvidenceQuality(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class EvidenceQualityCalculator:
    """Classifies recommendation evidence strength using configured thresholds."""

    def __init__(self, settings: Settings) -> None:
        self.strong_min_chars = settings.recommendation_strong_evidence_min_chars
        self.medium_min_chars = settings.recommendation_medium_evidence_min_chars

    def calculate(self, evidence_list: list[str]) -> EvidenceQuality:
        if not evidence_list:
            return EvidenceQuality.WEAK

        if len(evidence_list) >= 2 and all(
            len(evidence.strip()) >= self.strong_min_chars for evidence in evidence_list
        ):
            return EvidenceQuality.STRONG

        if any(len(evidence.strip()) >= self.medium_min_chars for evidence in evidence_list):
            return EvidenceQuality.MEDIUM

        return EvidenceQuality.WEAK
