"""Reading and writing an assessment, with the context every caller turns out to need.

`_with_context()` eagerly loads the company (and its sector, size and region) plus the current
axis on every read. That is not caution: an assessment is almost never useful on its own -- the
question composer needs the sector, the report needs the size, the progress bar needs the axis --
and fetching them lazily turned one read into five.

`get_by_id_for_update` is the same query holding a row lock. Answering takes a lock because two
browser tabs on one assessment would otherwise both read the same version, both score, and one
would silently overwrite the other. Take the lock whenever the assessment is about to change;
`get_by_id` is for reads that only display.
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.text_normalization import normalize_text
from app.db.models.assessment import Assessment
from app.db.models.assessment_answer import AssessmentAnswer
from app.db.models.assessment_insight import AssessmentInsight
from app.db.models.recommendation_output import RecommendationOutput
from app.db.models.assessment_score import AssessmentScore
from app.db.models.capability import Capability
from app.db.models.company import Company
from app.db.models.maturity_level import MaturityLevel
from app.db.models.region import Region


class AssessmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _with_context(self):
        return (
            joinedload(Assessment.company).joinedload(Company.sector),
            joinedload(Assessment.company).joinedload(Company.company_size),
            joinedload(Assessment.company).joinedload(Company.region_ref),
            joinedload(Assessment.current_axis),
        )

    async def get_by_id(self, assessment_id: int) -> Assessment | None:
        result = await self.db.execute(
            select(Assessment)
            .options(*self._with_context())
            .where(Assessment.id == assessment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, assessment_id: int) -> Assessment | None:
        result = await self.db.execute(
            select(Assessment)
            .options(*self._with_context())
            .where(Assessment.id == assessment_id)
            .with_for_update(of=Assessment)
        )
        return result.scalar_one_or_none()

    async def get_maturity_level_by_number(self, level_number: int) -> MaturityLevel | None:
        result = await self.db.execute(
            select(MaturityLevel).where(MaturityLevel.level_number == level_number)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        company_id: int,
        status: str,
        current_axis_id: int | None,
        prompt_profile: str = "consultant_guided",
        language: str = "fr",
    ) -> Assessment:
        assessment = Assessment(
            company_id=company_id,
            status=status,
            current_axis_id=current_axis_id,
            prompt_profile=prompt_profile,
            language=language,
        )
        self.db.add(assessment)
        await self.db.flush()
        return assessment

    async def initialize_scores(self, assessment_id: int) -> None:
        result = await self.db.execute(select(Capability))
        capabilities = result.scalars().all()
        links = [
            AssessmentScore(
                assessment_id=assessment_id,
                capability_id=c.id,
                maturity_level_id=None,
                assessment_status="not_assessed",
                confidence=None,
                justification=None,
            )
            for c in capabilities
        ]
        self.db.add_all(links)

    async def list_assessments(
        self,
        limit: int = 50,
        offset: int = 0,
        region_code: str | None = None,
    ) -> list[Assessment]:
        statement = (
            select(Assessment)
            .options(*self._with_context())
            .join(Company, Company.id == Assessment.company_id)
        )
        if region_code:
            statement = statement.join(Region, Region.id == Company.region_id).where(
                Region.name == region_code
            )
        result = await self.db.execute(statement.order_by(Assessment.id.desc()).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def add_insight(
        self,
        assessment_id: int,
        capability_id: int | None,
        insight_text: str,
        maturity_level_id: int | None,
        confidence: float | None,
        justification: str | None,
        evidence_text: str | None,
    ) -> None:
        self.db.add(
            AssessmentInsight(
                assessment_id=assessment_id,
                capability_id=capability_id,
                insight_text=insight_text,
                maturity_level_id=maturity_level_id,
                confidence=confidence,
                justification=justification,
                evidence_text=evidence_text,
            )
        )

    async def get_answers_by_capability(
        self, assessment_id: int, capability_ids: list[int]
    ) -> dict[int, list[str]]:
        """The respondent's own answers for each capability, oldest first.

        Each entry pairs the question with the answer, because these are handed to a model as
        evidence and an answer read without its question is frequently meaningless ("about half").
        Answers with no text are skipped rather than stored as blanks.
        """
        if not capability_ids:
            return {}
        result = await self.db.execute(
            select(
                AssessmentAnswer.capability_id,
                AssessmentAnswer.question,
                AssessmentAnswer.answer,
            )
            .where(
                AssessmentAnswer.assessment_id == assessment_id,
                AssessmentAnswer.capability_id.in_(capability_ids),
            )
            .order_by(AssessmentAnswer.created_at.asc(), AssessmentAnswer.id.asc())
        )

        by_capability: dict[int, list[str]] = {}
        for capability_id, question, answer in result.all():
            if capability_id is None:
                continue
            answer_text = normalize_text(str(answer or "")).strip()
            if not answer_text:
                continue
            question_text = normalize_text(str(question or "")).strip()
            by_capability.setdefault(int(capability_id), []).append(
                f"Q: {question_text} A: {answer_text}" if question_text else answer_text
            )
        return by_capability

    async def get_insight_texts_by_capability(
        self, assessment_id: int, capability_ids: list[int]
    ) -> dict[int, list[str]]:
        """What the diagnostic concluded about each capability, newest first.

        The insight, its justification and its evidence are flattened into one string per insight:
        downstream they are read as a single block of context, never as separate fields.
        """
        if not capability_ids:
            return {}
        result = await self.db.execute(
            select(
                AssessmentInsight.capability_id,
                AssessmentInsight.insight_text,
                AssessmentInsight.justification,
                AssessmentInsight.evidence_text,
            )
            .where(
                AssessmentInsight.assessment_id == assessment_id,
                AssessmentInsight.capability_id.in_(capability_ids),
            )
            .order_by(AssessmentInsight.created_at.desc(), AssessmentInsight.id.desc())
        )

        by_capability: dict[int, list[str]] = {}
        for capability_id, insight_text, justification, evidence_text in result.all():
            if capability_id is None:
                continue
            combined = " ".join(
                part
                for part in (
                    normalize_text(str(insight_text or "")).strip(),
                    normalize_text(str(justification or "")).strip(),
                    normalize_text(str(evidence_text or "")).strip(),
                )
                if part
            )
            if combined:
                by_capability.setdefault(int(capability_id), []).append(combined)
        return by_capability

    async def replace_recommendation_outputs(self, assessment_id: int, items: list[dict]) -> None:
        await self.db.execute(
            delete(RecommendationOutput).where(RecommendationOutput.assessment_id == assessment_id)
        )
        if not items:
            return
        rows = [
            RecommendationOutput(
                assessment_id=assessment_id,
                capability_id=item.get("capability_id"),
                maturity_level_id=item.get("maturity_level_id"),
                generated_text=item["generated_text"],
                priority=item.get("priority"),
            )
            for item in items
        ]
        self.db.add_all(rows)

    async def list_recommendation_outputs(self, assessment_id: int) -> list[RecommendationOutput]:
        result = await self.db.execute(
            select(RecommendationOutput).where(RecommendationOutput.assessment_id == assessment_id)
        )
        return list(result.scalars().all())

    async def update_report_synthesis(
        self,
        assessment: Assessment,
        executive_summary_text: str,
        priority_message_text: str,
    ) -> None:
        assessment.executive_summary_text = executive_summary_text
        assessment.priority_message_text = priority_message_text
        await self.db.flush()

    async def update_leaders_snapshot_cache(
        self,
        assessment: Assessment,
        leaders_snapshot_payload: dict | None,
        leaders_snapshot_status: str | None = None,
        leaders_snapshot_generated_at: datetime | None = None,
        leaders_snapshot_error: str | None = None,
    ) -> None:
        assessment.leaders_snapshot_payload = leaders_snapshot_payload
        if leaders_snapshot_status is not None:
            assessment.leaders_snapshot_status = leaders_snapshot_status
        assessment.leaders_snapshot_generated_at = leaders_snapshot_generated_at
        assessment.leaders_snapshot_error = leaders_snapshot_error
        await self.db.flush()
