from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.scoring import MaturityScoring
from app.core.text_normalization import normalize_text
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository


class AssessmentScoringService:
    """Owns scoring persistence, maturity math, and post-LLM evidence gating."""

    def __init__(
        self,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        settings: Settings,
    ) -> None:
        self.assessments = assessments
        self.capabilities = capabilities
        self.settings = settings

    def resolve_confidence(self, covered_ids: list[int], confidence: float | None) -> float:
        if confidence is not None:
            return float(confidence)
        if covered_ids:
            return self.settings.scoring_default_confidence_if_covered
        return self.settings.scoring_default_confidence_if_not_covered

    async def persist_scoring(
        self,
        assessment_id: int,
        covered_ids: list[int],
        confidence: float,
        maturity_level_by_id: dict[int, int],
        rationale_by_id: dict[int, str],
    ) -> None:
        await self.capabilities.mark_covered(
            assessment_id=assessment_id,
            covered_ids=covered_ids,
            confidence=confidence,
            maturity_level_by_id=maturity_level_by_id,
            rationale_by_id=rationale_by_id,
        )

    async def persist_insights(
        self,
        assessment_id: int,
        covered_ids: list[int],
        maturity_level_by_id: dict[int, int],
        confidence: float,
        rationale_by_id: dict[int, str],
        evidence_by_id: dict[int, str],
    ) -> None:
        for capability_id in covered_ids:
            evidence = (evidence_by_id.get(capability_id) or "").strip()
            rationale = (rationale_by_id.get(capability_id) or "").strip()
            insight_text = rationale or evidence or "Capability assessed from latest response."
            if evidence and rationale:
                insight_text = f"{rationale} Evidence: {evidence}"
            await self.assessments.add_insight(
                assessment_id=assessment_id,
                capability_id=capability_id,
                insight_text=insight_text,
                maturity_level_id=maturity_level_by_id.get(capability_id),
                confidence=confidence,
                justification=rationale or None,
                evidence_text=evidence or None,
            )

    def apply_followup_gating(
        self,
        covered_ids: list[int],
        confidence_by_id: dict[int, float],
        evidence_by_id: dict[int, str],
        rationale_by_id: dict[int, str],
        maturity_level_number_by_id: dict[int, int],
        is_specific_and_actionable_by_id: dict[int, bool],
    ) -> list[int]:
        if not covered_ids:
            return []

        ranked: list[tuple[int, float, int, int]] = []
        for capability_id in covered_ids:
            confidence = float(
                confidence_by_id.get(
                    capability_id,
                    self.settings.scoring_default_confidence_if_covered,
                )
            )
            evidence = normalize_text(evidence_by_id.get(capability_id) or "").strip()
            rationale = normalize_text(rationale_by_id.get(capability_id) or "").strip()
            has_support = bool(evidence or rationale)
            is_level_one = int(maturity_level_number_by_id.get(capability_id, 0) or 0) == 1

            if not bool(is_specific_and_actionable_by_id.get(capability_id, False)):
                continue
            if not has_support:
                continue
            if not is_level_one and confidence < self.settings.scoring_min_confidence_to_score:
                continue
            if (
                not is_level_one
                and len(evidence) < self.settings.scoring_min_evidence_text_len
                and len(rationale) < self.settings.scoring_min_rationale_text_len
            ):
                continue
            ranked.append((capability_id, confidence, len(evidence), len(rationale)))

        if not ranked:
            return []

        ranked.sort(key=lambda item: (item[1], item[2] + item[3]), reverse=True)
        return [
            capability_id
            for capability_id, _, _, _ in ranked[: self.settings.scoring_max_capabilities_per_answer]
        ]

    async def compute_overall_maturity_band(self, level_numbers: list[int]) -> tuple[int | None, str | None]:
        if not level_numbers:
            return None, None
        average = sum(level_numbers) / len(level_numbers)
        target_level, target_band = MaturityScoring.target_level_from_average(
            average=average,
            basic_threshold=self.settings.maturity_average_basic_threshold,
            established_threshold=self.settings.maturity_average_established_threshold,
        )

        row = await self.assessments.get_maturity_level_by_number(target_level)
        if row is None:
            return None, target_band
        return int(row.id), target_band


def build_assessment_scoring_service(
    db: AsyncSession,
    assessments: AssessmentRepository | None = None,
    capabilities: CapabilityRepository | None = None,
    settings: Settings | None = None,
) -> AssessmentScoringService:
    resolved_settings = settings or get_settings()
    resolved_assessments = assessments or AssessmentRepository(db)
    resolved_capabilities = capabilities or CapabilityRepository(db)
    return AssessmentScoringService(
        assessments=resolved_assessments,
        capabilities=resolved_capabilities,
        settings=resolved_settings,
    )
