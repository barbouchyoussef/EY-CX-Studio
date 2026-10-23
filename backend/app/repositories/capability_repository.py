"""Database access for the CX capability framework and one assessment's progress through it.

The reference side is fixed reference data seeded by the migrations: nine capabilities across
three axes (Manage / Analyze / Improve), each with maturity rubrics describing what levels 1-3
look like. The per-assessment side is what has been covered so far, and the score and evidence
recorded for each.

Two groups of query exist for two different consumers, which is why the class is large:

  * the **conversation** needs to know what is still uncovered, so it can choose what to ask next
    (`get_axis_progress`, `list_for_axis`, `mark_covered`);
  * the **report** needs everything at once, joined with rubric text and level-3 guidance
    (`get_rubrics_for_capabilities`, `get_axis_maturity_content`, `get_recommendations_for_scores`).

Those bulk getters return dictionaries keyed by id specifically to avoid a query per capability
while a report is being assembled.
"""

import re

from sqlalchemy import func, inspect, literal, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_normalization import clean_optional_text, normalize_text
from app.domain.constants import axis_name_variants, normalize_axis_code, normalize_axis_name
from app.db.models.capability_maturity_rubric import CapabilityMaturityRubric
from app.db.models.assessment_insight import AssessmentInsight
from app.db.models.assessment_score import AssessmentScore
from app.db.models.axis import Axis
from app.db.models.axis_maturity_content import AxisMaturityContent
from app.db.models.capability import Capability
from app.db.models.capability_maturity_content import CapabilityMaturityContent
from app.db.models.maturity_level import MaturityLevel
from app.db.models.capability_quick_win_template import CapabilityQuickWinTemplate


class CapabilityRepository:
    _MAX_EVIDENCE_TEXT_LEN = 180
    _MAX_RATIONALE_TEXT_LEN = 220

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._capability_columns: set[str] | None = None

    async def _capability_has_column(self, column_name: str) -> bool:
        if self._capability_columns is not None:
            return column_name in self._capability_columns
        try:
            connection = await self.db.connection()
            columns = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_columns("capabilities")
            )
        except Exception:
            return False
        self._capability_columns = {str(col.get("name")) for col in columns}
        return column_name in self._capability_columns

    def _format_evidence_text(self, evidence_text: str | None) -> str | None:
        text = normalize_text(evidence_text)
        if not text:
            return None

        text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
        if not text:
            return None

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        candidate = sentences[0] if sentences else text

        if len(candidate) > self._MAX_EVIDENCE_TEXT_LEN:
            candidate = candidate[: self._MAX_EVIDENCE_TEXT_LEN - 3].rstrip(" ,;:") + "..."

        if candidate and candidate[-1].isalnum():
            candidate += "."
        return candidate

    def _format_rationale_text(self, rationale_text: str | None) -> str | None:
        text = normalize_text(rationale_text)
        if not text:
            return None

        text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
        if not text:
            return None

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if not sentences:
            candidate = text
        elif len(sentences) == 1:
            candidate = sentences[0]
        else:
            candidate = " ".join(sentences[:2])

        if len(candidate) > self._MAX_RATIONALE_TEXT_LEN:
            candidate = candidate[: self._MAX_RATIONALE_TEXT_LEN - 3].rstrip(" ,;:") + "..."

        if candidate and candidate[-1].isalnum():
            candidate += "."
        return candidate

    async def get_axis_progress(self, assessment_id: int) -> dict[str, tuple[int, int]]:
        result = await self.db.execute(
            select(Axis.name, AssessmentScore.assessment_status)
            .join(Capability, Capability.axis_id == Axis.id)
            .join(
                AssessmentScore,
                (AssessmentScore.capability_id == Capability.id)
                & (AssessmentScore.assessment_id == assessment_id),
            )
        )
        rows = result.all()

        totals: dict[str, int] = {}
        covered: dict[str, int] = {}
        for axis_name, assessment_status in rows:
            canonical_axis = normalize_axis_name(str(axis_name)) or str(axis_name)
            totals[canonical_axis] = totals.get(canonical_axis, 0) + 1
            if str(assessment_status or "").strip().lower() == "assessed":
                covered[canonical_axis] = covered.get(canonical_axis, 0) + 1

        return {a: (covered.get(a, 0), totals[a]) for a in totals}

    async def list_for_axis(self, assessment_id: int, axis_name: str) -> list[dict]:
        question_guidelines_col = (
            Capability.question_guidelines
            if await self._capability_has_column("question_guidelines")
            else literal(None)
        )
        if await self._capability_has_column("expected_evidence"):
            expected_evidence_col = literal_column("capabilities.expected_evidence")
        elif await self._capability_has_column("evidence_required"):
            expected_evidence_col = Capability.evidence_required
        else:
            expected_evidence_col = literal(None)
        result = await self.db.execute(
            select(
                Capability.id,
                Capability.code,
                Capability.name,
                Capability.description,
                Capability.sort_order,
                expected_evidence_col,
                question_guidelines_col,
                AssessmentScore.maturity_level_id,
                AssessmentScore.confidence,
                AssessmentScore.assessment_status,
            )
            .join(Axis, Axis.id == Capability.axis_id)
            .join(
                AssessmentScore,
                (AssessmentScore.capability_id == Capability.id)
                & (AssessmentScore.assessment_id == assessment_id),
            )
            .where(func.lower(Axis.name).in_(axis_name_variants(axis_name)))
        )
        rows = result.all()
        return [
            {
                "id": cid,
                "code": str(code),
                "label": label,
                "description": description,
                "sort_order": int(sort_order),
                "expected_evidence": expected_evidence,
                "question_guidelines": question_guidelines,
                "maturity_level_id": int(maturity_level_id) if maturity_level_id is not None else None,
                "covered": str(assessment_status or "").strip().lower() == "assessed",
                "confidence": float(conf or 0),
                "assessment_status": str(assessment_status or "not_assessed"),
            }
            for (
                cid,
                code,
                label,
                description,
                sort_order,
                expected_evidence,
                question_guidelines,
                maturity_level_id,
                conf,
                assessment_status,
            ) in rows
        ]

    async def mark_covered(
        self,
        assessment_id: int,
        covered_ids: list[int],
        confidence: float,
        maturity_level_by_id: dict[int, int] | None = None,
        rationale_by_id: dict[int, str] | None = None,
    ) -> None:
        if not covered_ids:
            return

        maturity_level_by_id = maturity_level_by_id or {}
        rationale_by_id = rationale_by_id or {}

        for capability_id in covered_ids:
            update_values = {
                "assessment_status": "assessed",
                "confidence": confidence,
                "justification": rationale_by_id.get(capability_id),
                "last_assessed_at": func.now(),
            }
            if capability_id in maturity_level_by_id:
                update_values["maturity_level_id"] = maturity_level_by_id[capability_id]
            await self.db.execute(
                update(AssessmentScore)
                .where(
                    AssessmentScore.assessment_id == assessment_id,
                    AssessmentScore.capability_id == capability_id,
                )
                .values(**update_values)
            )

    async def list_all_for_assessment(self, assessment_id: int, axis_name: str | None = None) -> list[dict]:
        statement = (
            select(
                Capability.id,
                Axis.name,
                Axis.sort_order,
                Capability.code,
                Capability.name,
                Capability.sort_order,
                AssessmentScore.maturity_level_id,
                AssessmentScore.confidence,
                AssessmentScore.assessment_status,
                AssessmentScore.justification,
                AssessmentScore.created_at,
            )
            .join(Axis, Axis.id == Capability.axis_id)
            .join(
                AssessmentScore,
                (AssessmentScore.capability_id == Capability.id)
                & (AssessmentScore.assessment_id == assessment_id),
            )
        )
        if axis_name:
            statement = statement.where(func.lower(Axis.name).in_(axis_name_variants(axis_name)))

        result = await self.db.execute(
            statement.order_by(Axis.sort_order.asc(), Capability.sort_order.asc(), Capability.id.asc())
        )
        rows = result.all()
        capability_ids = [int(cid) for (cid, *_rest) in rows]
        latest_insight_by_capability: dict[int, AssessmentInsight] = {}
        if capability_ids:
            insight_result = await self.db.execute(
                select(AssessmentInsight)
                .where(
                    AssessmentInsight.assessment_id == assessment_id,
                    AssessmentInsight.capability_id.in_(capability_ids),
                )
                .order_by(AssessmentInsight.capability_id.asc(), AssessmentInsight.id.desc())
            )
            insight_rows = insight_result.scalars().all()
            for insight in insight_rows:
                if insight.capability_id is None:
                    continue
                capability_id = int(insight.capability_id)
                if capability_id not in latest_insight_by_capability:
                    latest_insight_by_capability[capability_id] = insight

        items = [
            {
                "id": int(cid),
                "axis": normalize_axis_name(str(axis)) or str(axis),
                "code": str(code),
                "label": str(label),
                "maturity_level_id": int(maturity_level_id) if maturity_level_id is not None else None,
                "assessed": str(assessment_status or "").strip().lower() == "assessed",
                "covered": str(assessment_status or "").strip().lower() == "assessed",
                "confidence": float(confidence or 0),
                "assessment_status": str(assessment_status or "not_assessed"),
                "evidence_text": (
                    self._format_evidence_text(latest_insight_by_capability[int(cid)].evidence_text)
                    if int(cid) in latest_insight_by_capability
                    else None
                ),
                "rationale": (
                    self._format_rationale_text(latest_insight_by_capability[int(cid)].justification)
                    if int(cid) in latest_insight_by_capability and latest_insight_by_capability[int(cid)].justification
                    else self._format_rationale_text(justification)
                ),
                "updated_at": (
                    latest_insight_by_capability[int(cid)].created_at
                    if int(cid) in latest_insight_by_capability
                    else updated_at
                ),
                "_axis_sort_order": int(axis_sort_order),
                "_capability_sort_order": int(capability_sort_order),
            }
            for (
                cid,
                axis,
                axis_sort_order,
                code,
                label,
                capability_sort_order,
                maturity_level_id,
                confidence,
                assessment_status,
                justification,
                updated_at,
            ) in rows
        ]

        items.sort(
            key=lambda item: (
                0 if item["covered"] else 1,
                0 if item["assessed"] else 1,
                -float(item["confidence"] or 0.0),
                int(item["_axis_sort_order"]),
                int(item["_capability_sort_order"]),
                int(item["id"]),
            )
        )

        for item in items:
            item.pop("_axis_sort_order", None)
            item.pop("_capability_sort_order", None)
        return items

    async def get_rubrics_for_capabilities(self, capability_ids: list[int]) -> dict[int, list[dict]]:
        if not capability_ids:
            return {}
        result = await self.db.execute(
            select(
                CapabilityMaturityRubric.capability_id,
                CapabilityMaturityRubric.maturity_level_id,
                MaturityLevel.level_number,
                CapabilityMaturityRubric.description,
                CapabilityMaturityRubric.card_summary,
            )
            .join(MaturityLevel, MaturityLevel.id == CapabilityMaturityRubric.maturity_level_id)
            .where(CapabilityMaturityRubric.capability_id.in_(capability_ids))
            .order_by(CapabilityMaturityRubric.capability_id.asc(), CapabilityMaturityRubric.maturity_level_id.asc())
        )
        rows = result.all()
        out: dict[int, list[dict]] = {}
        for capability_id, maturity_level_id, maturity_level_number, description, card_summary in rows:
            out.setdefault(int(capability_id), []).append(
                {
                    "maturity_level_id": int(maturity_level_id),
                    "maturity_level_number": int(maturity_level_number),
                    "description": normalize_text(str(description or "")).strip() or None,
                    "card_summary": normalize_text(str(card_summary or "")).strip() or None,
                }
            )
        return out

    async def get_level3_recommendations_for_capabilities(self, capability_ids: list[int]) -> dict[int, dict]:
        if not capability_ids:
            return {}

        result = await self.db.execute(
            select(
                CapabilityQuickWinTemplate.capability_id,
                CapabilityQuickWinTemplate.quick_win_guideline,
                CapabilityQuickWinTemplate.after_text,
            )
            .join(MaturityLevel, MaturityLevel.id == CapabilityQuickWinTemplate.maturity_level_id)
            .where(
                CapabilityQuickWinTemplate.capability_id.in_(capability_ids),
                MaturityLevel.level_number == 3,
                CapabilityQuickWinTemplate.active.is_(True),
            )
            .order_by(CapabilityQuickWinTemplate.capability_id.asc())
        )
        rows = result.all()
        return {
            int(capability_id): {
                "recommendation_guideline": normalize_text(str(quick_win_guideline or "")).strip() or None,
                "initiative_suggestions": normalize_text(str(after_text or "")).strip() or None,
            }
            for capability_id, quick_win_guideline, after_text in rows
        }

    async def get_axis_maturity_content(self) -> dict[tuple[str, int], dict[str, str | None]]:
        result = await self.db.execute(
            select(
                Axis.code,
                MaturityLevel.level_number,
                AxisMaturityContent.axis_description,
                AxisMaturityContent.axis_panel_copy,
            )
            .join(Axis, Axis.id == AxisMaturityContent.axis_id)
            .join(MaturityLevel, MaturityLevel.id == AxisMaturityContent.maturity_level_id)
            .order_by(Axis.sort_order.asc(), MaturityLevel.level_number.asc())
        )
        rows = result.all()
        return {
            ((normalize_axis_code(str(axis_code)) or str(axis_code)).lower(), int(level_number)): {
                "axis_description": normalize_text(str(axis_description or "")).strip() or None,
                "axis_panel_copy": normalize_text(str(axis_panel_copy or "")).strip() or None,
            }
            for axis_code, level_number, axis_description, axis_panel_copy in rows
        }

    async def get_capability_descriptions(self, capability_ids: list[int]) -> dict[int, str | None]:
        """What each capability is, in the framework's own words, keyed by id."""
        if not capability_ids:
            return {}
        result = await self.db.execute(
            select(Capability.id, Capability.description).where(Capability.id.in_(capability_ids))
        )
        return {
            int(capability_id): clean_optional_text(description)
            for capability_id, description in result.all()
        }

    async def get_capability_maturity_content(self) -> dict[tuple[int, int], dict[str, str | None]]:
        result = await self.db.execute(
            select(
                CapabilityMaturityContent.capability_id,
                MaturityLevel.level_number,
                CapabilityMaturityContent.card_summary,
                CapabilityMaturityContent.modal_summary,
            )
            .join(MaturityLevel, MaturityLevel.id == CapabilityMaturityContent.maturity_level_id)
            .order_by(CapabilityMaturityContent.capability_id.asc(), MaturityLevel.level_number.asc())
        )
        rows = result.all()
        return {
            (int(capability_id), int(level_number)): {
                "card_summary": normalize_text(str(card_summary or "")).strip() or None,
                "modal_summary": normalize_text(str(modal_summary or "")).strip() or None,
            }
            for capability_id, level_number, card_summary, modal_summary in rows
        }

    async def get_quick_win_templates(
        self, capability_ids: list[int]
    ) -> dict[tuple[int, int], dict[str, str | None]]:
        """Admin-authored quick-win copy, keyed by (capability, maturity level).

        A quick win is only ever offered where an admin wrote one for the exact level a capability
        landed on -- that is what keeps the report proposing actions the firm stands behind rather
        than inventing them. Templates switched off are excluded here rather than downstream.
        """
        if not capability_ids:
            return {}
        result = await self.db.execute(
            select(
                CapabilityQuickWinTemplate.capability_id,
                CapabilityQuickWinTemplate.maturity_level_id,
                CapabilityQuickWinTemplate.quick_win_guideline,
                CapabilityQuickWinTemplate.after_text,
                CapabilityQuickWinTemplate.owner_hint,
                CapabilityQuickWinTemplate.timeline_hint,
            ).where(
                CapabilityQuickWinTemplate.active.is_(True),
                CapabilityQuickWinTemplate.capability_id.in_(capability_ids),
            )
        )
        return {
            (int(capability_id), int(maturity_level_id)): {
                "quick_win_guideline": normalize_text(str(quick_win_guideline or "")).strip() or None,
                "after_text": normalize_text(str(after_text or "")).strip() or None,
                "owner_hint": normalize_text(str(owner_hint or "")).strip() or None,
                "timeline_hint": normalize_text(str(timeline_hint or "")).strip() or None,
            }
            for capability_id, maturity_level_id, quick_win_guideline, after_text, owner_hint, timeline_hint in result.all()
            if capability_id is not None and maturity_level_id is not None
        }

    async def get_recommendations_for_scores(self, assessment_id: int) -> list[dict]:
        latest_insight_subquery = (
            select(
                AssessmentInsight.capability_id.label("capability_id"),
                func.max(AssessmentInsight.id).label("latest_insight_id"),
            )
            .where(AssessmentInsight.assessment_id == assessment_id)
            .group_by(AssessmentInsight.capability_id)
            .subquery()
        )
        latest_insight = AssessmentInsight.__table__.alias("latest_insight")
        result = await self._execute_recommendations_query(
            assessment_id=assessment_id,
            latest_insight_subquery=latest_insight_subquery,
            latest_insight=latest_insight,
        )
        rows = result.all()
        return [
            {
                "capability_id": int(capability_id),
                "capability_code": str(capability_code),
                "capability_name": str(capability_name),
                "axis": normalize_axis_code(str(axis_name)) or str(axis_name),
                  "maturity_level_id": int(maturity_level_id) if maturity_level_id is not None else None,
                  "confidence": float(confidence) if confidence is not None else None,
                  "assessment_status": str(assessment_status or "not_assessed"),
                  "justification": justification,
                  "evidence_text": evidence_text,
                  "insight_justification": insight_justification,
                "recommendation_guideline": quick_win_guideline,
                "priority_hint": timeline_hint,
                "consultant_note": (
                    f"Suggested owner: {normalize_text(str(owner_hint)).strip()}"
                    if normalize_text(str(owner_hint or "")).strip()
                    else None
                ),
                "evidence_to_cite": evidence_text,
                "initiative_suggestions": quick_win_guideline,
                "business_impact": after_text,
                "tone_hint": "balanced",
            }
            for (
                capability_id,
                capability_code,
                capability_name,
                axis_name,
                maturity_level_id,
                  confidence,
                  assessment_status,
                  justification,
                  evidence_text,
                  insight_justification,
                  quick_win_guideline,
                after_text,
                owner_hint,
                timeline_hint,
            ) in rows
        ]

    async def _execute_recommendations_query(
        self,
        *,
        assessment_id: int,
        latest_insight_subquery,
        latest_insight,
    ):
        statement = (
            select(
                Capability.id,
                Capability.code,
                Capability.name,
                Axis.name,
                AssessmentScore.maturity_level_id,
                AssessmentScore.confidence,
                AssessmentScore.assessment_status,
                AssessmentScore.justification,
                latest_insight.c.evidence_text,
                latest_insight.c.justification,
                CapabilityQuickWinTemplate.quick_win_guideline,
                CapabilityQuickWinTemplate.after_text,
                CapabilityQuickWinTemplate.owner_hint,
                CapabilityQuickWinTemplate.timeline_hint,
            )
            .join(Axis, Axis.id == Capability.axis_id)
            .join(
                AssessmentScore,
                (AssessmentScore.capability_id == Capability.id)
                & (AssessmentScore.assessment_id == assessment_id),
            )
            .outerjoin(
                latest_insight_subquery,
                latest_insight_subquery.c.capability_id == Capability.id,
            )
            .outerjoin(
                latest_insight,
                latest_insight.c.id == latest_insight_subquery.c.latest_insight_id,
            )
            .outerjoin(
                CapabilityQuickWinTemplate,
                (CapabilityQuickWinTemplate.capability_id == Capability.id)
                & (CapabilityQuickWinTemplate.maturity_level_id == AssessmentScore.maturity_level_id)
                & (CapabilityQuickWinTemplate.active.is_(True)),
            )
        )
        statement = statement.order_by(Axis.sort_order.asc(), Capability.sort_order.asc(), Capability.id.asc())
        return await self.db.execute(statement)
