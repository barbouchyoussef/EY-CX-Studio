from pydantic import BaseModel


class FinalReportHero(BaseModel):
    report_title: str
    report_date_label: str | None = None
    company_name: str | None = None
    sector_name: str | None = None
    region: str | None = None
    overall_level: int | None = None
    overall_level_label: str | None = None
    overall_maturity_band: str
    hero_message: str | None = None
    strongest_axis: str | None = None
    strongest_axis_level: int | None = None
    strongest_axis_level_label: str | None = None
    strongest_axis_description: str | None = None
    priority_axis: str | None = None
    priority_axis_level: int | None = None
    priority_axis_level_label: str | None = None
    priority_axis_description: str | None = None


class FinalReportSummary(BaseModel):
    overall_score_percent: float
    overall_maturity_band: str
    strongest_axis: str
    strongest_axis_score_percent: float
    priority_axis: str
    priority_axis_score_percent: float
    strengths_count: int
    pain_points_count: int
    assessed_capabilities_count: int = 0
    unassessed_capabilities_count: int = 0
    executive_summary_text: str | None = None
    priority_message_text: str | None = None


class FinalReportAxisItem(BaseModel):
    axis: str
    score_percent: float
    maturity_band: str
    axis_level: int | None = None
    axis_level_label: str | None = None


class FinalReportThemeItem(BaseModel):
    axis: str
    capability: str
    maturity_band: str
    rationale: str | None = None
    recommendation: str | None = None
    priority: str | None = None


class FinalReportCapabilityItem(BaseModel):
    capability_id: int | None = None
    maturity_level_number: int | None = None
    axis: str
    capability: str
    maturity_band: str
    assessment_status: str = "not_assessed"
    confidence: float | None = None
    rationale: str | None = None
    recommendation: str | None = None
    priority: str | None = None


class FinalReportBenchmarkItem(BaseModel):
    title: str
    url: str
    site_name: str | None = None
    published_at: str | None = None
    summary: str | None = None
    method_signal: str | None = None
    context_match: str | None = None


class FinalReportCompetitiveEvidenceLink(BaseModel):
    label: str
    url: str
    source_title: str | None = None


class FinalReportCompetitiveCompetitor(BaseModel):
    key: str
    company_name: str
    note: str | None = None
    stage_level: int
    stage_label: str
    logo_url: str | None = None
    is_you: bool = False
    evidence_links: list[FinalReportCompetitiveEvidenceLink] = []


class FinalReportCompetitiveStage(BaseModel):
    level: int
    label: str
    summary: str
    competitors: list[FinalReportCompetitiveCompetitor] = []


class FinalReportLeaderEvidenceLink(BaseModel):
    label: str
    url: str
    source_title: str | None = None
    mapped_capability: str | None = None
    why_relevant: str | None = None


class FinalReportLeadersSnapshotMetrics(BaseModel):
    candidates_considered: int = 0
    candidates_evaluated: int = 0
    web_search_calls: int = 0
    rerank_calls: int = 0
    mistral_calls: int = 0
    documents_retrieved: int = 0
    documents_validated: int = 0
    documents_rejected_indirect: int = 0
    capability_coverage_count: int = 0


class FinalReportLeaderItem(BaseModel):
    key: str
    company_name: str
    note: str | None = None
    leader_summary: str | None = None
    logo_url: str | None = None
    evidence_links: list[FinalReportLeaderEvidenceLink] = []


class FinalReportLeadersSnapshot(BaseModel):
    supported: bool
    status: str = "unavailable"
    sector: str
    respondent_company_name: str
    message: str | None = None
    metrics: FinalReportLeadersSnapshotMetrics | None = None
    leaders: list[FinalReportLeaderItem] = []


class FinalReportWorkingMissingItem(BaseModel):
    capability: str
    maturity_band: str
    summary: str | None = None
    evidence_snippet: str | None = None


class FinalReportWorkingMissingAxis(BaseModel):
    axis: str
    label: str
    score_percent: float
    maturity_band: str
    axis_level: int | None = None
    axis_level_label: str | None = None
    subtitle: str | None = None
    intro: str | None = None
    stat_note: str | None = None
    working: list[FinalReportWorkingMissingItem] = []
    missing: list[FinalReportWorkingMissingItem] = []


class FinalReportQuickWinItem(BaseModel):
    step: int
    timeline_label: str
    title: str
    owner: str
    today_text: str
    after_text: str


class FinalReportQuickWinsTimeline(BaseModel):
    section_title: str = "Your Quick Wins, In Order"
    language: str | None = None
    items: list[FinalReportQuickWinItem] = []


class FinalReportResponse(BaseModel):
    assessment_id: int
    hero: FinalReportHero
    summary: FinalReportSummary
    axes: list[FinalReportAxisItem]
    strengths: list[FinalReportThemeItem]
    pain_points: list[FinalReportThemeItem]
    capabilities: list[FinalReportCapabilityItem]
    benchmarks: list[FinalReportBenchmarkItem]
    competitive_landscape: list[FinalReportCompetitiveStage] = []
    leaders_snapshot: FinalReportLeadersSnapshot | None = None
    quick_wins_timeline: FinalReportQuickWinsTimeline | None = None
    working_missing: list[FinalReportWorkingMissingAxis] = []
