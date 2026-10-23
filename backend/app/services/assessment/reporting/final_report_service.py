"""Assembles the final maturity report from everything the diagnostic produced.

`ReportBuilderService` is the composition point of the assessment module: scores, capability
evidence, recommendations and the competitor benchmark are gathered here into the single payload
the report UI and the PDF export both render.

Two things in this file are about resource control rather than content:

  * the **leaders-snapshot semaphore**, which bounds how many competitor-benchmark jobs run at
    once. That work is the most expensive thing the assessment does -- many web searches plus a
    model pass per candidate -- so it is deliberately throttled rather than run per request;
  * the `debug_*` methods, which expose each stage of the benchmark separately. They exist
    because the benchmark is the hardest part of the report to diagnose from its output alone.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.scoring import MaturityScoring
from app.core.text_normalization import clean_optional_text, normalize_text
from app.services.assessment.reporting.maturity_level_cache import MaturityLevelCache
from app.db.session import SessionLocal
from app.domain.constants import ASSESSMENT_STATUS_COMPLETED
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.schemas.final_report import (
    FinalReportAxisItem,
    FinalReportBenchmarkItem,
    FinalReportCapabilityItem,
    FinalReportCompetitiveCompetitor,
    FinalReportCompetitiveEvidenceLink,
    FinalReportCompetitiveStage,
    FinalReportHero,
    FinalReportLeaderEvidenceLink,
    FinalReportLeaderItem,
    FinalReportLeadersSnapshotMetrics,
    FinalReportLeadersSnapshot,
    FinalReportQuickWinItem,
    FinalReportQuickWinsTimeline,
    FinalReportWorkingMissingAxis,
    FinalReportWorkingMissingItem,
    FinalReportResponse,
    FinalReportSummary,
    FinalReportThemeItem,
)
from app.services.assessment.scoring.scoring_service import AssessmentScoringService
from app.services.assessment.scoring.scoring_service import build_assessment_scoring_service
from app.services.assessment.reporting.benchmark_service import (
    BenchmarkEvidenceSignal,
    BenchmarkQueryContext,
    BenchmarkService,
)
from app.services.assessment.reporting.telecom_discovery_leaders_service import TelecomDiscoveryLeadersService
from app.services.assessment.reporting.semantic_leaders_service import SemanticLeadersService
from app.services.llm.core.facade_service import LLMService, build_llm_service
from app.services.llm.prompts.templates import language_directive
from app.services.llm.utils import extract_json
from app.services.platform import AsyncUnitOfWork

logger = logging.getLogger(__name__)

LEADERS_SNAPSHOT_STATUS_PENDING = "pending"
LEADERS_SNAPSHOT_STATUS_RUNNING = "running"
LEADERS_SNAPSHOT_STATUS_COMPLETED = "completed"
LEADERS_SNAPSHOT_STATUS_FAILED = "failed"

_leaders_snapshot_tasks: dict[int, asyncio.Task[None]] = {}
_leaders_snapshot_tasks_lock = asyncio.Lock()
_leaders_snapshot_job_semaphore: asyncio.Semaphore | None = None
QUICK_WIN_TIMELINE_LABELS = ("Week 1", "Month 1", "Month 2", "Month 3-4")
QUICK_WIN_TIMELINE_LABELS_FR = ("Semaine 1", "Mois 1", "Mois 2", "Mois 3-4")


def _get_leaders_snapshot_job_semaphore(settings: Settings) -> asyncio.Semaphore:
    global _leaders_snapshot_job_semaphore
    if _leaders_snapshot_job_semaphore is None:
        _leaders_snapshot_job_semaphore = asyncio.Semaphore(settings.benchmark_max_concurrent_jobs)
    return _leaders_snapshot_job_semaphore


def _build_report_builder_service(db: AsyncSession, settings: Settings) -> "ReportBuilderService":
    assessments = AssessmentRepository(db)
    capabilities = CapabilityRepository(db)
    llm = build_llm_service(settings=settings)
    benchmarks = BenchmarkService(db=db)
    uow = AsyncUnitOfWork(db)
    scoring = build_assessment_scoring_service(
        db,
        assessments=assessments,
        capabilities=capabilities,
        settings=settings,
    )
    return ReportBuilderService(
        db=db,
        assessments=assessments,
        capabilities=capabilities,
        llm_service=llm,
        benchmark_service=benchmarks,
        scoring_service=scoring,
        uow=uow,
        settings=settings,
    )

# ── Quick-win owners ────────────────────────────────────────────────────────────────────────
# An authored owner hint is free text. These map it onto a standard job title, in report language.

_QUICK_WIN_OWNER_TITLES: dict[str, dict[str, str]] = {
    "cx": {"fr": "Responsable Expérience Client", "en": "Customer Experience Lead"},
    "insights": {"fr": "Responsable Insights Client", "en": "Insights Lead"},
    "operations": {"fr": "Responsable Opérations", "en": "Operations Lead"},
    "support": {"fr": "Responsable Support", "en": "Support Lead"},
    "transformation": {"fr": "Responsable Transformation", "en": "Transformation Lead"},
    "marketing": {"fr": "Responsable Marketing", "en": "Marketing Lead"},
    "digital": {"fr": "Responsable Digital", "en": "Digital Lead"},
    "people": {"fr": "Responsable Ressources Humaines", "en": "People Lead"},
    "product": {"fr": "Responsable Produit", "en": "Product Lead"},
}

# Which words in a hint point at which role. Ordered: the first match wins, so the more specific
# readings come before the ones that would otherwise swallow them.
_QUICK_WIN_OWNER_TERMS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cx", "customer experience"), "cx"),
    (("insight", "analytics", "data"), "insights"),
    (("operation", "service operation"), "operations"),
    (("support",), "support"),
    (("transform", "program"), "transformation"),
    (("market",), "marketing"),
    (("digital",), "digital"),
    (("people", "hr", "training", "learning"), "people"),
    (("product",), "product"),
)

# A hint naming only one of these says nothing about who actually does the work.
_VAGUE_OWNERS = frozenset({"leadership", "management", "team", "business", "company"})
# Past this, the hint is a description rather than a job title.
_MAX_OWNER_WORDS = 4

_GOVERNANCE_CAPABILITY_PHRASES = (
    "ownership and governance",
    "governance",
    "decision-making",
    "decision making",
)
# Naming any of these means the hint picked a function deliberately, so it is left alone even on a
# governance capability.
_FUNCTIONAL_OWNER_TERMS = (
    "operation",
    "support",
    "marketing",
    "digital",
    "product",
    "people",
    "insight",
    "analytic",
)


def _is_governance_capability(capability: str) -> bool:
    """Whether a capability is about who decides and who owns, rather than about doing the work."""
    text = normalize_text(capability).lower()
    return any(phrase in text for phrase in _GOVERNANCE_CAPABILITY_PHRASES)


# Capabilities sent to the competitor benchmark. It is the most expensive thing the report does,
# so it runs against the worst few rather than all nine.
_MAX_BENCHMARK_PAIN_POINTS = 3

# Answers and insights passed to the model as evidence for one quick win. A handful is context;
# more is the whole transcript, which buries the action being rewritten.
_MAX_EVIDENCE_SNIPPETS = 3

# How many quick wins the report proposes. Enough to look like a plan, few enough to be done.
_MAX_QUICK_WINS = 4

# ── Axis panel copy ─────────────────────────────────────────────────────────────────────────
# Each axis panel carries three sentences. The subtitle depends on how mature the axis scored;
# the intro and the stat note depend on the part the axis plays in the report -- the strongest
# one, the priority one, or one of the rest. `{axis_label}` is the axis name as displayed.

_AXIS_BAND_SUBTITLE: dict[str, dict[str, str]] = {
    "advanced": {
        "fr": "L'axe {axis_label} fonctionne comme un système fiable, et non pas seulement comme une bonne intention.",
        "en": "{axis_label} is operating as a reliable system, not just a good intention.",
    },
    "established": {
        "fr": "L'axe {axis_label} fait preuve d'une discipline visible, mais l'exécution n'est pas encore pleinement systématique.",
        "en": "{axis_label} shows visible discipline, but execution is not fully systematic yet.",
    },
    "basic": {
        "fr": "L'axe {axis_label} montre des signaux précoces, mais le modèle opérationnel reste fragile.",
        "en": "{axis_label} shows early signals, but the operating model is still fragile.",
    },
    "unknown": {
        "fr": "L'axe {axis_label} ne présente pas encore assez de preuves pour démontrer un modèle opérationnel stable.",
        "en": "{axis_label} does not yet have enough evidence to show a stable operating model.",
    },
}

_AXIS_ROLE_INTRO: dict[str, dict[str, str]] = {
    "strongest": {
        "fr": "L'axe {axis_label} est actuellement le point fort du profil. "
              "Il présente les preuves opérationnelles les plus claires de l'évaluation.",
        "en": "{axis_label} is currently the strongest part of the respondent profile. "
              "It already shows the clearest operating evidence in the assessment.",
    },
    "priority": {
        "fr": "L'axe {axis_label} est la priorité absolue actuellement. "
              "Il nécessite des routines plus solides, une visibilité partagée et un suivi plus systématique.",
        "en": "{axis_label} is the main priority axis right now. "
              "It needs stronger routines, shared visibility, and more repeatable follow-through.",
    },
    "balanced": {
        "fr": "L'axe {axis_label} se situe entre les forces actuelles et les écarts à combler. "
              "L'objectif est de maintenir ce qui fonctionne et de rendre les routines plus cohérentes.",
        "en": "{axis_label} sits between current strengths and current gaps. "
              "The focus here is to keep what is working and make the weaker routines more consistent.",
    },
}

_AXIS_ROLE_STAT_NOTE: dict[str, dict[str, str]] = {
    "strongest": {
        "fr": "Il s'agit de l'axe le plus mature dans le rapport actuel et de la meilleure base sur laquelle s'appuyer.",
        "en": "This is the most mature axis in the current report and the best foundation to build on.",
    },
    "priority": {
        "fr": "C'est l'axe sur lequel le prochain gain de maturité est le plus susceptible d'être réalisé.",
        "en": "This is the axis where the next maturity gain is most likely to come from.",
    },
    "balanced": {
        "fr": "Cet axe présente des signaux significatifs, mais nécessite encore plus de cohérence et de preuves.",
        "en": "This axis has meaningful signals, but it still needs stronger consistency and proof.",
    },
}


def _maturity_band_key(maturity_band: str) -> str:
    """Which band an axis scored in, tolerant of how the band was labelled.

    Substring matching rather than equality because the band arrives as display text -- "Advanced",
    "Avancé", "Intermédiaire" -- and a report is generated in either language. Anything
    unrecognised, including a not-yet-scored axis, falls to "unknown".
    """
    band = (maturity_band or "").lower().strip()
    if "adv" in band or "avan" in band:
        return "advanced"
    if "est" in band or "étab" in band or "interm" in band:
        return "established"
    if "bas" in band:
        return "basic"
    return "unknown"


# ── Hero copy for the strongest and weakest axis ────────────────────────────────────────────
# One sentence per axis per role, in both languages. Data rather than branching, so adding an
# axis or reworking a sentence is an edit here and nothing else.

_AXIS_SHORT_COPY: dict[str, dict[str, dict[str, str]]] = {
    "manage": {
        "strongest": {
            "en": "You have structured governance, clear ownership, and consistent processes.",
            "fr": "Vous disposez d'une gouvernance structurée, de responsabilités claires et de processus établis.",
        },
        "priority": {
            "en": "Establish formal governance and clear ownership for customer experience.",
            "fr": "Formaliser la gouvernance et définir des responsabilités claires pour l'expérience client.",
        },
    },
    "analyze": {
        "strongest": {
            "en": "Customer data and feedback are consistently turned into actionable insights.",
            "fr": "Les données et retours clients sont systématiquement transformés en insights actionnables.",
        },
        "priority": {
            "en": "Build consistent customer listening channels and structured insight generation.",
            "fr": "Développer des canaux d'écoute client homogènes et structurer la génération d'insights.",
        },
    },
    "improve": {
        "strongest": {
            "en": "Improvements are systematically implemented and embedded into operations.",
            "fr": "Les améliorations sont systématiquement déployées et intégrées aux opérations.",
        },
        "priority": {
            "en": "Take consistent action on feedback and close the customer loop systematically.",
            "fr": "Agir sur les retours d'expérience et boucler la boucle client de manière systématique.",
        },
    },
}

# How many of each theme the report shows.
_MAX_THEMES = 3


def _axis_short_copy(axis: str | None, role: str, language: str) -> str | None:
    """The one-line description for an axis, or None when there is no copy for it."""
    key = (axis or "").lower().strip()
    return _AXIS_SHORT_COPY.get(key, {}).get(role, {}).get(language)


@dataclass(frozen=True)
class _ReportThemes:
    """The strengths and pain points shown in the report, and how many were available.

    The counts are the full candidate totals, not the displayed slice: the summary reports how
    many strengths the assessment found, while the report body shows at most three.
    """

    strengths: list["FinalReportThemeItem"]
    pain_points: list["FinalReportThemeItem"]
    strength_candidates: list["FinalReportCapabilityItem"]
    pain_candidates: list["FinalReportCapabilityItem"]


def _theme_item(item: "FinalReportCapabilityItem") -> "FinalReportThemeItem":
    """A capability as it appears in the strengths or pain-points list."""
    return FinalReportThemeItem(
        axis=item.axis,
        capability=item.capability,
        maturity_band=item.maturity_band,
        rationale=item.rationale,
        recommendation=item.recommendation,
        priority=item.priority,
    )


def _select_report_themes(capabilities: list["FinalReportCapabilityItem"]) -> _ReportThemes:
    """Pick what the report presents as strengths and as pain points.

    Advanced capabilities are the strengths. When there are none, the report falls back to the
    best-evidenced Established ones rather than showing an empty section -- ranked by confidence,
    because with nothing Advanced to show, how well-supported a claim is decides which is worth
    making.
    """
    strength_candidates = [c for c in capabilities if c.maturity_band == "Advanced"]
    if not strength_candidates:
        established = sorted(
            (c for c in capabilities if c.maturity_band == "Established"),
            key=lambda item: float(item.confidence or 0.0),
            reverse=True,
        )
        strength_candidates = established[:_MAX_THEMES]

    pain_candidates = [c for c in capabilities if c.maturity_band == "Basic"]
    return _ReportThemes(
        strengths=[_theme_item(c) for c in strength_candidates[:_MAX_THEMES]],
        pain_points=[_theme_item(c) for c in pain_candidates[:_MAX_THEMES]],
        strength_candidates=strength_candidates,
        pain_candidates=pain_candidates,
    )


class ReportBuilderService:
    """Owns final report assembly, report synthesis caching, and report presentation helpers."""

    def __init__(
        self,
        db: AsyncSession,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        llm_service: LLMService,
        benchmark_service: BenchmarkService,
        scoring_service: AssessmentScoringService,
        uow: AsyncUnitOfWork,
        settings: Settings,
    ) -> None:
        self.db = db
        self.assessments = assessments
        self.capabilities = capabilities
        self.llm = llm_service
        self.benchmarks = benchmark_service
        self.scoring = scoring_service
        self.uow = uow
        self.settings = settings
        # Maturity levels are fixed reference data read several times while a report is built.
        # The cache loads them once per request; both call sites below used to run their own
        # `select(MaturityLevel)` and rebuild the same dict by hand.
        self.maturity_levels = MaturityLevelCache(db)

    def _score_axes(
        self, capability_rows: list[dict], maturity_number_by_id: dict[int, int]
    ) -> list["FinalReportAxisItem"]:
        """Score each axis from the maturity levels of its assessed capabilities.

        Three outcomes, and the distinction matters to the reader of the report:
        nothing assessed yet is "In progress"; assessed but with no usable level is
        "Not scored" (a data problem, not a low score); otherwise the average of the
        levels becomes the band.
        """
        axis_groups: dict[str, list[dict]] = {}
        for row in capability_rows:
            axis_groups.setdefault(str(row["axis"]), []).append(row)

        axes: list[FinalReportAxisItem] = []
        for axis_name, rows in axis_groups.items():
            if not rows:
                continue
            score, axis_level, band = self._axis_score(rows, maturity_number_by_id)
            axes.append(
                FinalReportAxisItem(
                    axis=axis_name,
                    score_percent=round(score, 2),
                    maturity_band=band,
                    axis_level=axis_level,
                    axis_level_label=self._level_label(axis_level),
                )
            )
        return axes

    def _axis_score(
        self, rows: list[dict], maturity_number_by_id: dict[int, int]
    ) -> tuple[float, int | None, str]:
        """One axis: (score percent, rounded level, band)."""
        assessed = [r for r in rows if str(r.get("assessment_status") or "not_assessed") == "assessed"]
        if not assessed:
            return 0.0, None, "In progress"

        levels = [
            maturity_number_by_id[int(r["maturity_level_id"])]
            for r in assessed
            if r.get("maturity_level_id") is not None
            and int(r["maturity_level_id"]) in maturity_number_by_id
        ]
        if not levels:
            return 0.0, None, "Not scored"

        average = sum(levels) / len(levels)
        axis_level = self._rounded_level(average)
        return (
            MaturityScoring.score_percent_from_level_average(average),
            axis_level,
            self._band_from_level(axis_level, "assessed"),
        )

    async def get_final_report(
        self,
        assessment_id: int,
        refresh_synthesis: bool = False,
    ) -> FinalReportResponse | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None

        report_date_label = self._report_date_label(getattr(assessment, "updated_at", None))
        company_name = normalize_text(getattr(assessment.company, "name", None))
        sector_name = normalize_text(getattr(getattr(assessment.company, "sector", None), "name", None))
        region = normalize_text(
            getattr(getattr(assessment.company, "region_ref", None), "name", None)
        )

        capability_rows = await self.capabilities.list_all_for_assessment(assessment_id=assessment_id)
        recommendation_rows = await self.capabilities.get_recommendations_for_scores(assessment_id=assessment_id)
        axis_maturity_content = await self.capabilities.get_axis_maturity_content()
        rec_by_capability = {int(row["capability_id"]): row for row in recommendation_rows}
        persisted_outputs = await self.assessments.list_recommendation_outputs(assessment_id=assessment_id)
        persisted_by_capability = {
            int(item.capability_id): item for item in persisted_outputs if item.capability_id is not None
        }
        maturity_number_by_id = await self.maturity_levels.get_numbers()

        axes = self._score_axes(capability_rows, maturity_number_by_id)

        all_level_numbers = [
            maturity_number_by_id[int(row["maturity_level_id"])]
            for row in capability_rows
            if str(row.get("assessment_status") or "not_assessed") == "assessed"
            and row.get("maturity_level_id") is not None
            and int(row["maturity_level_id"]) in maturity_number_by_id
        ]

        if axes:
            strongest = max(axes, key=lambda axis: axis.score_percent)
            priority = min(axes, key=lambda axis: axis.score_percent)
            overall_score = round(sum(axis.score_percent for axis in axes) / len(axes), 2)
        else:
            strongest = FinalReportAxisItem(
                axis="N/A",
                score_percent=0.0,
                maturity_band="Not scored",
                axis_level=None,
                axis_level_label=None,
            )
            priority = strongest
            overall_score = 0.0

        if all_level_numbers:
            overall_average = sum(all_level_numbers) / len(all_level_numbers)
            overall_level, overall_band = MaturityScoring.target_level_from_average(
                average=overall_average,
                basic_threshold=self.settings.maturity_average_basic_threshold,
                established_threshold=self.settings.maturity_average_established_threshold,
            )
        else:
            overall_level = None
            overall_band = "Not scored"

        capabilities: list[FinalReportCapabilityItem] = []
        for row in capability_rows:
            assessment_status = str(row.get("assessment_status") or "not_assessed")
            if assessment_status != "assessed":
                continue
            capability_id = int(row["id"])
            maturity_level_id = row.get("maturity_level_id")
            maturity_level_number = (
                maturity_number_by_id[int(maturity_level_id)]
                if maturity_level_id is not None and int(maturity_level_id) in maturity_number_by_id
                else None
            )
            rec = rec_by_capability.get(capability_id, {})
            persisted = persisted_by_capability.get(capability_id)
            recommendation_text = (
                normalize_text(persisted.generated_text)
                if persisted is not None
                else normalize_text(str(rec.get("recommendation_text") or rec.get("recommendation_guideline") or ""))
            )
            confidence_value = float(row.get("confidence") or 0.0) if row.get("confidence") is not None else None
            capabilities.append(
                FinalReportCapabilityItem(
                    capability_id=capability_id,
                    maturity_level_number=maturity_level_number,
                    axis=str(row["axis"]),
                    capability=self._translate_capability_name(str(row["label"]), getattr(assessment, "language", "fr")),
                    maturity_band=self._band_from_level(maturity_level_number, assessment_status),
                    assessment_status=assessment_status,
                    confidence=confidence_value,
                    rationale=self._soften_report_rationale(
                        rationale=row.get("rationale"),
                        confidence=confidence_value,
                    ),
                    recommendation=recommendation_text or None,
                    priority=rec.get("priority_hint"),
                )
            )

        assessed_capabilities = list(capabilities)
        themes = _select_report_themes(assessed_capabilities)
        strengths, pain_points = themes.strengths, themes.pain_points

        rubric_content_by_capability_id = self._current_rubric_content_by_capability(
            capability_rows=capability_rows,
            rubrics_by_capability=await self.capabilities.get_rubrics_for_capabilities(
                capability_ids=[int(row["id"]) for row in capability_rows if row.get("id") is not None]
            ),
            language=getattr(assessment, "language", "fr"),
        )

        synthesis = await self._get_or_generate_report_synthesis(
            assessment=assessment,
            overall_band=overall_band,
            overall_score=overall_score,
            strongest_axis=strongest.axis,
            priority_axis=priority.axis,
            axes=axes,
            strengths=strengths,
            pain_points=pain_points,
            strengths_count=len(themes.strength_candidates),
            pain_points_count=len(themes.pain_candidates),
            capabilities=capabilities,
            refresh_synthesis=refresh_synthesis,
        )

        summary = FinalReportSummary(
            overall_score_percent=overall_score,
            overall_maturity_band=overall_band,
            strongest_axis=strongest.axis,
            strongest_axis_score_percent=strongest.score_percent,
            priority_axis=priority.axis,
            priority_axis_score_percent=priority.score_percent,
            strengths_count=len(themes.strength_candidates),
            pain_points_count=len(themes.pain_candidates),
            assessed_capabilities_count=len(assessed_capabilities),
            unassessed_capabilities_count=max(0, len(capability_rows) - len(assessed_capabilities)),
            executive_summary_text=synthesis.get("executive_summary"),
            priority_message_text=synthesis.get("priority_message"),
        )
        
        strongest_key = strongest.axis.lower().strip() if strongest.axis else None
        priority_key = priority.axis.lower().strip() if priority.axis else None
        is_fr = (getattr(assessment, "language", "fr") or "").lower().startswith("fr")
        lang_code = "fr" if is_fr else "en"

        strongest_desc = _axis_short_copy(strongest.axis, "strongest", lang_code)
        priority_desc = _axis_short_copy(priority.axis, "priority", lang_code)

        hero = FinalReportHero(
            report_title="Rapport de maturité de l'expérience client" if is_fr else "Customer Experience Maturity Report",
            report_date_label=report_date_label,
            company_name=company_name,
            sector_name=sector_name,
            region=region,
            overall_level=overall_level,
            overall_level_label=self._level_label(overall_level),
            overall_maturity_band=overall_band,
            hero_message=self._hero_message(
                executive_summary=synthesis.get("executive_summary"),
                priority_message=synthesis.get("priority_message"),
                overall_band=overall_band,
                priority_axis=priority.axis,
            ),
            strongest_axis=strongest.axis if strongest.axis != "N/A" else None,
            strongest_axis_level=strongest.axis_level,
            strongest_axis_level_label=self._level_label(strongest.axis_level),
            strongest_axis_description=strongest_desc,
            priority_axis=priority.axis if priority.axis != "N/A" else None,
            priority_axis_level=priority.axis_level,
            priority_axis_level_label=self._level_label(priority.axis_level),
            priority_axis_description=priority_desc,
        )

        benchmarks: list[FinalReportBenchmarkItem] = []
        # Temporary safeguard: skip competitive landscape generation so completed
        # reports remain responsive while the benchmark layer is being stabilized.
        competitive_landscape: list[FinalReportCompetitiveStage] = []
        leaders_snapshot = await self._leaders_snapshot_section(
            assessment_id=assessment_id,
            assessment=assessment,
            refresh_snapshot=refresh_synthesis,
        )
        quick_wins_timeline = await self._build_quick_wins_timeline(
            assessment_id=assessment_id,
            assessment=assessment,
            capability_rows=capability_rows,
            capabilities=capabilities,
            maturity_number_by_id=maturity_number_by_id,
        )
        working_missing = self._build_working_missing_section(
            axes=axes,
            capabilities=capabilities,
            strengths=strengths,
            pain_points=pain_points,
            strongest_axis=strongest.axis,
            priority_axis=priority.axis,
            axis_maturity_content=axis_maturity_content,
            rubric_content_by_capability_id=rubric_content_by_capability_id,
            language=getattr(assessment, "language", "fr"),
        )

        return FinalReportResponse(
            assessment_id=assessment_id,
            hero=hero,
            summary=summary,
            axes=axes,
            strengths=strengths,
            pain_points=pain_points,
            capabilities=capabilities,
            benchmarks=benchmarks,
            competitive_landscape=competitive_landscape,
            leaders_snapshot=leaders_snapshot,
            quick_wins_timeline=quick_wins_timeline,
            working_missing=working_missing,
        )

    async def debug_competitive_first_layer(
        self,
        assessment_id: int,
        competitor_name: str | None = None,
    ) -> dict[str, Any] | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None

        sector_name = getattr(assessment.company.sector, "name", "Unknown")
        company_name = normalize_text(getattr(assessment.company, "name", None)) or "You"
        return await self.benchmarks.debug_competitive_first_layer(
            sector=sector_name,
            company_name=company_name,
            competitor_name=competitor_name,
        )

    async def debug_telecom_semantic_leaders(self, assessment_id: int) -> dict[str, Any] | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None

        pain_points = await self._telecom_benchmark_pain_points(assessment_id=assessment_id)
        service = SemanticLeadersService(settings=self.settings, llm_service=self.llm)
        return await service.debug_leaders_snapshot(
            sector=getattr(assessment.company.sector, "name", "Unknown"),
            respondent_company_name=normalize_text(getattr(assessment.company, "name", None)) or "You",
            pain_points=pain_points,
            language=getattr(assessment, "language", "fr"),
        )

    async def debug_telecom_discovery_leaders(self, assessment_id: int) -> dict[str, Any] | None:
        assessment = await self.assessments.get_by_id(assessment_id)
        if assessment is None:
            return None

        pain_points = await self._telecom_benchmark_pain_points(assessment_id=assessment_id)
        service = TelecomDiscoveryLeadersService(settings=self.settings, llm_service=self.llm)
        return await service.build_leaders_snapshot(
            sector=getattr(assessment.company.sector, "name", "Unknown"),
            respondent_company_name=normalize_text(getattr(assessment.company, "name", None)) or "You",
            pain_points=pain_points,
            include_debug=True,
        )

    async def _leaders_snapshot_section(
        self,
        *,
        assessment_id: int,
        assessment: Any,
        refresh_snapshot: bool,
    ) -> FinalReportLeadersSnapshot | None:
        cached_payload = getattr(assessment, "leaders_snapshot_payload", None)
        snapshot_status = str(getattr(assessment, "leaders_snapshot_status", "") or "").strip().lower()
        if cached_payload and snapshot_status == LEADERS_SNAPSHOT_STATUS_COMPLETED and not refresh_snapshot:
            try:
                logger.warning("leaders_snapshot cache hit for assessment=%s", assessment_id)
                return FinalReportLeadersSnapshot(**cached_payload)
            except Exception as exc:
                logger.warning("Invalid cached leaders snapshot for assessment=%s: %s", assessment_id, exc)

        logger.warning("leaders_snapshot generating synchronously for assessment=%s", assessment_id)
        await self._generate_and_persist_leaders_snapshot_job(
            assessment_id=assessment_id,
            force_refresh=True,
        )
        
        # Re-fetch assessment to get the newly generated payload
        assessment = await self.assessments.get_by_id(assessment_id)
        cached_payload = getattr(assessment, "leaders_snapshot_payload", None)
        if cached_payload:
            try:
                return FinalReportLeadersSnapshot(**cached_payload)
            except Exception as exc:
                logger.warning("Invalid generated leaders snapshot for assessment=%s: %s", assessment_id, exc)
        return self._failed_leaders_snapshot(assessment=assessment)


    async def prepare_leaders_snapshot_generation(
        self,
        *,
        assessment_id: int,
        assessment: Any,
    ) -> None:
        if str(getattr(assessment, "status", "")) != ASSESSMENT_STATUS_COMPLETED:
            return
        snapshot_status = str(getattr(assessment, "leaders_snapshot_status", "") or "").strip().lower()
        if snapshot_status == LEADERS_SNAPSHOT_STATUS_COMPLETED and getattr(assessment, "leaders_snapshot_payload", None):
            return
        await self._generate_and_persist_leaders_snapshot_job(assessment_id=assessment_id, force_refresh=False)


    async def _schedule_leaders_snapshot_job(
        self,
        *,
        assessment_id: int,
        force_refresh: bool,
    ) -> None:
        async with _leaders_snapshot_tasks_lock:
            existing_task = _leaders_snapshot_tasks.get(assessment_id)
            if existing_task is not None and not existing_task.done():
                logger.warning("leaders_snapshot joined in-flight task for assessment=%s", assessment_id)
                return
            logger.warning("leaders_snapshot job enqueued for assessment=%s refresh=%s", assessment_id, force_refresh)
            task = asyncio.create_task(
                self._run_leaders_snapshot_job(
                    assessment_id=assessment_id,
                    force_refresh=force_refresh,
                )
            )
            _leaders_snapshot_tasks[assessment_id] = task

    async def _run_leaders_snapshot_job(
        self,
        *,
        assessment_id: int,
        force_refresh: bool,
    ) -> None:
        semaphore = _get_leaders_snapshot_job_semaphore(self.settings)
        try:
            async with semaphore:
                logger.warning("leaders_snapshot job started for assessment=%s refresh=%s", assessment_id, force_refresh)
                async with SessionLocal() as db:
                    builder = _build_report_builder_service(db, self.settings)
                    await builder._generate_and_persist_leaders_snapshot_job(
                        assessment_id=assessment_id,
                        force_refresh=force_refresh,
                    )
                logger.warning("leaders_snapshot job completed for assessment=%s refresh=%s", assessment_id, force_refresh)
        except Exception as exc:
            logger.warning("leaders_snapshot job failed for assessment=%s refresh=%s error=%s", assessment_id, force_refresh, exc)
        finally:
            current_task = asyncio.current_task()
            async with _leaders_snapshot_tasks_lock:
                task = _leaders_snapshot_tasks.get(assessment_id)
                if task is current_task:
                    _leaders_snapshot_tasks.pop(assessment_id, None)

    async def _persist_leaders_snapshot_cache(
        self,
        *,
        assessment: Any,
        snapshot: FinalReportLeadersSnapshot,
        status: str,
        generated_at: datetime | None,
        error_message: str | None,
    ) -> None:
        if str(getattr(assessment, "status", "")) != ASSESSMENT_STATUS_COMPLETED:
            return
        try:
            async with self.uow:
                await self.assessments.update_leaders_snapshot_cache(
                    assessment=assessment,
                    leaders_snapshot_payload=snapshot.model_dump(),
                    leaders_snapshot_status=status,
                    leaders_snapshot_generated_at=generated_at,
                    leaders_snapshot_error=error_message,
                )
        except Exception as exc:
            logger.warning(
                "Could not persist leaders snapshot cache for assessment=%s: %s",
                getattr(assessment, "id", None),
                exc,
            )

    async def _generate_and_persist_leaders_snapshot_job(
        self,
        *,
        assessment_id: int,
        force_refresh: bool,
    ) -> None:
        assessment = None
        for attempt in range(5):
            assessment = await self.assessments.get_by_id(assessment_id)
            if assessment is not None and str(getattr(assessment, "status", "")) == ASSESSMENT_STATUS_COMPLETED:
                break
            await asyncio.sleep(0.4)
        if assessment is None or str(getattr(assessment, "status", "")) != ASSESSMENT_STATUS_COMPLETED:
            logger.warning("leaders_snapshot job skipped for assessment=%s because completion state was not visible yet", assessment_id)
            return

        if (
            not force_refresh
            and str(getattr(assessment, "leaders_snapshot_status", "") or "").strip().lower() == LEADERS_SNAPSHOT_STATUS_COMPLETED
            and getattr(assessment, "leaders_snapshot_payload", None)
        ):
            return

        existing_payload = getattr(assessment, "leaders_snapshot_payload", None)
        if not (force_refresh and existing_payload):
            running_snapshot = self._pending_leaders_snapshot(
                assessment=assessment,
                status=LEADERS_SNAPSHOT_STATUS_RUNNING,
                message="Benchmark content is generating in the background.",
            )
            await self._persist_leaders_snapshot_cache(
                assessment=assessment,
                snapshot=running_snapshot,
                status=LEADERS_SNAPSHOT_STATUS_RUNNING,
                generated_at=None,
                error_message=None,
            )

        snapshot = await self._generate_live_leaders_snapshot(
            assessment_id=assessment_id,
            assessment=assessment,
            generation_mode="refresh" if force_refresh else "initial",
        )
        if snapshot is None:
            if force_refresh and existing_payload:
                logger.warning("leaders_snapshot refresh failed for assessment=%s; preserving previous completed snapshot", assessment_id)
                return
            failed_snapshot = self._failed_leaders_snapshot(assessment=assessment)
            await self._persist_leaders_snapshot_cache(
                assessment=assessment,
                snapshot=failed_snapshot,
                status=LEADERS_SNAPSHOT_STATUS_FAILED,
                generated_at=None,
                error_message="generation_failed",
            )
            return

        await self._persist_leaders_snapshot_cache(
            assessment=assessment,
            snapshot=snapshot,
            status=LEADERS_SNAPSHOT_STATUS_COMPLETED,
            generated_at=datetime.now(timezone.utc),
            error_message=None,
        )

    async def _generate_live_leaders_snapshot(
        self,
        *,
        assessment_id: int,
        assessment: Any,
        generation_mode: str,
    ) -> FinalReportLeadersSnapshot | None:
        """Run the competitor benchmark and turn its result into the report's snapshot section.

        The benchmark is the most failure-prone part of the report -- many web searches plus a
        model pass per candidate -- so a failure returns None and the report ships without the
        section rather than not shipping at all.
        """
        sector = getattr(assessment.company.sector, "name", "Unknown")
        respondent_company_name = normalize_text(getattr(assessment.company, "name", None)) or "You"
        pain_points = await self._telecom_benchmark_pain_points(assessment_id=assessment_id)

        service = SemanticLeadersService(settings=self.settings, llm_service=self.llm)
        try:
            snapshot = await service.build_leaders_snapshot(
                sector=sector,
                respondent_company_name=respondent_company_name,
                pain_points=pain_points,
                generation_mode=generation_mode,
                language=getattr(assessment, "language", "fr"),
            )
        except Exception as exc:
            logger.warning("Leaders snapshot generation failed for assessment=%s: %s", assessment_id, exc)
            return None

        leaders = [
            leader
            for leader in (self._leader_item(item) for item in (snapshot.get("leaders") or []))
            if leader is not None
        ]
        # No leaders found for a sector the benchmark claims to support means the run failed to
        # produce anything usable, so the section is dropped. An explicitly unsupported sector is
        # different: that snapshot is kept, because it carries the reason to show the reader.
        if not leaders and snapshot.get("supported", True):
            return None

        metrics = snapshot.get("metrics")
        return FinalReportLeadersSnapshot(
            supported=bool(snapshot.get("supported")),
            status=LEADERS_SNAPSHOT_STATUS_COMPLETED,
            sector=str(snapshot.get("sector") or sector),
            respondent_company_name=str(snapshot.get("respondent_company_name") or respondent_company_name),
            message=str(snapshot.get("reason") or snapshot.get("message") or "") or None,
            metrics=FinalReportLeadersSnapshotMetrics(**metrics) if isinstance(metrics, dict) else None,
            leaders=leaders,
        )

    def _leader_item(self, item: dict) -> FinalReportLeaderItem | None:
        """One benchmarked company as the report renders it, or None if it has no name to show."""
        company_name = str(item.get("company_name") or "").strip()
        if not company_name:
            return None

        leader_summary = normalize_text(str(item.get("leader_summary") or "")).strip() or None
        return FinalReportLeaderItem(
            key=str(item.get("key") or ""),
            company_name=company_name,
            # `note` is the older name for this sentence, still written so that reports stored
            # before the rename keep rendering -- the UI and the PDF both read
            # `leader_summary ?? note`.
            note=leader_summary,
            leader_summary=leader_summary,
            logo_url=item.get("logo_url"),
            evidence_links=[
                self._leader_evidence_link(link)
                for link in (item.get("evidence_links") or [])
                if str(link.get("url") or "").strip()
            ],
        )

    @staticmethod
    def _leader_evidence_link(link: dict) -> FinalReportLeaderEvidenceLink:
        """One piece of published evidence backing what a leader is said to do."""
        return FinalReportLeaderEvidenceLink(
            label=normalize_text(str(link.get("label") or "")).strip(),
            url=str(link.get("url") or ""),
            source_title=normalize_text(str(link.get("source_title") or "")).strip() or None,
            mapped_capability=normalize_text(str(link.get("mapped_capability") or "")).strip() or None,
            why_relevant=normalize_text(str(link.get("why_relevant") or "")).strip() or None,
        )


    def _pending_leaders_snapshot(
        self,
        *,
        assessment: Any,
        status: str = LEADERS_SNAPSHOT_STATUS_PENDING,
        message: str = "Benchmark content is being prepared and will appear shortly.",
    ) -> FinalReportLeadersSnapshot:
        return FinalReportLeadersSnapshot(
            supported=True,
            status=status,
            sector=str(getattr(getattr(assessment.company, "sector", None), "name", "Unknown") or "Unknown"),
            respondent_company_name=normalize_text(getattr(assessment.company, "name", None)) or "You",
            message=message,
            metrics=None,
            leaders=[],
        )

    def _failed_leaders_snapshot(self, *, assessment: Any) -> FinalReportLeadersSnapshot:
        return FinalReportLeadersSnapshot(
            supported=False,
            status=LEADERS_SNAPSHOT_STATUS_FAILED,
            sector=str(getattr(getattr(assessment.company, "sector", None), "name", "Unknown") or "Unknown"),
            respondent_company_name=normalize_text(getattr(assessment.company, "name", None)) or "You",
            message="Benchmark content is temporarily unavailable.",
            metrics=None,
            leaders=[],
        )

    async def _build_quick_wins_timeline(
        self,
        *,
        assessment_id: int,
        assessment: Any,
        capability_rows: list[dict[str, Any]],
        capabilities: list[FinalReportCapabilityItem],
        maturity_number_by_id: dict[int, int],
    ) -> FinalReportQuickWinsTimeline | None:
        """The "what to do next" section: a few concrete actions, in the order to take them.

        Returns None rather than an empty section when there is nothing to propose -- which happens
        legitimately, when no assessed capability has an authored quick win for the level it
        scored.
        """
        assessed_capability_ids = [
            int(row["id"])
            for row in capability_rows
            if row.get("id") is not None and str(row.get("assessment_status") or "not_assessed") == "assessed"
        ]
        template_by_key = await self.capabilities.get_quick_win_templates(assessed_capability_ids)

        selected = self._select_quick_win_candidates(
            capability_rows=capability_rows,
            capabilities=capabilities,
            maturity_number_by_id=maturity_number_by_id,
            template_by_key=template_by_key,
        )
        if not selected:
            return None

        # The model rewrites each action in the client's own terms, so it is given what the client
        # actually said about that capability alongside what the diagnostic concluded.
        capability_ids = [int(item["capability_id"]) for item in selected]
        answers_by_capability = await self.assessments.get_answers_by_capability(
            assessment_id, capability_ids
        )
        insights_by_capability = await self.assessments.get_insight_texts_by_capability(
            assessment_id, capability_ids
        )

        language = getattr(assessment, "language", "fr")
        timeline_labels = self._quick_win_timeline_labels(language)
        llm_candidates = [
            {
                "step": step,
                "timeline_label": timeline_labels[step - 1],
                "axis": item["axis"],
                "capability": item["capability"],
                "capability_raw": item.get("capability_raw"),
                "maturity_band": item["maturity_band"],
                "quick_win_guideline": item.get("quick_win_guideline"),
                "after_text": item.get("after_text"),
                "owner_hint": item.get("owner_hint"),
                "timeline_hint": item.get("timeline_hint"),
                "respondent_answers": answers_by_capability.get(int(item["capability_id"]), [])[
                    :_MAX_EVIDENCE_SNIPPETS
                ],
                "respondent_insights": insights_by_capability.get(int(item["capability_id"]), [])[
                    :_MAX_EVIDENCE_SNIPPETS
                ],
                "current_rationale": item.get("rationale"),
            }
            for step, item in enumerate(selected, start=1)
        ]

        items = await self._shape_quick_wins_with_llm(candidates=llm_candidates, language=language)
        if not items:
            return None
        return FinalReportQuickWinsTimeline(
            section_title=self._quick_win_section_title(language),
            language=self._normalize_report_language(language),
            items=items[:_MAX_QUICK_WINS],
        )

    def _select_quick_win_candidates(
        self,
        *,
        capability_rows: list[dict[str, Any]],
        capabilities: list[FinalReportCapabilityItem],
        maturity_number_by_id: dict[int, int],
        template_by_key: dict[tuple[int, int], dict[str, str | None]],
    ) -> list[dict[str, Any]]:
        """The quick wins to put in the report, best first.

        A capability qualifies only if it was assessed, scored, and has an admin-authored quick-win
        guideline for the level it landed on -- without that guideline there is nothing concrete to
        propose, and inventing one is what the whole template mechanism exists to avoid.
        """
        capability_item_by_id = {
            int(item.capability_id): item
            for item in capabilities
            if item.capability_id is not None
        }

        candidates: list[dict[str, Any]] = []
        for row in capability_rows:
            candidate = self._quick_win_candidate(
                row,
                capability_item_by_id=capability_item_by_id,
                maturity_number_by_id=maturity_number_by_id,
                template_by_key=template_by_key,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda item: item["quick_win_rank_score"])
        return self._spread_quick_wins_across_axes(candidates)

    def _quick_win_candidate(
        self,
        row: dict[str, Any],
        *,
        capability_item_by_id: dict[int, FinalReportCapabilityItem],
        maturity_number_by_id: dict[int, int],
        template_by_key: dict[tuple[int, int], dict[str, str | None]],
    ) -> dict[str, Any] | None:
        """One capability row as a quick-win candidate, or None if it does not qualify.

        Five ways to not qualify, and they are all "we do not have what we would need to write
        this": not assessed, no capability or level recorded, no scored item to draw the wording
        from, an unknown maturity level, or no authored guideline for that level.
        """
        if str(row.get("assessment_status") or "not_assessed") != "assessed":
            return None
        capability_id = row.get("id")
        maturity_level_id = row.get("maturity_level_id")
        if capability_id is None or maturity_level_id is None:
            return None

        capability_item = capability_item_by_id.get(int(capability_id))
        if capability_item is None:
            return None
        maturity_level_number = maturity_number_by_id.get(int(maturity_level_id))
        if maturity_level_number is None:
            return None

        template = template_by_key.get((int(capability_id), int(maturity_level_id))) or {}

        def authored(field: str) -> str | None:
            return normalize_text(str(template.get(field) or "")).strip() or None

        quick_win_guideline = authored("quick_win_guideline")
        if not quick_win_guideline:
            return None

        timeline_hint = authored("timeline_hint")
        after_text = authored("after_text")
        confidence = float(capability_item.confidence or 0.0)
        return {
            "capability_id": int(capability_id),
            "maturity_level_id": int(maturity_level_id),
            "maturity_level_number": int(maturity_level_number),
            "axis": capability_item.axis,
            "capability": capability_item.capability,
            "capability_raw": str(row.get("label") or ""),
            "maturity_band": capability_item.maturity_band,
            "confidence": confidence,
            "rationale": normalize_text(
                capability_item.rationale
                or str(row.get("justification") or row.get("insight_justification") or row.get("evidence_text") or "")
            ).strip()
            or None,
            "quick_win_guideline": quick_win_guideline,
            "after_text": after_text,
            "owner_hint": authored("owner_hint"),
            "timeline_hint": timeline_hint,
            "timeline_stage": self._quick_win_timeline_stage(timeline_hint),
            "quick_win_rank_score": self._quick_win_rank_score(
                timeline_hint=timeline_hint,
                maturity_level_number=int(maturity_level_number),
                confidence=confidence,
                has_after_text=bool(after_text),
            ),
        }

    def _spread_quick_wins_across_axes(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Take the best few candidates, preferring one per axis over the top of one ranking.

        Ranking alone tends to cluster: the weakest axis produces the easiest wins, so the top four
        by score are often four fixes to the same part of the business. That reads as a narrow
        report. So the first pass takes the best candidate from each axis in turn, and only once
        every axis is represented does a second pass fill any remaining slots from the ranking.

        `candidates` must already be sorted best-first.
        """
        if len(candidates) <= _MAX_QUICK_WINS:
            return candidates

        selected: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        seen_axes: set[str] = set()
        for item in candidates:
            axis_key = self._normalize_axis_key(str(item["axis"]))
            if axis_key in seen_axes:
                continue
            selected.append(item)
            seen_axes.add(axis_key)
            seen_ids.add(int(item["capability_id"]))
            if len(selected) >= _MAX_QUICK_WINS:
                return selected

        for item in candidates:
            capability_id = int(item["capability_id"])
            if capability_id in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(capability_id)
            if len(selected) >= _MAX_QUICK_WINS:
                break
        return selected[:_MAX_QUICK_WINS]

    async def _shape_quick_wins_with_llm(self, candidates: list[dict[str, Any]], language: str = "fr") -> list[FinalReportQuickWinItem]:
        fallback = [self._fallback_quick_win_item(candidate, language=language) for candidate in candidates[:4]]
        if not candidates or not self.settings.mistral_api_key:
            return fallback

        payload = {
            "timeline_labels": list(self._quick_win_timeline_labels(language)[: len(candidates)]),
            "items": candidates[:4],
        }
        system_prompt = (
            "You write section-4 quick wins for a customer experience maturity report. "
            "Return JSON only with an object containing an `items` array. "
            "No markdown. No benchmark references. No consultant filler."
        ) + language_directive(language)
        user_prompt = (
            "Transform the following capability-level inputs into exactly one quick win per item.\n"
            "Rules:\n"
            "- Preserve each item's step and timeline_label exactly as given.\n"
            "- Write a short action title of 5 to 10 words, suitable for the timeline label and popup.\n"
            "- Prefer owners explicitly mentioned in respondent answers or insights; otherwise infer the most plausible concise owner role.\n"
            "- `today_text` must summarize the respondent's current weakness in plain language.\n"
            "- Do not generate `after_text`; the backend derives and localizes that separately from the quick-win template.\n"
            "- Use only the provided inputs.\n"
            "- Never mention competitors, benchmarks, or sources.\n"
            "- Keep owner concise, like 'Customer Experience Lead' or 'Operations Manager'.\n"
            "Return JSON in this shape:\n"
            "{\"items\": [{\"step\": 1, \"timeline_label\": \"Week 1\", \"title\": \"...\", \"owner\": \"...\", \"today_text\": \"...\"}]}\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=True)}"
        )
        try:
            content = await self.llm.gateway.chat_messages(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            blob = extract_json(content)
            raw_items = blob.get("items") if isinstance(blob, dict) else None
            if not isinstance(raw_items, list):
                return fallback
            parsed: list[FinalReportQuickWinItem] = []
            for index, raw in enumerate(raw_items[: len(candidates)]):
                if not isinstance(raw, dict):
                    continue
                parsed.append(
                    self._finalize_quick_win_item(
                        raw=raw,
                        candidate=candidates[index],
                        fallback=fallback[index],
                        language=language,
                    )
                )
            if len(parsed) != len(candidates[:4]):
                return fallback
            return self._post_process_quick_win_items(
                parsed=parsed,
                candidates=candidates[:4],
                fallback=fallback,
                language=language,
            )
        except Exception as exc:
            logger.error("Quick wins timeline shaping failed: %s", exc, exc_info=True)
            return fallback

    def _fallback_quick_win_item(self, candidate: dict[str, Any], language: str = "fr") -> FinalReportQuickWinItem:
        step = int(candidate["step"])
        title = self._fallback_quick_win_title(candidate, language=language)
        today_text = self._fallback_quick_win_today_text(candidate, language=language)
        after_text = self._quick_win_after_text(candidate, language=language)
        owner = self._normalize_quick_win_owner_label(
            raw_owner=str(candidate.get("owner_hint") or ""),
            axis=str(candidate.get("axis") or ""),
            capability=str(candidate.get("capability") or ""),
        )
        return FinalReportQuickWinItem(
            step=step,
            timeline_label=self._normalize_quick_win_label(
                candidate.get("timeline_label"),
                self._quick_win_timeline_labels(language)[step - 1],
                language=language,
            ),
            title=title,
            owner=owner,
            today_text=today_text,
            after_text=after_text,
        )

    def _normalize_quick_win_label(self, value: Any, fallback: str, language: str = "fr") -> str:
        normalized = normalize_text(str(value or "")).strip()
        allowed_labels = set(QUICK_WIN_TIMELINE_LABELS) | set(QUICK_WIN_TIMELINE_LABELS_FR)
        if normalized in allowed_labels:
            return normalized
        return fallback

    def _quick_win_timeline_stage(self, timeline_hint: str | None) -> int:
        normalized = normalize_text(timeline_hint).lower().strip()
        if normalized == "earliest quick win":
            return 0
        if normalized == "after first routine is in place":
            return 1
        if normalized == "after first routines are visible":
            return 2
        if normalized == "later operationalization":
            return 3
        return 2

    def _normalize_report_language(self, language: str | None) -> str:
        return "fr" if normalize_text(language).lower().startswith("fr") else "en"

    def _is_french(self, language: str | None) -> bool:
        return self._normalize_report_language(language) == "fr"

    def _quick_win_timeline_labels(self, language: str | None) -> tuple[str, str, str, str]:
        return QUICK_WIN_TIMELINE_LABELS_FR if self._is_french(language) else QUICK_WIN_TIMELINE_LABELS

    def _quick_win_section_title(self, language: str | None) -> str:
        return "Vos quick wins, dans l'ordre" if self._is_french(language) else "Your Quick Wins, In Order"

    def _fr_capability_label(self, capability: str) -> str:
        key = normalize_text(capability).lower().strip()
        labels = {
            "decision-making": "la prise de decision",
            "ownership and governance": "l'ownership et la gouvernance",
            "feedback collection": "la collecte des retours clients",
            "use of insights": "l'exploitation des insights",
            "channel consistency": "la coherence multicanale",
            "journey visibility": "la visibilite des parcours",
            "measurement and continuous improvement": "la mesure et l'amelioration continue",
            "acting on pain points": "le traitement des points de douleur",
            "cx culture": "la culture de l'expérience client",
        }
        return labels.get(key, capability)

    def _fr_quick_win_title_map(self) -> dict[str, str]:
        return {
            "decision-making": "Lancer une revue decisionnelle client",
            "ownership and governance": "Formaliser les revues d'expérience client transverses",
            "feedback collection": "Structurer la revue des retours clients",
            "use of insights": "Prioriser les irritants par impact client",
            "channel consistency": "Corriger les principaux ecarts multicanaux",
            "journey visibility": "Cartographier les parcours et nommer les owners",
            "measurement and continuous improvement": "Nommer les owners des indicateurs d'expérience client",
            "acting on pain points": "Ajouter une verification des causes racines",
            "cx culture": "Coacher les équipes sur les moments d'expérience client",
        }

    def _fr_quick_win_today_map(self) -> dict[str, str]:
        return {
            "decision-making": "Les retours clients sont suivis, mais ils influencent encore rarement les decisions et les priorites de maniere structuree.",
            "ownership and governance": "Un responsable existe, mais les routines transverses et les escalades restent encore inegales.",
            "feedback collection": "Les retours sont collectes, mais la couverture et les routines de revue restent incompletes.",
            "use of insights": "Les informations clients existent, mais les themes, causes et impacts ne sont pas revus de maniere reguliere.",
            "channel consistency": "Les clients peuvent encore rencontrer des reponses ou des passages de relais inegaux selon les canaux.",
            "journey visibility": "Les equipes ameliorent des points de contact isoles, sans vision partagee du parcours.",
            "measurement and continuous improvement": "Des indicateurs existent, mais ils ne sont pas encore relies a des owners, decisions ou plans de suivi.",
            "acting on pain points": "Les irritants sont traites de facon reactive, sans backlog, owner ou discipline de cloture suffisamment stable.",
            "cx culture": "Les attentes d'expérience client ne sont pas encore renforcées par des habitudes, du coaching ou des routines communes.",
        }

    def _localize_quick_win_after_text(self, after_text: str, candidate: dict[str, Any]) -> str:
        key = normalize_text(after_text).lower().strip()
        exact_map = {
            "customer-facing teams get a shared service baseline, reducing inconsistent behaviors and making cx expectations easier to coach.": "Les équipes en contact client disposent d'un socle de service commun, ce qui réduit les comportements incohérents et facilite le coaching de l'expérience client.",
            "customer-focused behaviors become more repeatable through team routines, qa feedback, and visible reinforcement.": "Les comportements orientes client deviennent plus repetables grace aux routines d'equipe, aux retours qualite et au renforcement visible.",
            "teams can connect daily behaviors to measurable customer outcomes, strengthening accountability and cultural consistency.": "Les equipes relient les comportements quotidiens a des resultats client mesurables, ce qui renforce la responsabilisation et la coherence culturelle.",
            "customer issues stop depending only on informal follow-up because ownership, escalation, and next actions become visible.": "Les problemes clients ne dependent plus seulement du suivi informel, car les owners, escalades et prochaines actions deviennent visibles.",
            "cross-functional teams gain a clearer operating rhythm for customer issues, reducing dropped actions and fragmented accountability.": "Les équipes transverses gagnent un rythme de pilotage plus clair des problèmes clients, ce qui réduit les actions oubliées et la responsabilité fragmentée.",
            "cx governance becomes a decision mechanism that connects ownership, investment choices, and measurable customer outcomes.": "La gouvernance de l'expérience client devient un mécanisme de décision reliant la responsabilité, les choix d'investissement et les résultats client mesurables.",
            "customer evidence gets a defined place in operational decisions, reducing purely reactive or internally driven prioritization.": "Les preuves client trouvent une place claire dans les décisions opérationnelles, ce qui réduit les priorités purement réactives ou internes.",
            "customer feedback becomes more actionable because decisions are connected to owners, next steps, and visible follow-up.": "Les retours clients deviennent plus actionnables, car les décisions sont reliées à des owners, des prochaines étapes et un suivi visible.",
            "customer evidence has a stronger path into planning, helping teams prioritize resources around the highest-impact experience gaps.": "Les preuves client alimentent mieux la planification et aident les équipes à prioriser les ressources sur les écarts d'expérience les plus critiques.",
            "feedback capture becomes less ad hoc, giving teams a repeatable source of customer signals to review and act on.": "La collecte des retours devient moins ad hoc et donne aux équipes une source répétable de signaux client à analyser et traiter.",
            "teams gain broader and more comparable feedback coverage, improving visibility across the main customer touchpoints.": "Les équipes obtiennent une couverture de feedback plus large et comparable, ce qui améliore la visibilité sur les principaux points de contact.",
            "feedback becomes a normal input into service management, improving continuity between listening, decisions, and action.": "Le feedback devient une entrée normale du pilotage du service, ce qui renforce la continuité entre écoute, décision et action.",
            "customer comments become easier to interpret because repeated issues are grouped into themes instead of handled only case by case.": "Les commentaires clients deviennent plus faciles à interpréter, car les problèmes récurrents sont regroupés par thèmes plutôt que traités au cas par cas.",
            "insight reviews become more decision-ready by connecting repeated themes to causes, impact, and prioritization logic.": "Les revues d'insights deviennent plus utiles pour la décision en reliant thèmes récurrents, causes, impact et logique de priorisation.",
            "customer insight becomes a stronger management input, helping teams focus improvement effort where it can shift outcomes.": "L'insight client devient un intrant de management plus fort et aide les équipes à concentrer les efforts là où ils peuvent changer les résultats.",
            "customers receive more consistent information and handoffs because teams have a shared baseline for channel behaviour.": "Les clients reçoivent des informations et passages de relais plus cohérents, car les équipes disposent d'un socle commun de comportement par canal.",
            "cross-channel friction becomes easier to spot and resolve, reducing repeat contacts and inconsistent customer experiences.": "Les frictions multicanales deviennent plus faciles à repérer et corriger, ce qui réduit les contacts répétés et les expériences incohérentes.",
            "channel management shifts from local fixes to a more joined-up experience with clearer standards and monitoring.": "Le pilotage des canaux passe de corrections locales à une expérience plus cohérente, avec des standards et un suivi plus clairs.",
            "teams gain a shared view of the most important journeys, making pain points easier to locate and discuss together.": "Les équipes disposent d'une vision partagée des parcours les plus importants, ce qui facilite l'identification et la discussion des irritants.",
            "journey visibility becomes more operational because teams regularly review touchpoints, friction, and ownership.": "La visibilité parcours devient plus opérationnelle, car les équipes revoient régulièrement points de contact, frictions et ownership.",
            "journey architecture becomes a practical planning tool, helping leaders connect improvement decisions to customer moments.": "L'architecture des parcours devient un outil de planification concret, reliant les décisions d'amélioration aux moments client.",
            "teams gain a basic improvement rhythm by tracking a focused set of cx measures and discussing what changed.": "Les équipes installent un premier rythme d'amélioration en suivant quelques mesures d'expérience client ciblées et en discutant ce qui évolue.",
            "measurement becomes more useful because metric movement triggers ownership, action review, and follow-up.": "La mesure devient plus utile, car l'évolution des indicateurs déclenche ownership, revue d'action et suivi.",
            "improvement activity becomes easier to prioritize and govern through connected cx, operational, and business outcomes.": "Les actions d'amélioration deviennent plus faciles à prioriser et piloter grâce au lien entre résultats d'expérience client, opérationnels et commerciaux.",
            "recurring pain points are less likely to be closed superficially because teams check causes before moving on.": "Les irritants récurrents risquent moins d'être clos superficiellement, car les équipes vérifient les causes avant de passer à la suite.",
            "pain-point handling becomes more structured through review routines, owners, and clearer action follow-through.": "Le traitement des irritants devient plus structuré grâce aux routines de revue, aux owners et à un meilleur suivi des actions.",
            "teams move from reactive fixes toward earlier detection and more systematic prevention of recurring customer issues.": "Les équipes passent de corrections réactives à une détection plus précoce et une prévention plus systématique des problèmes clients récurrents.",
        }
        if key in exact_map:
            return exact_map[key]
        capability = self._fr_capability_label(str(candidate.get("capability") or ""))
        return f"{capability} devient plus clair, plus regulier et plus facile a piloter."

    def _looks_like_english_quick_win_text(self, text: str) -> bool:
        lowered = normalize_text(text).lower()
        english_markers = (
            "customer",
            "feedback",
            "decision",
            "owner",
            "journey",
            "channel",
            "review",
            "formalize",
            "launch",
            "assign",
            "metrics",
        )
        french_markers = (" client", " clients", " equipe", " equipes", "decision", "retour", "retours", "amelior")
        return any(marker in lowered for marker in english_markers) and not any(marker in lowered for marker in french_markers)

    def _quick_win_rank_score(
        self,
        *,
        timeline_hint: str | None,
        maturity_level_number: int,
        confidence: float,
        has_after_text: bool,
    ) -> tuple[float, int, int, float]:
        return (
            float(self._quick_win_timeline_stage(timeline_hint)),
            int(maturity_level_number),
            0 if has_after_text else 1,
            -round(float(confidence), 4),
        )

    def _normalize_quick_win_owner_label(
        self,
        *,
        raw_owner: str,
        axis: str,
        capability: str,
        language: str = "fr",
    ) -> str:
        """The job title to print as the owner of a quick win.

        An authored owner hint is free text, so it arrives as anything from "CX" to "the digital
        transformation programme team". This maps it onto one of the standard titles, and falls
        back to something derived from the axis when the hint is too vague to print.

        Governance work is the one capability that overrides the hint: it belongs to the CX lead
        unless the hint names a specific function, because "operations owns governance" is how
        governance ends up owned by nobody.
        """
        normalized = normalize_text(raw_owner).strip()
        lowered = normalized.lower()
        lang = "fr" if self._is_french(language) else "en"
        is_governance = _is_governance_capability(capability)

        def title(role_key: str) -> str:
            return _QUICK_WIN_OWNER_TITLES[role_key][lang]

        def owner_when_hint_is_unusable() -> str:
            if is_governance:
                return title("cx")
            return self._fallback_quick_win_owner(axis=axis, capability=capability, language=language)

        if is_governance and not any(term in lowered for term in _FUNCTIONAL_OWNER_TERMS):
            return title("cx")

        for terms, role_key in _QUICK_WIN_OWNER_TERMS:
            if any(term in lowered for term in terms):
                if is_governance and role_key == "operations":
                    return title("cx")
                return title(role_key)

        too_vague = lowered in _VAGUE_OWNERS or len(normalized.split()) > _MAX_OWNER_WORDS
        if too_vague or not normalized:
            return owner_when_hint_is_unusable()

        # Specific enough to print as the admin wrote it.
        return normalized

    def _fallback_quick_win_title(self, candidate: dict[str, Any], language: str = "fr") -> str:
        capability_text = normalize_text(str(candidate.get("capability_raw") or candidate.get("capability") or "")).lower()
        title_map = self._fr_quick_win_title_map() if self._is_french(language) else {
            "decision-making": "Launch monthly customer decision review",
            "ownership and governance": "Formalize cross-functional Customer Experience reviews",
            "feedback collection": "Set weekly CRM feedback review",
            "use of insights": "Review top issues by customer impact",
            "channel consistency": "Fix top three channel handoff gaps",
            "journey visibility": "Map top journeys and assign owners",
            "measurement and continuous improvement": "Assign owners to core Customer Experience metrics",
            "acting on pain points": "Add root-cause step before closure",
            "cx culture": "Coach teams on key Customer Experience moments",
        }
        if capability_text in title_map:
            return title_map[capability_text]
        title_source = normalize_text(str(candidate.get("quick_win_guideline") or "")).strip()
        title = title_source.split(".")[0].strip() if title_source else ""
        if not title or len(title) > 90:
            title = (
                f"Renforcer {self._fr_capability_label(str(candidate['capability']))}"
                if self._is_french(language)
                else f"Strengthen {candidate['capability']}"
            )
        return title

    def _fallback_quick_win_today_text(self, candidate: dict[str, Any], language: str = "fr") -> str:
        capability_text = normalize_text(str(candidate.get("capability_raw") or candidate.get("capability") or "")).lower()
        today_map = self._fr_quick_win_today_map() if self._is_french(language) else {
            "decision-making": "Customer feedback is monitored, but it rarely shapes decisions, priorities, or roadmap choices in a structured way.",
            "ownership and governance": "A named owner exists, but cross-functional routines and escalation paths are still inconsistent.",
            "feedback collection": "Feedback is captured, but review routines and coverage across touchpoints are still incomplete.",
            "use of insights": "Customer information is available, but themes, root causes, and impact are not reviewed in a consistent way.",
            "channel consistency": "Customers can still face uneven handoffs or inconsistent answers across channels.",
            "journey visibility": "Teams improve isolated touchpoints, but no shared journey view drives coordinated action.",
            "measurement and continuous improvement": "Metrics are tracked, but they are not yet tied to ownership, decisions, or follow-through.",
            "acting on pain points": "Pain points are handled reactively, without a repeatable backlog, named owners, or closure discipline.",
            "cx culture": "Customer experience expectations are not yet reinforced through daily habits, coaching, or shared routines.",
        }
        if capability_text in today_map:
            return today_map[capability_text]
        rationale = normalize_text(str(candidate.get("current_rationale") or "")).strip()
        if rationale:
            return rationale
        if self._is_french(language):
            return f"{self._fr_capability_label(str(candidate['capability']))} reste inegal et depend encore de pratiques informelles."
        return f"{candidate['capability']} is still inconsistent and relies on informal habits instead of a repeatable routine."

    def _quick_win_after_text(self, candidate: dict[str, Any], language: str = "fr") -> str:
        after_text = normalize_text(str(candidate.get("after_text") or "")).strip()
        if after_text:
            if self._is_french(language):
                return self._localize_quick_win_after_text(after_text, candidate)
            return after_text
        if self._is_french(language):
            return f"{self._fr_capability_label(str(candidate['capability']))} devient plus clair, plus regulier et plus facile a piloter."
        return f"{candidate['capability']} becomes clearer, more repeatable, and easier for the team to sustain."

    def _finalize_quick_win_item(
        self,
        *,
        raw: dict[str, Any],
        candidate: dict[str, Any],
        fallback: FinalReportQuickWinItem,
        language: str = "fr",
    ) -> FinalReportQuickWinItem:
        title = normalize_text(str(raw.get("title") or "")).strip() or fallback.title
        today_text = normalize_text(str(raw.get("today_text") or "")).strip() or fallback.today_text
        owner = self._normalize_quick_win_owner_label(
            raw_owner=str(raw.get("owner") or candidate.get("owner_hint") or ""),
            axis=str(candidate.get("axis") or ""),
            capability=str(candidate.get("capability") or ""),
        )

        if self._is_french(language) and self._looks_like_english_quick_win_text(title):
            title = fallback.title
        if self._is_french(language) and self._looks_like_english_quick_win_text(today_text):
            today_text = fallback.today_text
        if not self._quick_win_title_matches_context(title=title, candidate=candidate, today_text=today_text):
            title = fallback.title
        if not self._quick_win_today_matches_context(today_text=today_text, candidate=candidate, title=title):
            today_text = fallback.today_text

        return FinalReportQuickWinItem(
            step=int(raw.get("step") or fallback.step),
            timeline_label=self._normalize_quick_win_label(raw.get("timeline_label"), fallback.timeline_label, language=language),
            title=title,
            owner=owner,
            today_text=today_text,
            after_text=self._quick_win_after_text(candidate, language=language),
        )

    def _post_process_quick_win_items(
        self,
        *,
        parsed: list[FinalReportQuickWinItem],
        candidates: list[dict[str, Any]],
        fallback: list[FinalReportQuickWinItem],
        language: str = "fr",
    ) -> list[FinalReportQuickWinItem]:
        finalized: list[FinalReportQuickWinItem] = []
        seen_after_keys: set[str] = set()
        for index, item in enumerate(parsed):
            after_text = normalize_text(item.after_text).strip() or fallback[index].after_text
            if self._is_generic_quick_win_after_text(after_text) or self._after_text_key(after_text) in seen_after_keys:
                after_text = fallback[index].after_text
            seen_after_keys.add(self._after_text_key(after_text))
            finalized.append(
                FinalReportQuickWinItem(
                    step=item.step,
                    timeline_label=item.timeline_label,
                    title=item.title,
                    owner=self._normalize_quick_win_owner_label(
                        raw_owner=item.owner,
                        axis=str(candidates[index].get("axis") or ""),
                        capability=str(candidates[index].get("capability") or ""),
                    ),
                    today_text=item.today_text,
                    after_text=self._localize_quick_win_after_text(after_text, candidates[index])
                    if self._is_french(language)
                    else after_text,
                )
            )
        return finalized

    def _quick_win_title_matches_context(self, *, title: str, candidate: dict[str, Any], today_text: str) -> bool:
        title_terms = self._quick_win_terms(title)
        context_terms = self._quick_win_terms(
            " ".join(
                [
                    str(candidate.get("capability") or ""),
                    str(candidate.get("quick_win_guideline") or ""),
                    str(today_text or ""),
                ]
            )
        )
        return bool(title_terms and title_terms.intersection(context_terms))

    def _quick_win_today_matches_context(self, *, today_text: str, candidate: dict[str, Any], title: str) -> bool:
        today_terms = self._quick_win_terms(today_text)
        context_terms = self._quick_win_terms(
            " ".join(
                [
                    str(candidate.get("capability") or ""),
                    str(candidate.get("current_rationale") or ""),
                    str(title or ""),
                ]
            )
        )
        return bool(today_terms and today_terms.intersection(context_terms))

    def _quick_win_terms(self, text: str | None) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", normalize_text(text).lower())
        stopwords = {
            "the", "and", "with", "from", "into", "that", "this", "your", "their", "they",
            "will", "than", "have", "has", "for", "more", "less", "over", "only", "still",
            "today", "after", "week", "month", "lead", "manager", "owner", "team", "customer",
        }
        return {token for token in tokens if len(token) > 3 and token not in stopwords}

    def _is_generic_quick_win_after_text(self, text: str) -> bool:
        lowered = normalize_text(text).lower().strip()
        generic_markers = (
            "improves customer experience",
            "better outcomes",
            "more repeatable",
            "easier to sustain",
            "drives improvement",
        )
        return any(marker in lowered for marker in generic_markers)

    def _after_text_key(self, text: str) -> str:
        return re.sub(r"\s+", " ", normalize_text(text).lower()).strip()

    def _fallback_quick_win_owner(self, *, axis: str, capability: str, language: str = "fr") -> str:
        capability_text = normalize_text(capability).lower()
        axis_key = self._normalize_axis_key(axis)
        is_fr = self._is_french(language)
        if "journey" in capability_text or "channel" in capability_text:
            return "Responsable Expérience Client" if is_fr else "Customer Experience Lead"
        if "feedback" in capability_text or axis_key == "analyze":
            return "Responsable Insights Client" if is_fr else "Insights Lead"
        if axis_key == "manage":
            return "Directeur des Opérations" if is_fr else "Operations Manager"
        if axis_key == "improve":
            return "Responsable Transformation" if is_fr else "Transformation Lead"
        return "Responsable Expérience Client" if is_fr else "Customer Experience Lead"

    async def _telecom_benchmark_pain_points(self, assessment_id: int) -> list[dict[str, Any]]:
        """The few weakest capabilities, with everything the benchmark needs to search on.

        The competitor benchmark is expensive -- web searches plus a model pass per candidate --
        so it runs against only the worst capabilities rather than all nine. Each one carries the
        client's own evidence plus the framework's rubric and level-3 guidance, so the search is
        for what a leader does about *this* weakness, not for the capability's name.
        """
        capability_rows = await self.capabilities.list_all_for_assessment(assessment_id=assessment_id)
        maturity_number_by_id = await self.maturity_levels.get_numbers()

        weakest = self._weakest_scored_capabilities(capability_rows, maturity_number_by_id)
        if not weakest:
            return []

        capability_ids = [int(item["capability_id"]) for item in weakest]
        recommendation_rows = await self.capabilities.get_recommendations_for_scores(assessment_id=assessment_id)
        recommendation_by_capability = {int(row["capability_id"]): row for row in recommendation_rows}
        description_by_capability = await self.capabilities.get_capability_descriptions(capability_ids)
        rubrics_by_capability = await self.capabilities.get_rubrics_for_capabilities(
            capability_ids=capability_ids
        )
        level3_by_capability = await self.capabilities.get_level3_recommendations_for_capabilities(
            capability_ids=capability_ids
        )

        return [
            {
                "capability": item["capability"],
                "capability_description": description_by_capability.get(int(item["capability_id"])),
                "rationale": item["rationale"],
                "maturity_number": item["maturity_number"],
                "evidence_to_cite": clean_optional_text(
                    (recommendation_by_capability.get(int(item["capability_id"])) or {}).get("evidence_to_cite")
                ),
                "action_hints": clean_optional_text(
                    (recommendation_by_capability.get(int(item["capability_id"])) or {}).get("initiative_suggestions")
                ),
                "rubric_description": self._rubric_description_for_level(
                    rubrics_by_capability.get(int(item["capability_id"]), []),
                    maturity_level_id=item["maturity_level_id"],
                ),
                # Level 3 is the top of the framework, so its guidance describes where the
                # capability is heading -- which is what makes a leader's practice comparable.
                "level3_action_hints": clean_optional_text(
                    (level3_by_capability.get(int(item["capability_id"])) or {}).get("initiative_suggestions")
                ),
            }
            for item in weakest
        ]

    @staticmethod
    def _weakest_scored_capabilities(
        capability_rows: list[dict[str, Any]], maturity_number_by_id: dict[int, int]
    ) -> list[dict[str, Any]]:
        """The lowest-scoring assessed capabilities, worst first.

        Ties break on confidence and then on name, so the same assessment always produces the same
        benchmark -- otherwise a re-run could swap which capabilities were researched and quietly
        change the report.
        """
        scored: list[dict[str, Any]] = []
        for row in capability_rows:
            if str(row.get("assessment_status") or "not_assessed") != "assessed":
                continue
            maturity_level_id = row.get("maturity_level_id")
            if maturity_level_id is None:
                continue
            maturity_number = maturity_number_by_id.get(int(maturity_level_id))
            if maturity_number is None:
                continue
            scored.append(
                {
                    "capability_id": int(row.get("id")),
                    "capability": str(row.get("label") or ""),
                    "rationale": clean_optional_text(row.get("rationale") or row.get("evidence_text")),
                    "maturity_level_id": int(maturity_level_id),
                    "maturity_number": maturity_number,
                    "confidence": float(row.get("confidence") or 0.0),
                }
            )

        scored.sort(
            key=lambda item: (
                int(item["maturity_number"]),
                float(item["confidence"]),
                str(item["capability"]),
            )
        )
        return scored[:_MAX_BENCHMARK_PAIN_POINTS]

    @staticmethod
    def _rubric_description_for_level(
        rubrics: list[dict[str, Any]], *, maturity_level_id: int | None
    ) -> str | None:
        """What the framework says this capability looks like at the level it actually scored."""
        return next(
            (
                clean_optional_text(rubric.get("description"))
                for rubric in rubrics
                if int(rubric.get("maturity_level_id") or 0) == int(maturity_level_id or 0)
            ),
            None,
        )


    async def _get_or_generate_report_synthesis(
        self,
        assessment: Any,
        overall_band: str,
        overall_score: float,
        strongest_axis: str,
        priority_axis: str,
        axes: list[FinalReportAxisItem],
        strengths: list[FinalReportThemeItem],
        pain_points: list[FinalReportThemeItem],
        strengths_count: int,
        pain_points_count: int,
        capabilities: list[FinalReportCapabilityItem],
        refresh_synthesis: bool = False,
    ) -> dict[str, str | None]:
        cached_summary = normalize_text(getattr(assessment, "executive_summary_text", None))
        cached_priority = normalize_text(getattr(assessment, "priority_message_text", None))
        if cached_summary and cached_priority and not refresh_synthesis:
            return {"executive_summary": cached_summary, "priority_message": cached_priority}

        degraded = self._degraded_report_synthesis(priority_axis=priority_axis, language=getattr(assessment, "language", "fr"))
        try:
            synthesis = await self.llm.generate_report_synthesis(
                company_name=getattr(assessment.company, "name", "This company"),
                overall_maturity_band=overall_band,
                overall_score_percent=overall_score,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                strengths_count=strengths_count,
                pain_points_count=pain_points_count,
                axes=[axis_item.model_dump() for axis_item in axes],
                strengths=[
                    {
                        **item.model_dump(),
                        "confidence_label": self._confidence_label(capabilities, item.capability, item.axis),
                        "evidence_strength": self._evidence_strength_label(capabilities, item.capability, item.axis),
                    }
                    for item in strengths
                ],
                pain_points=[
                    {
                        **item.model_dump(),
                        "confidence_label": self._confidence_label(capabilities, item.capability, item.axis),
                        "evidence_strength": self._evidence_strength_label(capabilities, item.capability, item.axis),
                    }
                    for item in pain_points
                ],
                language=getattr(assessment, "language", "fr"),
            )
        except Exception as exc:
            logger.error(
                "Report synthesis generation failed; returning degraded summary.",
                extra={
                    "assessment_id": getattr(assessment, "id", None),
                    "company_name": getattr(getattr(assessment, "company", None), "name", None),
                    "priority_axis": priority_axis,
                    "strongest_axis": strongest_axis,
                    "exception_type": type(exc).__name__,
                },
                exc_info=True,
            )
            return degraded

        executive_summary = normalize_text(synthesis.get("executive_summary")) or degraded["executive_summary"]
        priority_message = normalize_text(synthesis.get("priority_message")) or degraded["priority_message"]
        if str(getattr(assessment, "status", "")) == ASSESSMENT_STATUS_COMPLETED:
            try:
                async with self.uow:
                    await self.assessments.update_report_synthesis(
                        assessment=assessment,
                        executive_summary_text=executive_summary,
                        priority_message_text=priority_message,
                    )
            except Exception as exc:
                logger.error("Could not persist report synthesis cache: %s", exc, exc_info=True)
        return {"executive_summary": executive_summary, "priority_message": priority_message}

    def _degraded_report_synthesis(self, priority_axis: str, language: str = "fr") -> dict[str, str]:
        is_french = (language or "").lower().startswith("fr")
        if is_french:
            axis_mapping = {
                "manage": "Gérer",
                "analyze": "Analyser",
                "improve": "Améliorer",
            }
            axis_fr = axis_mapping.get(str(priority_axis).lower().strip(), priority_axis)
            return {
                "executive_summary": (
                    "La synthèse du rapport est temporairement indisponible. "
                    "Veuillez vous référer aux résultats détaillés ci-dessous."
                ),
                "priority_message": (
                    f"La prochaine étape consiste à examiner les résultats pour l'axe '{axis_fr}' et à prioriser les éléments ayant la maturité la plus faible."
                ),
            }
        return {
            "executive_summary": (
                "Report synthesis is temporarily unavailable. "
                "Please refer to your detailed findings below."
            ),
            "priority_message": (
                f"The next step is to review the {priority_axis} findings and prioritize the lowest maturity items."
            ),
        }


    def _build_working_missing_section(
        self,
        *,
        axes: list[FinalReportAxisItem],
        capabilities: list[FinalReportCapabilityItem],
        strengths: list[FinalReportThemeItem],
        pain_points: list[FinalReportThemeItem],
        strongest_axis: str,
        priority_axis: str,
        axis_maturity_content: dict[tuple[str, int], dict[str, str | None]],
        rubric_content_by_capability_id: dict[int, dict[str, str | None]],
        language: str | None = None,
    ) -> list[FinalReportWorkingMissingAxis]:
        axis_order = ("manage", "analyze", "improve")
        is_french = (language or "").lower().startswith("fr")
        if is_french:
            label_map = {"manage": "Gérer", "analyze": "Analyser", "improve": "Améliorer"}
        else:
            label_map = {"manage": "Manage", "analyze": "Analyze", "improve": "Improve"}
        axis_lookup = {
            self._normalize_axis_key(item.axis): item
            for item in axes
            if self._normalize_axis_key(item.axis) in axis_order
        }
        capability_lookup: dict[str, list[FinalReportCapabilityItem]] = {key: [] for key in axis_order}
        for item in capabilities:
            axis_key = self._normalize_axis_key(item.axis)
            if axis_key in capability_lookup:
                capability_lookup[axis_key].append(item)

        strengths_lookup: dict[str, list[FinalReportThemeItem]] = {key: [] for key in axis_order}
        for item in strengths:
            axis_key = self._normalize_axis_key(item.axis)
            if axis_key in strengths_lookup:
                strengths_lookup[axis_key].append(item)

        pain_lookup: dict[str, list[FinalReportThemeItem]] = {key: [] for key in axis_order}
        for item in pain_points:
            axis_key = self._normalize_axis_key(item.axis)
            if axis_key in pain_lookup:
                pain_lookup[axis_key].append(item)

        result: list[FinalReportWorkingMissingAxis] = []
        for axis_key in axis_order:
            axis_item = axis_lookup.get(
                axis_key,
                FinalReportAxisItem(
                    axis=label_map[axis_key],
                    score_percent=0.0,
                    maturity_band="Not scored",
                    axis_level=None,
                    axis_level_label=None,
                ),
            )
            axis_capabilities = capability_lookup.get(axis_key, [])
            working = self._build_working_missing_items(
                prioritized=strengths_lookup.get(axis_key, []),
                capabilities=axis_capabilities,
                prefer_basic=False,
                rubric_content_by_capability_id=rubric_content_by_capability_id,
            )
            missing = self._build_working_missing_items(
                prioritized=pain_lookup.get(axis_key, []),
                capabilities=axis_capabilities,
                prefer_basic=True,
                rubric_content_by_capability_id=rubric_content_by_capability_id,
            )
            subtitle, intro, stat_note = self._working_missing_axis_copy(
                axis_key=axis_key,
                axis_label=label_map[axis_key],
                maturity_band=axis_item.maturity_band,
                axis_level=axis_item.axis_level,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                axis_maturity_content=axis_maturity_content,
                language=language,
            )
            result.append(
                FinalReportWorkingMissingAxis(
                    axis=axis_key,
                    label=label_map[axis_key],
                    score_percent=axis_item.score_percent,
                    maturity_band=axis_item.maturity_band,
                    axis_level=axis_item.axis_level,
                    axis_level_label=axis_item.axis_level_label,
                    subtitle=subtitle,
                    intro=intro,
                    stat_note=stat_note,
                    working=working,
                    missing=missing,
                )
            )
        return result

    def _build_working_missing_items(
        self,
        *,
        prioritized: list[FinalReportThemeItem],
        capabilities: list[FinalReportCapabilityItem],
        prefer_basic: bool,
        rubric_content_by_capability_id: dict[int, dict[str, str | None]],
    ) -> list[FinalReportWorkingMissingItem]:
        items: list[FinalReportWorkingMissingItem] = []
        seen: set[str] = set()
        capability_lookup = {
            (self._normalize_axis_key(item.axis), normalize_text(item.capability).lower()): item
            for item in capabilities
        }

        def push(capability_name: str, maturity_band: str, summary: str | None, evidence_snippet: str | None) -> None:
            key = normalize_text(capability_name).lower()
            if not key or key in seen:
                return
            seen.add(key)
            items.append(
                FinalReportWorkingMissingItem(
                    capability=capability_name,
                    maturity_band=maturity_band,
                    summary=summary,
                    evidence_snippet=evidence_snippet,
                )
            )

        for item in prioritized:
            capability_match = capability_lookup.get(
                (self._normalize_axis_key(item.axis), normalize_text(item.capability).lower())
            )
            display = self._working_missing_display_copy(
                capability=capability_match,
                rubric_content_by_capability_id=rubric_content_by_capability_id,
            )
            push(
                item.capability,
                item.maturity_band,
                display["summary"] or normalize_text(item.recommendation) or normalize_text(item.rationale),
                display["evidence_snippet"] or normalize_text(item.rationale) or normalize_text(item.recommendation),
            )

        sorted_capabilities = sorted(
            capabilities,
            key=lambda item: (
                0 if (item.maturity_band == "Basic") == prefer_basic else 1,
                float(item.confidence or 0.0) if not prefer_basic else -float(item.confidence or 0.0),
                item.capability,
            ),
        )
        for item in sorted_capabilities:
            if len(items) >= 3:
                break
            if prefer_basic and item.maturity_band != "Basic":
                continue
            if not prefer_basic and item.maturity_band == "Basic":
                continue
            display = self._working_missing_display_copy(
                capability=item,
                rubric_content_by_capability_id=rubric_content_by_capability_id,
            )
            push(
                item.capability,
                item.maturity_band,
                display["summary"] or normalize_text(item.recommendation) or normalize_text(item.rationale),
                display["evidence_snippet"] or normalize_text(item.rationale) or normalize_text(item.recommendation),
            )
        return items[:3]

    def _current_rubric_content_by_capability(
        self,
        *,
        capability_rows: list[dict[str, Any]],
        rubrics_by_capability: dict[int, list[dict]],
        language: str | None = None,
    ) -> dict[int, dict[str, str | None]]:
        result: dict[int, dict[str, str | None]] = {}
        for row in capability_rows:
            capability_id = row.get("id")
            maturity_level_id = row.get("maturity_level_id")
            if capability_id is None or maturity_level_id is None:
                continue
            for rubric in rubrics_by_capability.get(int(capability_id), []):
                if int(rubric.get("maturity_level_id") or 0) != int(maturity_level_id):
                    continue
                result[int(capability_id)] = {
                    "description": self._translate_rubric_description(
                        normalize_text(str(rubric.get("description") or "")).strip(), language
                    ) or None,
                    "card_summary": self._translate_rubric_description(
                        normalize_text(str(rubric.get("card_summary") or "")).strip(), language
                    ) or None,
                }
                break
        return result

    def _working_missing_display_copy(
        self,
        *,
        capability: FinalReportCapabilityItem | None,
        rubric_content_by_capability_id: dict[int, dict[str, str | None]],
    ) -> dict[str, str | None]:
        if capability is None or capability.capability_id is None:
            return {"summary": None, "evidence_snippet": None}
        content = rubric_content_by_capability_id.get(int(capability.capability_id), {})
        return {
            "summary": content.get("card_summary") or content.get("description"),
            "evidence_snippet": None,
        }

    def _working_missing_axis_copy(
        self,
        *,
        axis_key: str,
        axis_label: str,
        maturity_band: str,
        axis_level: int | None,
        strongest_axis: str,
        priority_axis: str,
        axis_maturity_content: dict[tuple[str, int], dict[str, str | None]],
        language: str = "fr",
    ) -> tuple[str, str, str]:
        """The three pieces of copy for one axis panel: subtitle, intro, and the stat note.

        Admin-authored content wins for the subtitle and the intro where it exists. The stat note
        has no authored equivalent, so it always comes from the table -- it depends only on the
        part this axis plays in the report, never on whether the intro was overridden.
        """
        content = (
            axis_maturity_content.get((axis_key, int(axis_level)))
            if axis_level is not None
            else None
        ) or {}
        lang = "fr" if (language or "").lower().startswith("fr") else "en"

        if axis_key == self._normalize_axis_key(strongest_axis):
            role = "strongest"
        elif axis_key == self._normalize_axis_key(priority_axis):
            role = "priority"
        else:
            role = "balanced"

        subtitle = content.get("axis_description") or _AXIS_BAND_SUBTITLE[_maturity_band_key(maturity_band)][
            lang
        ].format(axis_label=axis_label)
        intro = content.get("axis_panel_copy") or _AXIS_ROLE_INTRO[role][lang].format(axis_label=axis_label)
        return subtitle, intro, _AXIS_ROLE_STAT_NOTE[role][lang]

    @staticmethod
    def _normalize_axis_key(value: str | None) -> str:
        normalized = normalize_text(value).lower().strip()
        if normalized.startswith("manag"):
            return "manage"
        if normalized.startswith("anal"):
            return "analyze"
        if normalized.startswith("improv"):
            return "improve"
        return normalized

    def _benchmark_evidence_signals(
        self,
        capabilities: list[FinalReportCapabilityItem],
        pain_points: list[FinalReportThemeItem],
        priority_axis: str,
    ) -> list[BenchmarkEvidenceSignal]:
        signals: list[BenchmarkEvidenceSignal] = []
        seen: set[tuple[str, str]] = set()

        def add_signal(capability: str, maturity_band: str, rationale: str | None, axis: str) -> None:
            key = (axis, capability)
            if key in seen:
                return
            seen.add(key)
            signals.append(
                BenchmarkEvidenceSignal(
                    capability=capability,
                    maturity_band=maturity_band,
                    rationale=rationale,
                )
            )

        for item in pain_points:
            add_signal(
                capability=item.capability,
                maturity_band=item.maturity_band,
                rationale=item.rationale,
                axis=item.axis,
            )

        for item in capabilities:
            if len(signals) >= 6:
                break
            if item.axis != priority_axis:
                continue
            add_signal(
                capability=item.capability,
                maturity_band=item.maturity_band,
                rationale=item.rationale,
                axis=item.axis,
            )
        return signals

    def _band_from_level(self, level: int | None, assessment_status: str) -> str:
        return MaturityScoring.band_from_level(level=level, assessment_status=assessment_status)

    @staticmethod
    def _rounded_level(average: float) -> int | None:
        if average <= 0:
            return None
        return max(1, min(3, int(round(average))))

    @staticmethod
    def _level_label(level: int | None) -> str | None:
        if level is None:
            return None
        return f"{level} / 3"

    @staticmethod
    def _report_date_label(value: Any) -> str | None:
        if value is None:
            return None
        try:
            return value.strftime("%B %Y")
        except Exception:
            return None

    def _hero_message(
        self,
        executive_summary: str | None,
        priority_message: str | None,
        overall_band: str,
        priority_axis: str,
    ) -> str:
        summary = normalize_text(executive_summary)
        priority = normalize_text(priority_message)
        if summary and priority and priority.lower() not in summary.lower():
            return f"{summary} {priority}"
        if summary:
            return summary
        if priority:
            return priority
        if overall_band == "Not scored":
            return "The assessment is not yet complete enough to generate a reliable maturity summary."
        return f"The next step is to strengthen the {priority_axis} axis and raise overall maturity."

    def _competitive_company_note(
        self,
        *,
        overall_band: str,
        strongest_axis: str,
        priority_axis: str,
    ) -> str:
        strongest = normalize_text(strongest_axis).lower() if strongest_axis else "your strongest area"
        priority = normalize_text(priority_axis).lower() if priority_axis else "your next priority"
        if overall_band == "Basic":
            return (
                f"Early customer-experience foundations are visible, with the biggest opportunity in {priority}."
            )
        if overall_band == "Advanced":
            return (
                f"Customer experience is already being treated as a competitive system, with {strongest} leading today."
            )
        return (
            f"Solid ownership culture and visible progress, with {priority} still needing a more repeatable operating model."
        )

    def _soften_report_rationale(self, rationale: str | None, confidence: float | None) -> str | None:
        text = normalize_text(rationale)
        if not text:
            return None
        if confidence is None or confidence >= self.settings.RECOMMENDATION_MIN_CONFIDENCE:
            return text

        lowered = text.lower()
        if lowered.startswith(("there are early signs", "current evidence suggests", "the current evidence points to")):
            return text
        if confidence >= self.settings.REPORT_MEDIUM_CONFIDENCE_THRESHOLD:
            return (
                f"Current evidence suggests that {text[0].lower() + text[1:]}"
                if len(text) > 1
                else f"Current evidence suggests that {text.lower()}"
            )
        return (
            f"There are early signs that {text[0].lower() + text[1:]}"
            if len(text) > 1
            else f"There are early signs that {text.lower()}"
        )

    def _confidence_label(
        self,
        capabilities: list[FinalReportCapabilityItem],
        capability_name: str,
        axis_name: str,
    ) -> str:
        match = next(
            (item for item in capabilities if item.capability == capability_name and item.axis == axis_name),
            None,
        )
        confidence = float(match.confidence or 0.0) if match and match.confidence is not None else 0.0
        if confidence >= self.settings.REPORT_HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        if confidence >= self.settings.REPORT_MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        return "low"

    def _evidence_strength_label(
        self,
        capabilities: list[FinalReportCapabilityItem],
        capability_name: str,
        axis_name: str,
    ) -> str:
        match = next(
            (item for item in capabilities if item.capability == capability_name and item.axis == axis_name),
            None,
        )
        if match is None:
            return "low"
        rationale_length = len(normalize_text(match.rationale or ""))
        confidence = float(match.confidence or 0.0) if match.confidence is not None else 0.0
        if (
            confidence >= self.settings.REPORT_HIGH_CONFIDENCE_THRESHOLD
            and rationale_length >= self.settings.report_high_evidence_min_chars
        ):
            return "high"
        if (
            confidence >= self.settings.REPORT_MEDIUM_CONFIDENCE_THRESHOLD
            and rationale_length >= self.settings.report_medium_evidence_min_chars
        ):
            return "medium"
        return "low"

    def _translate_capability_name(self, capability: str, language: str | None) -> str:
        if not self._is_french(language):
            if capability.lower().strip() == "cx culture":
                return "Customer experience culture"
            return capability
        key = normalize_text(capability).lower().strip()
        labels = {
            "cx culture": "Culture de l'expérience client",
            "decision-making": "Prise de décision",
            "ownership and governance": "Ownership et gouvernance",
            "feedback collection": "Collecte des retours clients",
            "use of insights": "Exploitation des insights",
            "channel consistency": "Cohérence des canaux",
            "journey visibility": "Visibilité des parcours",
            "measurement and continuous improvement": "Mesure et amélioration continue",
            "acting on pain points": "Traitement des irritants",
        }
        return labels.get(key, capability)

    def _translate_rubric_description(self, description: str | None, language: str | None) -> str | None:
        if not description or not self._is_french(language):
            return description
        key = normalize_text(description).lower().strip()
        translations = {
            "customer-focused behaviours are ad hoc, weakly reinforced, and largely dependent on individual managers or frontline goodwill.":
                "Les comportements orientés client sont ponctuels, peu encouragés et dépendent largement de la bonne volonté des managers ou des équipes terrain.",
            "some coaching, training, service standards, or recognition exist, but adoption is partial and not yet fully embedded in routines.":
                "Des actions de coaching, de formation, des standards de service ou de la reconnaissance existent, mais leur adoption reste partielle et non ancrée dans le quotidien.",
            "customer-focused behaviours are actively reinforced through leadership routines, coaching, recognition, practical standards, and quality feedback.":
                "Les comportements orientés client sont activement renforcés par des routines managériales, du coaching, de la reconnaissance, des standards pratiques et des retours qualité.",
            "accountability is informal or fragmented, with no consistent owner, governance routine, or follow-up discipline for customer issues.":
                "La responsabilisation est informelle ou fragmentée, sans responsable désigné, routine de gouvernance ou processus de suivi structuré pour les problèmes clients.",
            "a named owner or central team exists, and some governance routines are in place, but coordination and follow-through are not yet fully reliable.":
                "Un responsable ou une équipe centrale existe et des routines de gouvernance sont en place, mais la coordination et le suivi ne sont pas encore totalement fiables.",
            "customer issues are managed through recurring governance, clear owners, escalation paths, action logs, and visible cross-functional accountability.":
                "Les problèmes clients sont gérés à travers une gouvernance récurrente, des responsables clairs, des circuits d'escalade, des registres d'actions et une responsabilité transverse visible.",
            "customer evidence rarely changes decisions; priorities are mostly internal, reactive, or driven by individual judgement.":
                "Les retours clients influencent rarement les décisions ; les priorités sont principalement internes, réactives ou basées sur des jugements individuels.",
            "customer evidence influences some decisions, but the practice is partial, siloed, or inconsistent across teams.":
                "Les retours clients influence certaines décisions, mais cette pratique reste partielle, cloisonnée ou incohérente selon les équipes.",
            "customer evidence systematically shapes decisions through governance, named owners, documented trade-offs, and follow-up.":
                "Les retours clients façonnent systématiquement les décisions via la gouvernance, des responsables désignés, des arbitrages documentés et un suivi rigoureux.",
            "feedback is collected inconsistently or through a few isolated channels, with weak logging, ownership, and review rhythm.":
                "Les retours sont collectés de manière incohérente ou via quelques canaux isolés, avec un suivi, une attribution et un rythme de revue insuffisants.",
            "feedback is captured through some defined channels or tools, but coverage, ownership, tagging, and review cadence are inconsistent.":
                "Les retours sont recueillis via des canaux ou outils définis, mais la couverture, l'attribution, la catégorisation et le rythme de revue restent irréguliers.",
            "feedback is captured across key touchpoints through structured channels with clear ownership, tagging, and regular review.":
                "Les retours sont captés sur les principaux points de contact via des canaux structurés avec des responsabilités claires, une catégorisation précise et des revues régulières.",
            "feedback is observed informally, with little evidence of theme review, root-cause analysis, or explicit prioritization logic.":
                "Les retours clients sont observés de manière informelle, sans réelle analyse des thématiques, recherche des causes racines ou logique claire de priorisation.",
            "some theme review or prioritization exists, but the process is inconsistent and not yet decision-ready.":
                "Une certaine analyse thématique ou priorisation existe, mais le processus reste irrégulier et n'est pas encore prêt à guider les décisions.",
            "feedback is translated into actionable insight through pattern analysis, root-cause work, and clear prioritization criteria.":
                "Les retours sont traduits en actions concrètes grâce à l'analyse des tendances, la recherche des causes racines et des critères clairs de priorisation.",
            "channels operate separately, with inconsistent standards, weak handoffs, and limited shared customer context.":
                "Les canaux fonctionnent séparément, avec des standards incohérents, des transitions fluides limitées et peu de partage du contexte client.",
            "some shared standards or handoff practices exist, but consistency is uneven across the experience.":
                "Certains standards communs ou pratiques de transition existent, mais la cohérence reste inégale d'un canal à l'autre.",
            "channels are managed with shared context, consistent standards, and active monitoring for consistency issues.":
                "Les canaux sont gérés avec un contexte client partagé, des standards cohérents et un suivi actif pour corriger les écarts de cohérence.",
            "journey visibility is weak or absent; teams mainly see isolated touchpoints rather than the full customer path.":
                "La visibilité sur les parcours est faible ou inexistante ; les équipes se concentrent sur des points de contact isolés plutôt que sur l'ensemble du parcours.",
            "some journeys are mapped or discussed, but ownership, updates, and pain-point tracking remain inconsistent.":
                "Certains parcours sont cartographiés ou discutés, mais leur mise à jour, l'attribution des responsabilités et le suivi des irritants restent irréguliers.",
            "key journeys are owned, documented, and reviewed cross-functionally to guide prioritization and improvements.":
                "Les parcours clés sont documentés, attribués à des responsables et revus de manière transverse pour guider les priorités et les améliorations.",
            "measures are limited or disconnected from action, with little evidence of a regular improvement loop.":
                "Les indicateurs de mesure sont limités ou déconnectés des actions, sans processus régulier d'amélioration continue.",
            "measures are tracked and reviewed, but ownership, targets, and business linkage are incomplete.":
                "Les indicateurs sont suivis et analysés, mais l'attribution des responsabilités, la définition des objectifs et le lien avec la performance globale restent incomplets.",
            "measures are tied to targets, owners, business outcomes, experiments, and systematic improvement loops.":
                "Les indicateurs sont directement reliés à des objectifs, des responsables, des résultats opérationnels, des tests et des boucles d'amélioration continue.",
            "pain points are handled reactively with little backlog, ownership, closure discipline, or validation.":
                "Le traitement des irritants est réactif, sans gestion de backlog, responsabilité claire, discipline de clôture ou validation de l'efficacité.",
            "some backlog or owner process exists, but prioritization and closure discipline are inconsistent.":
                "Un backlog ou processus de suivi existe, mais la priorisation et la rigueur dans la résolution finale restent irrégulières.",
            "pain points are managed through a repeatable improvement loop with prioritization, owners, closure checks, and validation.":
                "Les irritants sont gérés via une boucle d'amélioration continue répétable comprenant une priorisation, des responsables dédiés, un contrôle des clôtures et une validation.",
        }
        return translations.get(key, description)


