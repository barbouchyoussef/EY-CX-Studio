"""Aggregate statistics across every assessment, for the admin dashboard.

The rest of the platform reports on one assessment at a time. This reports on the portfolio: how
many were run, how they score by axis and capability, which weaknesses recur across clients, and
how any of that moves over time.

Every method takes the same window and filter set (dates, sector, company size, status) and
applies it through one helper, so two charts on the dashboard can never end up answering slightly
different questions. Reads only -- nothing here writes.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.scoring import MaturityScoring
from app.domain.constants import axis_name_variants, normalize_axis_code
from app.db.models.assessment import Assessment
from app.db.models.assessment_score import AssessmentScore
from app.db.models.axis import Axis
from app.db.models.capability import Capability
from app.db.models.company import Company
from app.db.models.company_size import CompanySize
from app.db.models.maturity_level import MaturityLevel
from app.db.models.recommendation_output import RecommendationOutput
from app.db.models.sector import Sector
from app.schemas.admin_analytics import (
    AnalyticsFilterSet,
    AnalyticsOverviewCounts,
    AnalyticsOverviewResponse,
    AnalyticsWindow,
    MaturityByCapabilityItem,
    MaturityByCapabilityResponse,
    RecommendationThemeItem,
    RecommendationThemesResponse,
    SectorTrendItem,
    SectorTrendsResponse,
    TopSignalItem,
    TopSignalsResponse,
)


class AdminAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def overview(
        self,
        from_date: date,
        to_date: date,
        sector_code: str | None,
        company_size_code: str | None,
        status: str | None,
    ) -> AnalyticsOverviewResponse:
        """Headline counts plus the average score per axis, for the dashboard's top row.

        Two independent queries over the same window: one counting assessments by status, one
        averaging maturity levels per axis. They stay separate because an assessment counts
        towards the totals as soon as it exists, but only contributes a score once its
        capabilities have actually been scored.
        """
        assessments_q = self.db.query(Assessment.id, Assessment.status).join(Company, Company.id == Assessment.company_id)
        assessments_q = self._apply_assessment_filters(
            query=assessments_q,
            from_date=from_date,
            to_date=to_date,
            status=status,
            sector_code=sector_code,
            company_size_code=company_size_code,
        )
        rows = assessments_q.all()
        total = len(rows)
        completed = sum(1 for r in rows if (r.status or "").lower() == "completed")
        active = sum(1 for r in rows if (r.status or "").lower() == "active")

        levels = self._level_map()
        by_label = {"Basic": 0, "Established": 0, "Advanced": 0}
        level_rows = (
            self.db.query(MaturityLevel.label, func.count(Assessment.id))
            .select_from(Assessment)
            .join(Company, Company.id == Assessment.company_id)
            .join(MaturityLevel, MaturityLevel.id == Assessment.overall_maturity_level_id, isouter=True)
        )
        level_rows = self._apply_assessment_filters(
            query=level_rows,
            from_date=from_date,
            to_date=to_date,
            status=status,
            sector_code=sector_code,
            company_size_code=company_size_code,
        ).group_by(MaturityLevel.label).all()
        for label, count in level_rows:
            if label in by_label:
                by_label[label] = int(count)

        axis_rows = (
            self.db.query(
                Axis.code,
                func.avg(MaturityLevel.level_number),
            )
            .select_from(AssessmentScore)
            .join(Assessment, Assessment.id == AssessmentScore.assessment_id)
            .join(Company, Company.id == Assessment.company_id)
            .join(Capability, Capability.id == AssessmentScore.capability_id)
            .join(Axis, Axis.id == Capability.axis_id)
            .join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id)
        )
        axis_rows = self._apply_assessment_filters(
            query=axis_rows,
            from_date=from_date,
            to_date=to_date,
            status=status,
            sector_code=sector_code,
            company_size_code=company_size_code,
        ).group_by(Axis.code).all()
        axis_avg: dict[str, float] = {}
        for axis_code, avg_level in axis_rows:
            score_pct = MaturityScoring.score_percent_from_level_average(float(avg_level or 0.0))
            axis_avg[normalize_axis_code(str(axis_code)) or str(axis_code).upper()] = round(score_pct, 2)

        return AnalyticsOverviewResponse(
            window=AnalyticsWindow(from_date=from_date, to_date=to_date),
            filters=AnalyticsFilterSet(sector_code=sector_code, company_size_code=company_size_code, status=status),
            counts=AnalyticsOverviewCounts(assessments=total, completed=completed, active=active),
            maturity_distribution=by_label,
            axis_avg_score_percent=axis_avg,
        )

    def maturity_by_capability(
        self,
        from_date: date,
        to_date: date,
        sector_code: str | None,
        company_size_code: str | None,
        axis: str | None,
    ) -> MaturityByCapabilityResponse:
        """Average maturity per capability, so the weakest ones stand out across all clients.

        This is the view that answers "what does the market struggle with", rather than what one
        client struggles with.
        """
        level_map = self._level_map()
        q = (
            self.db.query(
                Capability.code,
                Capability.name,
                Axis.code,
                func.count(AssessmentScore.id),
                func.sum(case((MaturityLevel.level_number == level_map["basic"], 1), else_=0)),
                func.sum(case((MaturityLevel.level_number == level_map["established"], 1), else_=0)),
                func.sum(case((MaturityLevel.level_number == level_map["advanced"], 1), else_=0)),
                func.avg(AssessmentScore.confidence),
            )
            .select_from(AssessmentScore)
            .join(Assessment, Assessment.id == AssessmentScore.assessment_id)
            .join(Company, Company.id == Assessment.company_id)
            .join(Capability, Capability.id == AssessmentScore.capability_id)
            .join(Axis, Axis.id == Capability.axis_id)
            .join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id)
        )
        q = self._apply_assessment_filters(
            query=q,
            from_date=from_date,
            to_date=to_date,
            status="completed",
            sector_code=sector_code,
            company_size_code=company_size_code,
        )
        if axis:
            q = q.filter(func.lower(Axis.code).in_(axis_name_variants(axis)))
        rows = q.group_by(Capability.code, Capability.name, Axis.code).order_by(Axis.sort_order.asc(), Capability.sort_order.asc()).all()
        items = [
            MaturityByCapabilityItem(
                capability_code=str(code),
                capability_name=str(name),
                axis=normalize_axis_code(str(axis_code)) or str(axis_code).upper(),
                n=int(n or 0),
                basic=int(basic or 0),
                established=int(established or 0),
                advanced=int(advanced or 0),
                avg_confidence=round(float(avg_conf), 3) if avg_conf is not None else None,
            )
            for code, name, axis_code, n, basic, established, advanced, avg_conf in rows
        ]
        return MaturityByCapabilityResponse(items=items)

    def top_signals(
        self,
        from_date: date,
        to_date: date,
        sector_code: str | None,
        company_size_code: str | None,
        limit: int,
        signal: str,
    ) -> TopSignalsResponse:
        """The capabilities that most often come back weakest, or strongest.

        `signal` picks which end to look at: "pain" counts how often a capability landed on the
        lowest maturity level, anything else counts the highest. Both are reported as a share of
        all scores at that level, so a capability assessed twice as often does not look twice as
        painful.
        """
        level_map = self._level_map()
        level_number = level_map["basic"] if signal == "pain" else level_map["advanced"]
        total_signal_q = (
            self.db.query(func.count(AssessmentScore.id))
            .select_from(AssessmentScore)
            .join(Assessment, Assessment.id == AssessmentScore.assessment_id)
            .join(Company, Company.id == Assessment.company_id)
        )
        total_signal_count = self._apply_assessment_filters(
            query=total_signal_q,
            from_date=from_date,
            to_date=to_date,
            status="completed",
            sector_code=sector_code,
            company_size_code=company_size_code,
        ).join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id).filter(
            MaturityLevel.level_number == level_number
        ).scalar() or 0

        rows = (
            self.db.query(
                Capability.code,
                Capability.name,
                Axis.code,
                func.count(AssessmentScore.id),
            )
            .select_from(AssessmentScore)
            .join(Assessment, Assessment.id == AssessmentScore.assessment_id)
            .join(Company, Company.id == Assessment.company_id)
            .join(Capability, Capability.id == AssessmentScore.capability_id)
            .join(Axis, Axis.id == Capability.axis_id)
            .join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id)
        )
        rows = self._apply_assessment_filters(
            query=rows,
            from_date=from_date,
            to_date=to_date,
            status="completed",
            sector_code=sector_code,
            company_size_code=company_size_code,
        ).filter(MaturityLevel.level_number == level_number).group_by(Capability.code, Capability.name, Axis.code).order_by(func.count(AssessmentScore.id).desc()).limit(limit).all()
        items: list[TopSignalItem] = []
        denom = max(int(total_signal_count), 1)
        for code, name, axis_code, cnt in rows:
            count_value = int(cnt or 0)
            items.append(
                TopSignalItem(
                    capability_code=str(code),
                    capability_name=str(name),
                    axis=normalize_axis_code(str(axis_code)) or str(axis_code).upper(),
                    count=count_value,
                    share_percent=round((count_value / denom) * 100.0, 2),
                )
            )
        return TopSignalsResponse(items=items)

    def recommendation_themes(
        self,
        from_date: date,
        to_date: date,
        sector_code: str | None,
        company_size_code: str | None,
        axis: str | None,
        limit: int,
    ) -> RecommendationThemesResponse:
        """What the platform has been recommending, grouped by priority and axis.

        Counts the recommendations actually written into reports, so it reflects what clients were
        told rather than what their scores implied.
        """
        q = (
            self.db.query(
                RecommendationOutput.priority,
                func.count(RecommendationOutput.id),
            )
            .select_from(RecommendationOutput)
            .join(Assessment, Assessment.id == RecommendationOutput.assessment_id)
            .join(Company, Company.id == Assessment.company_id)
            .join(Capability, Capability.id == RecommendationOutput.capability_id, isouter=True)
            .join(Axis, Axis.id == Capability.axis_id, isouter=True)
        )
        q = self._apply_assessment_filters(
            query=q,
            from_date=from_date,
            to_date=to_date,
            status="completed",
            sector_code=sector_code,
            company_size_code=company_size_code,
        )
        if axis:
            q = q.filter(func.lower(Axis.code).in_(axis_name_variants(axis)))
        rows = (
            q.group_by(RecommendationOutput.priority)
            .order_by(func.count(RecommendationOutput.id).desc())
            .limit(limit)
            .all()
        )
        items = [
            RecommendationThemeItem(theme=str(theme or "unclassified"), count=int(cnt or 0))
            for theme, cnt in rows
        ]
        return RecommendationThemesResponse(items=items)

    def sector_trends(
        self,
        from_date: date,
        to_date: date,
        sector_code: str,
        group_by: str,
    ) -> SectorTrendsResponse:
        """How a sector's maturity has moved over time, by month or by quarter.

        Completed assessments only: one still in progress has partial scores, and including it
        would drag a period's average down for a reason that has nothing to do with the sector.
        """
        period_expr = func.date_trunc("month" if group_by == "month" else "quarter", Assessment.created_at)

        rows = (
            self.db.query(
                period_expr.label("period_start"),
                func.count(func.distinct(Assessment.id)).label("assessments"),
                func.avg(MaturityLevel.level_number).label("avg_level"),
                func.sum(case((MaturityLevel.level_number == 1, 1), else_=0)).label("basic"),
                func.sum(case((MaturityLevel.level_number == 2, 1), else_=0)).label("established"),
                func.sum(case((MaturityLevel.level_number == 3, 1), else_=0)).label("advanced"),
            )
            .select_from(Assessment)
            .join(Company, Company.id == Assessment.company_id)
            .join(AssessmentScore, AssessmentScore.assessment_id == Assessment.id)
            .join(MaturityLevel, MaturityLevel.id == AssessmentScore.maturity_level_id)
        )
        rows = self._apply_assessment_filters(
            query=rows,
            from_date=from_date,
            to_date=to_date,
            status="completed",
            sector_code=sector_code,
            company_size_code=None,
        ).group_by(period_expr).order_by(period_expr.asc()).all()

        series: list[SectorTrendItem] = []
        for period_start, assessments, avg_level, basic, established, advanced in rows:
            period_dt = period_start if isinstance(period_start, datetime) else datetime.combine(from_date, time.min)
            if group_by == "quarter":
                quarter = ((period_dt.month - 1) // 3) + 1
                period_label = f"{period_dt.year}-Q{quarter}"
            else:
                period_label = period_dt.strftime("%Y-%m")
            series.append(
                SectorTrendItem(
                    period=period_label,
                    assessments=int(assessments or 0),
                    overall_avg_score=round(
                        MaturityScoring.score_percent_from_level_average(float(avg_level or 0.0)), 2
                    ),
                    basic=int(basic or 0),
                    established=int(established or 0),
                    advanced=int(advanced or 0),
                )
            )
        return SectorTrendsResponse(sector_code=sector_code, series=series)

    def _apply_assessment_filters(
        self,
        query,
        from_date: date,
        to_date: date,
        status: str | None,
        sector_code: str | None,
        company_size_code: str | None,
    ):
        """Apply the dashboard's window and filters to any query that reaches Assessment.

        Every public method goes through this. It is what guarantees two charts on one screen
        describe the same population: the filters cannot drift apart when there is only one place
        they are written.
        """
        query = query.filter(
            Assessment.created_at >= datetime.combine(from_date, time.min),
            Assessment.created_at <= datetime.combine(to_date, time.max),
        )
        if status:
            query = query.filter(func.lower(Assessment.status) == status.lower())
        if sector_code:
            query = query.join(Sector, Sector.id == Company.sector_id).filter(func.lower(Sector.code) == sector_code.lower())
        if company_size_code:
            query = query.join(CompanySize, CompanySize.id == Company.size_id).filter(
                func.lower(CompanySize.code) == company_size_code.lower()
            )
        return query

    def _level_map(self) -> dict[str, int]:
        """Maturity level numbers keyed by name, read from the database rather than assumed.

        The levels are reference data, so their numbering belongs to the schema and not to this
        file -- a fourth level would be picked up here without a code change.
        """
        rows = self.db.query(MaturityLevel.level_number, MaturityLevel.label).all()
        mapping = {str(label).strip().lower(): int(level_number) for level_number, label in rows}
        return {
            "basic": mapping.get("basic", 1),
            "established": mapping.get("established", 2),
            "advanced": mapping.get("advanced", 3),
        }
