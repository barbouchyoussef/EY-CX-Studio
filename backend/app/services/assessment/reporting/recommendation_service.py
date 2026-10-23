"""Writes the recommendations that close the maturity report.

Takes the scored capabilities and produces prioritised actions for the weakest ones. Two shapes
exist because the cost profile differs: a single-capability call for a targeted regeneration, and
a batched call that covers several at once for a full report.

The guards are in `Settings` rather than here: a minimum confidence below which a capability gets
no recommendation at all (guessing is worse than silence), a cap on actions per capability, and a
word budget so the report stays readable. Evidence-length thresholds decide whether a
recommendation is allowed to be specific or must stay general.
"""

import asyncio
import logging
import re
from time import perf_counter
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.text_normalization import normalize_text
from app.db.models.assessment import Assessment
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.services.assessment.reporting.evidence_quality import EvidenceQuality, EvidenceQualityCalculator
from app.services.assessment.reporting.maturity_level_cache import MaturityLevelCache
from app.services.assessment.reporting.recommendation_metrics import RecommendationMetrics
from app.schemas.recommendations import (
    AssessmentRecommendationItem,
    AssessmentRecommendationsResponse,
    BatchRecommendationGenerateResponse,
    BatchRecommendationResult,
    RecommendationOutputItem,
    RecommendationOutputsResponse,
)
from app.services.assessment.scoring.scoring_service import AssessmentScoringService
from app.services.llm.core.facade_service import LLMService
from app.services.platform import AsyncUnitOfWork

logger = logging.getLogger(__name__)


def _default_clarification_question(language: str) -> str:
    """Used when the model asks for clarification without saying what it needs."""
    if (language or "").lower().startswith("fr"):
        return "Pourriez-vous partager un exemple concret et récent ?"
    return "Can you share one concrete recent example?"


class RecommendationContext(TypedDict):
    recommendation_guideline: str | None
    priority_hint: str | None
    business_impact: str | None
    tone_hint: str | None
    supporting_notes: str | None


class RecommendationArgs(TypedDict):
    axis: str
    capability: str
    maturity_label: str
    confidence: float | None
    justification: str | None
    recommendation_guideline: str | None
    priority_hint: str | None
    business_impact: str | None
    tone_hint: str | None
    supporting_notes: str | None


class RecommendationService:
    """Owns recommendation generation, fallback handling, and persisted recommendation outputs."""

    def __init__(
        self,
        db: AsyncSession,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        llm_service: LLMService,
        scoring_service: AssessmentScoringService,
        uow: AsyncUnitOfWork,
        settings: Settings,
    ) -> None:
        self.assessments = assessments
        self.capabilities = capabilities
        self.llm = llm_service
        self.scoring = scoring_service
        self.uow = uow
        self.settings = settings
        self.maturity_levels = MaturityLevelCache(db)
        self.evidence_quality = EvidenceQualityCalculator(settings)

    async def get_recommendations(self, assessment_id: int) -> AssessmentRecommendationsResponse | None:
        self._validate_assessment_id(assessment_id)
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.capabilities.get_recommendations_for_scores(assessment_id=assessment_id)
        persisted_outputs = await self.assessments.list_recommendation_outputs(assessment_id=assessment_id)
        persisted_by_capability = {
            int(item.capability_id): item for item in persisted_outputs if item.capability_id is not None
        }
        maturity_label_by_id = await self._fetch_maturity_labels()
        generated_text_by_capability: dict[int, str] = {}

        for capability_id, persisted in persisted_by_capability.items():
            generated_text_by_capability[capability_id] = normalize_text(persisted.generated_text)

        generated_jobs = self._prepare_recommendation_jobs(
            rows=rows,
            maturity_label_by_id=maturity_label_by_id,
            excluded_capability_ids=set(persisted_by_capability),
        )
        language = getattr(assessment, "language", "en")
        generated_text_by_capability.update(await self._generate_recommendation_texts(generated_jobs, language=language))


        items: list[AssessmentRecommendationItem] = []
        for row in rows:
            if not self._is_assessed(row):
                row["recommendation_text"] = None
                items.append(AssessmentRecommendationItem(**row))
                continue
            row["recommendation_text"] = generated_text_by_capability.get(int(row["capability_id"]))
            items.append(AssessmentRecommendationItem(**row))
        return AssessmentRecommendationsResponse(assessment_id=assessment_id, items=items)

    async def generate_recommendations_batch(
        self,
        assessment_id: int,
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> BatchRecommendationGenerateResponse | None:
        self._validate_assessment_id(assessment_id)
        resolved_max_actions = max_actions_per_capability or self.settings.MAX_ACTIONS_PER_CAPABILITY
        resolved_max_words = max_words_per_capability or self.settings.MAX_WORDS_PER_CAPABILITY
        return await self._generate_recommendations_batch(
            assessment_id=assessment_id,
            language=language,
            max_actions_per_capability=resolved_max_actions,
            tone=tone,
            max_words_per_capability=resolved_max_words,
        )

    async def _generate_recommendations_batch(
        self,
        assessment_id: int,
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> BatchRecommendationGenerateResponse | None:
        """Write recommendations for every assessed capability, in one batched model call.

        Five stages: build the payload, gate out the capabilities with too little behind them,
        call the model, generate per-capability text for anything it skipped, then assemble.

        The gate and the fallback both exist because a full report cannot have holes in it: every
        assessed capability leaves this function with either a recommendation or a specific
        question back to the client.
        """
        start_time = perf_counter()
        max_actions_per_capability = max_actions_per_capability or self.settings.MAX_ACTIONS_PER_CAPABILITY
        max_words_per_capability = max_words_per_capability or self.settings.MAX_WORDS_PER_CAPABILITY
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.capabilities.get_recommendations_for_scores(assessment_id=assessment_id)
        maturity_label_by_id = await self._fetch_maturity_labels()
        maturity_level_id_by_capability = self._maturity_level_id_by_capability(rows)

        llm_items = [
            self._batch_item_from_row(row, maturity_label_by_id)
            for row in rows
            if self._is_assessed(row)
        ]
        pre_gated, llm_candidates = self._gate_batch_items(llm_items, language=language)

        try:
            generated = await self.llm.generate_recommendations_batch(
                assessment_id=assessment_id,
                items=llm_candidates,
                language=language,
                max_actions_per_capability=max_actions_per_capability,
                tone=tone,
                max_words_per_capability=max_words_per_capability,
            )
        except Exception as exc:
            logger.error("Batch recommendation LLM call failed: %s", exc, exc_info=True)
            generated = {}

        # Anything the model skipped or that the call failed on still needs text, so it is
        # generated one capability at a time rather than left blank in the report.
        fallback_jobs = {
            int(item["capability_id"]): self._recommendation_args_from_batch_item(item, tone=tone)
            for item in llm_items
            if int(item["capability_id"]) not in pre_gated and not generated.get(int(item["capability_id"]))
        }
        fallback_text_by_capability = await self._generate_recommendation_texts(fallback_jobs, language=language)

        results, output_rows = self._assemble_batch_results(
            llm_items=llm_items,
            pre_gated=pre_gated,
            generated=generated,
            fallback_text_by_capability=fallback_text_by_capability,
            maturity_level_id_by_capability=maturity_level_id_by_capability,
            language=language,
        )

        async with self.uow:
            await self.assessments.replace_recommendation_outputs(assessment_id=assessment_id, items=output_rows)
        ok_count = sum(1 for r in results if r.status == "ok")
        clarification_count = sum(1 for r in results if r.status == "needs_clarification")
        llm_success_count = sum(
            1
            for item in llm_items
            if (generated.get(int(item["capability_id"])) or {}).get("status") == "ok"
        )
        self._log_batch_metrics(
            assessment_id=assessment_id,
            llm_items=llm_items,
            pre_gated_count=len(pre_gated),
            llm_success_count=llm_success_count,
            fallback_count=len(fallback_text_by_capability),
            clarification_count=clarification_count,
            start_time=start_time,
        )
        return BatchRecommendationGenerateResponse(
            assessment_id=assessment_id,
            status="ok",
            results=results,
            ok_count=ok_count,
            clarification_count=clarification_count,
        )

    def _batch_item_from_row(self, row: dict, maturity_label_by_id: dict[int, str]) -> dict:
        """One scored capability as the payload the batch prompt expects.

        Evidence is the client's own words plus the scoring justification, capped at two entries:
        one call covers several capabilities, so each one's share of the context is small.
        """
        evidence_list: list[str] = []
        if row.get("evidence_text"):
            evidence_list.append(str(row.get("evidence_text")))
        if row.get("justification"):
            evidence_list.append(str(row.get("justification")))

        context = self.build_recommendation_context(row)
        confidence = row.get("confidence")
        return {
            "capability_id": int(row["capability_id"]),
            "axis": str(row.get("axis") or ""),
            "capability_name": str(row.get("capability_name") or ""),
            "maturity_level": (
                maturity_label_by_id.get(int(row["maturity_level_id"]))
                if row.get("maturity_level_id")
                else "Unknown"
            ),
            "confidence": float(confidence) if confidence is not None else None,
            "evidence": evidence_list[:2],
            "insight_summary": str(row.get("justification") or ""),
            "admin_guideline": context["recommendation_guideline"],
            "priority_hint": context["priority_hint"],
            "business_impact": context["business_impact"],
            "tone_hint": context["tone_hint"],
            "supporting_notes": context["supporting_notes"],
            "evidence_quality": self.evidence_quality.calculate(evidence_list).value,
        }

    def _too_thin_to_recommend(self, item: dict) -> bool:
        """Whether there is too little behind a capability to advise on it.

        Deliberately strict. A recommendation the client cannot trace back to something they
        actually said reads as invented, which costs more credibility than saying nothing, so any
        of these four is enough to hold back: no confidence score, a score under the configured
        floor, no evidence at all, or evidence the quality calculator rated weak.
        """
        confidence = item.get("confidence")
        return (
            confidence is None
            or float(confidence) < self.settings.RECOMMENDATION_MIN_CONFIDENCE
            or not (item.get("evidence") or [])
            or str(item.get("evidence_quality") or "weak") == EvidenceQuality.WEAK.value
        )

    def _gate_batch_items(
        self, llm_items: list[dict], *, language: str
    ) -> tuple[dict[int, BatchRecommendationResult], list[dict]]:
        """Split the capabilities into those worth advising on and those to ask about instead.

        Returns the already-decided clarification results keyed by capability, and the candidates
        that go to the model.
        """
        pre_gated: dict[int, BatchRecommendationResult] = {}
        llm_candidates: list[dict] = []
        for item in llm_items:
            if not self._too_thin_to_recommend(item):
                llm_candidates.append(item)
                continue
            capability_id = int(item["capability_id"])
            pre_gated[capability_id] = BatchRecommendationResult(
                capability_id=capability_id,
                status="needs_clarification",
                recommendation_text=None,
                clarification_question=self._build_clarification_question(
                    capability_name=str(item.get("capability_name") or "this capability"),
                    axis=str(item.get("axis") or ""),
                    language=language,
                ),
                evidence_used=(item.get("evidence") or [])[:2],
            )
        return pre_gated, llm_candidates

    def _assemble_batch_results(
        self,
        *,
        llm_items: list[dict],
        pre_gated: dict[int, BatchRecommendationResult],
        generated: dict,
        fallback_text_by_capability: dict[int, str],
        maturity_level_id_by_capability: dict[int, int | None],
        language: str,
    ) -> tuple[list[BatchRecommendationResult], list[dict]]:
        """Pair every capability with its final recommendation, and the rows to persist.

        Four ways a capability can end up, in the order they are checked:

          1. gated before the call, so it already has a clarification question;
          2. the model wrote a recommendation, which is stitched into one paragraph;
          3. the model answered but asked for clarification itself;
          4. the model returned nothing for it, so the per-capability fallback text is used.

        Only 2 and 4 produce something to store -- a clarification is a question to the client,
        not a report finding.
        """
        results: list[BatchRecommendationResult] = []
        output_rows: list[dict] = []

        for item in llm_items:
            capability_id = int(item["capability_id"])
            if capability_id in pre_gated:
                results.append(pre_gated[capability_id])
                continue

            ai = generated.get(capability_id)
            if ai and ai.get("status") != "ok":
                results.append(
                    BatchRecommendationResult(
                        capability_id=capability_id,
                        status="needs_clarification",
                        recommendation_text=None,
                        clarification_question=(
                            ai.get("clarification_question") or _default_clarification_question(language)
                        ),
                        evidence_used=ai.get("evidence_used") or [],
                    )
                )
                continue

            if ai:
                recommendation_text = normalize_text(
                    self._safe_concat(
                        [
                            ai.get("title"),
                            ai.get("why_this"),
                            ai.get("primary_action"),
                            ai.get("secondary_action"),
                            ai.get("expected_impact"),
                        ]
                    )
                )
            else:
                recommendation_text = fallback_text_by_capability.get(
                    capability_id,
                    self._fallback_recommendation_text(
                        recommendation_guideline=item.get("admin_guideline"),
                        business_impact=item.get("business_impact"),
                    ),
                )

            output_rows.append(
                {
                    "capability_id": capability_id,
                    "maturity_level_id": maturity_level_id_by_capability.get(capability_id),
                    "generated_text": recommendation_text,
                    "priority": item.get("priority_hint"),
                }
            )
            results.append(
                BatchRecommendationResult(
                    capability_id=capability_id,
                    status="ok",
                    recommendation_text=recommendation_text,
                    clarification_question=None,
                    evidence_used=(ai or {}).get("evidence_used") or [],
                )
            )

        return results, output_rows

    async def get_recommendation_outputs(self, assessment_id: int) -> RecommendationOutputsResponse | None:
        self._validate_assessment_id(assessment_id)
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None
        rows = await self.assessments.list_recommendation_outputs(assessment_id=assessment_id)
        items = [
            RecommendationOutputItem(
                id=int(row.id),
                capability_id=int(row.capability_id) if row.capability_id is not None else None,
                maturity_level_id=int(row.maturity_level_id) if row.maturity_level_id is not None else None,
                generated_text=str(row.generated_text),
                priority=row.priority,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return RecommendationOutputsResponse(assessment_id=assessment_id, items=items)

    async def finalize_completed_assessment(self, assessment_id: int, assessment: Assessment) -> None:
        self._validate_assessment_id(assessment_id)
        rows = await self.capabilities.get_recommendations_for_scores(assessment_id=assessment_id)
        maturity_label_by_id = await self._fetch_maturity_labels()
        maturity_number_by_id = await self._fetch_maturity_numbers()
        output_rows: list[dict] = []
        level_numbers: list[int] = []
        assessed_rows: list[dict] = []

        for row in rows:
            if not self._is_assessed(row):
                continue
            assessed_rows.append(row)
            maturity_level_id = row.get("maturity_level_id")
            if maturity_level_id is not None and int(maturity_level_id) in maturity_number_by_id:
                level_numbers.append(maturity_number_by_id[int(maturity_level_id)])

        recommendation_jobs = self._prepare_recommendation_jobs(
            rows=assessed_rows,
            maturity_label_by_id=maturity_label_by_id,
        )
        recommendation_text_by_capability = await self._generate_recommendation_texts(recommendation_jobs, language=assessment.language)
        for row in assessed_rows:
            maturity_level_id = row.get("maturity_level_id")
            capability_id = int(row["capability_id"])
            output_rows.append(
                {
                    "capability_id": row.get("capability_id"),
                    "maturity_level_id": maturity_level_id,
                    "generated_text": recommendation_text_by_capability.get(
                        capability_id,
                        self._fallback_recommendation_text(
                            recommendation_guideline=row.get("recommendation_guideline"),
                            business_impact=row.get("business_impact"),
                            language=assessment.language,
                        ),
                    ),
                    "priority": row.get("priority_hint"),
                }
            )


        await self.assessments.replace_recommendation_outputs(assessment_id=assessment_id, items=output_rows)
        overall_level_id, overall_band = await self.scoring.compute_overall_maturity_band(level_numbers=level_numbers)
        assessment.overall_maturity_level_id = overall_level_id
        assessment.overall_maturity_band = overall_band

    async def _fetch_maturity_labels(self) -> dict[int, str]:
        return await self.maturity_levels.get_labels()

    async def _fetch_maturity_numbers(self) -> dict[int, int]:
        return await self.maturity_levels.get_numbers()

    def _prepare_recommendation_jobs(
        self,
        rows: list[dict],
        maturity_label_by_id: dict[int, str],
        excluded_capability_ids: set[int] | None = None,
    ) -> dict[int, RecommendationArgs]:
        excluded_capability_ids = excluded_capability_ids or set()
        jobs: dict[int, RecommendationArgs] = {}
        for row in rows:
            if not self._is_assessed(row):
                continue

            capability_id = int(row["capability_id"])
            if capability_id in excluded_capability_ids:
                continue

            jobs[capability_id] = self._recommendation_args_from_score_row(
                row,
                maturity_label=self._maturity_label_for_row(row, maturity_label_by_id),
            )
        return jobs

    @staticmethod
    def _is_assessed(row: dict) -> bool:
        return str(row.get("assessment_status") or "not_assessed") == "assessed"

    @staticmethod
    def _maturity_label_for_row(row: dict, maturity_label_by_id: dict[int, str]) -> str:
        maturity_level_id = row.get("maturity_level_id")
        if maturity_level_id is None:
            return "Unknown"
        return maturity_label_by_id.get(int(maturity_level_id), "Unknown")

    @staticmethod
    def _maturity_level_id_by_capability(rows: list[dict]) -> dict[int, int | None]:
        mapping: dict[int, int | None] = {}
        for row in rows:
            if not row.get("capability_id"):
                continue
            maturity_level_id = row.get("maturity_level_id")
            mapping[int(row["capability_id"])] = int(maturity_level_id) if maturity_level_id is not None else None
        return mapping

    def _build_clarification_question(self, capability_name: str, axis: str, language: str = "en") -> str:
        normalized_axis = axis.strip().upper()
        is_french = (language or "").lower().startswith("fr")
        if is_french:
            cap_key = normalize_text(capability_name).lower().strip()
            labels = {
                "decision-making": "la prise de décision",
                "ownership and governance": "l'ownership et la gouvernance",
                "feedback collection": "la collecte des retours clients",
                "use of insights": "l'exploitation des insights",
                "channel consistency": "la cohérence multicanale",
                "journey visibility": "la visibilité des parcours",
                "measurement and continuous improvement": "la mesure et l'amélioration continue",
                "acting on pain points": "le traitement des points de douleur",
                "cx culture": "la culture CX",
            }
            fr_cap = labels.get(cap_key, capability_name)
            templates = {
                "MANAGE": (
                    f"Pour mieux évaluer '{fr_cap}', pourriez-vous partager un exemple récent indiquant qui était responsable, "
                    "quel processus a été suivi et quel résultat a été obtenu ?"
                ),
                "ANALYZE": (
                    f"Pour mieux évaluer '{fr_cap}', pourriez-vous décrire un cas précis où les retours clients "
                    "ont été collectés, analysés et traduits en action ?"
                ),
                "IMPROVE": (
                    f"Pour mieux évaluer '{fr_cap}', pourriez-vous partager un cas concret où un point de douleur "
                    "a été identifié, priorisé et amélioré ?"
                ),
            }
            return templates.get(
                normalized_axis,
                f"Pourriez-vous partager un exemple concret et récent concernant '{fr_cap}' avec le responsable, l'action et le résultat ?",
            )

        templates = {
            "MANAGE": (
                f"To better assess {capability_name}, could you share one recent example of who was responsible, "
                "what process was followed, and what outcome was achieved?"
            ),
            "ANALYZE": (
                f"To better assess {capability_name}, could you describe one specific instance where customer "
                "feedback was collected, reviewed, and translated into an action?"
            ),
            "IMPROVE": (
                f"To better assess {capability_name}, could you share one concrete case where a pain point was "
                "identified, prioritized, and improved?"
            ),
        }
        return templates.get(
            normalized_axis,
            f"Could you share one recent concrete example about {capability_name} with owner, action, and outcome?",
        )

    def _log_batch_metrics(
        self,
        assessment_id: int,
        llm_items: list[dict],
        pre_gated_count: int,
        llm_success_count: int,
        fallback_count: int,
        clarification_count: int,
        start_time: float,
    ) -> None:
        metrics = RecommendationMetrics(
            assessment_id=assessment_id,
            total_capabilities=len(llm_items),
            pre_gated_count=pre_gated_count,
            llm_success_count=llm_success_count,
            fallback_count=fallback_count,
            clarification_count=clarification_count,
            total_duration_ms=int((perf_counter() - start_time) * 1000),
            evidence_quality_distribution=self._evidence_quality_distribution(llm_items),
        )
        logger.info("Recommendation batch completed", extra=metrics.to_log_dict())

    @staticmethod
    def _evidence_quality_distribution(llm_items: list[dict]) -> dict[str, int]:
        distribution = {
            EvidenceQuality.WEAK.value: 0,
            EvidenceQuality.MEDIUM.value: 0,
            EvidenceQuality.STRONG.value: 0,
        }
        for item in llm_items:
            key = str(item.get("evidence_quality") or EvidenceQuality.WEAK.value)
            distribution[key] = distribution.get(key, 0) + 1
        return distribution

    @staticmethod
    def _validate_assessment_id(assessment_id: int) -> None:
        if assessment_id <= 0:
            raise ValueError("assessment_id must be positive")

    @staticmethod
    def build_recommendation_context(row: dict) -> RecommendationContext:
        recommendation_guideline = normalize_text(str(row.get("recommendation_guideline") or "")) or None
        priority_hint = normalize_text(str(row.get("priority_hint") or "")) or None
        business_impact = normalize_text(str(row.get("business_impact") or "")) or None
        tone_hint = normalize_text(str(row.get("tone_hint") or "")) or "balanced"

        supporting_parts: list[str] = []
        consultant_note = normalize_text(str(row.get("consultant_note") or ""))
        if consultant_note:
            supporting_parts.append(consultant_note)
        initiative_suggestions = normalize_text(str(row.get("initiative_suggestions") or ""))
        if initiative_suggestions:
            supporting_parts.append(f"Suggested initiatives: {initiative_suggestions}")
        evidence_to_cite = normalize_text(str(row.get("evidence_to_cite") or ""))
        if evidence_to_cite and not row.get("justification"):
            supporting_parts.append(f"Reference pattern: {evidence_to_cite}")

        supporting_notes = " | ".join(part for part in supporting_parts[:2] if part) or None
        return {
            "recommendation_guideline": recommendation_guideline,
            "priority_hint": priority_hint,
            "business_impact": business_impact,
            "tone_hint": tone_hint,
            "supporting_notes": supporting_notes,
        }

    def _recommendation_args_from_score_row(self, row: dict, maturity_label: str) -> RecommendationArgs:
        recommendation_context = self.build_recommendation_context(row)
        return {
            "axis": str(row.get("axis") or ""),
            "capability": str(row.get("capability_name") or ""),
            "maturity_label": maturity_label,
            "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
            "justification": self._evidence_only_justification(row),
            "recommendation_guideline": recommendation_context["recommendation_guideline"],
            "priority_hint": recommendation_context["priority_hint"],
            "business_impact": recommendation_context["business_impact"],
            "tone_hint": recommendation_context["tone_hint"],
            "supporting_notes": recommendation_context["supporting_notes"],
        }

    def _recommendation_args_from_batch_item(self, row: dict, tone: str) -> RecommendationArgs:
        return {
            "axis": str(row.get("axis") or ""),
            "capability": str(row.get("capability_name") or ""),
            "maturity_label": str(row.get("maturity_level") or "Unknown"),
            "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
            "justification": self._evidence_only_batch_justification(row),
            "recommendation_guideline": row.get("admin_guideline"),
            "priority_hint": row.get("priority_hint"),
            "business_impact": row.get("business_impact"),
            "tone_hint": row.get("tone_hint") or tone,
            "supporting_notes": row.get("supporting_notes"),
        }

    async def _generate_recommendation_texts(self, jobs: dict[int, RecommendationArgs], language: str = "en") -> dict[int, str]:
        if not jobs:
            return {}

        async def run_job(capability_id: int, payload: RecommendationArgs) -> tuple[int, str]:
            return capability_id, await self._generate_recommendation_safe(**payload, language=language)


        task_results = await asyncio.gather(
            *(run_job(capability_id, payload) for capability_id, payload in jobs.items()),
            return_exceptions=True,
        )

        generated: dict[int, str] = {}
        for result in task_results:
            if isinstance(result, Exception):
                logger.error(
                    "Parallel recommendation task failed: %s",
                    result,
                    exc_info=(type(result), result, result.__traceback__),
                )
                continue
            capability_id, recommendation_text = result
            generated[capability_id] = recommendation_text
        return generated

    async def _generate_recommendation_safe(
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
        supporting_notes: str | None,
        language: str = "en",
    ) -> str:
        safe_justification = self._sanitize_recommendation_evidence(justification)
        try:
            recommendation = await self.llm.generate_recommendation(
                axis=axis,
                capability=capability,
                maturity_label=maturity_label,
                confidence=confidence,
                justification=safe_justification,
                recommendation_guideline=recommendation_guideline,
                priority_hint=priority_hint,
                business_impact=business_impact,
                tone_hint=tone_hint,
                supporting_notes=supporting_notes,
                language=language,
            )
            return normalize_text(recommendation) or self._fallback_recommendation_text(
                recommendation_guideline=recommendation_guideline,
                business_impact=business_impact,
                language=language,
            )
        except Exception as exc:
            logger.error("Recommendation generation failed for %s: %s", capability, exc, exc_info=True)
            return self._fallback_recommendation_text(
                recommendation_guideline=recommendation_guideline,
                business_impact=business_impact,
                language=language,
            )


    def _evidence_only_justification(self, row: dict) -> str | None:
        parts = [
            self._sanitize_recommendation_evidence(row.get("evidence_text")),
            self._sanitize_recommendation_evidence(row.get("insight_justification")),
            self._sanitize_recommendation_evidence(row.get("justification")),
        ]
        return normalize_text(" ".join(part for part in parts if part)) or None

    def _evidence_only_batch_justification(self, row: dict) -> str | None:
        evidence_items = row.get("evidence") or []
        evidence_text = " ".join(str(item) for item in evidence_items if item)
        parts = [
            self._sanitize_recommendation_evidence(evidence_text),
            self._sanitize_recommendation_evidence(row.get("insight_summary")),
        ]
        return normalize_text(" ".join(part for part in parts if part)) or None

    def _sanitize_recommendation_evidence(self, value: object) -> str | None:
        text = normalize_text(str(value or ""))
        if not text:
            return None
        if self._is_meta_conversation_evidence(text):
            return (
                "Evidence quality is limited because the respondent asked for clarification "
                "or did not provide business evidence."
            )
        return text

    @staticmethod
    def _is_meta_conversation_evidence(text: str) -> bool:
        lowered = text.lower()
        meta_patterns = (
            r"\brepeated clarification request\b",
            r"\basked for clarification\b",
            r"\bin simple terms\b",
            r"\bexplain\b",
            r"\bdid not provide assessable business evidence\b",
            r"\blow-quality\b",
            r"\bnon-interpretable\b",
        )
        return any(re.search(pattern, lowered) for pattern in meta_patterns)

    def _fallback_recommendation_text(
        self,
        recommendation_guideline: str | None,
        business_impact: str | None,
        language: str = "en",
    ) -> str:
        is_french = (language or "").lower().startswith("fr")
        default_guide = "La génération de recommandation est temporairement indisponible" if is_french else "Recommendation generation is temporarily unavailable"
        return normalize_text(
            self._safe_concat(
                [
                    recommendation_guideline or default_guide,
                    business_impact,
                ]
            )
        )


    def _safe_concat(self, parts: list[str | None]) -> str:
        safe_parts = []
        for part in parts:
            if part and str(part).strip():
                clean_part = str(part).strip()
                if clean_part[-1] not in ".!?":
                    clean_part += "."
                safe_parts.append(clean_part)
        return " ".join(safe_parts)


