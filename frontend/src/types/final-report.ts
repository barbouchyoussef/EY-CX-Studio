export type FinalReportHero = {
  report_title: string;
  report_date_label?: string | null;
  company_name?: string | null;
  sector_name?: string | null;
  region?: string | null;
  overall_level?: number | null;
  overall_level_label?: string | null;
  overall_maturity_band: string;
  hero_message?: string | null;
  strongest_axis?: string | null;
  strongest_axis_level?: number | null;
  strongest_axis_level_label?: string | null;
  strongest_axis_description?: string | null;
  priority_axis?: string | null;
  priority_axis_level?: number | null;
  priority_axis_level_label?: string | null;
  priority_axis_description?: string | null;
};

export type FinalReportSummary = {
  overall_score_percent: number;
  overall_maturity_band: string;
  strongest_axis: string;
  strongest_axis_score_percent: number;
  priority_axis: string;
  priority_axis_score_percent: number;
  strengths_count: number;
  pain_points_count: number;
  assessed_capabilities_count?: number;
  unassessed_capabilities_count?: number;
  executive_summary_text?: string | null;
  priority_message_text?: string | null;
};

export type FinalReportAxisItem = {
  axis: string;
  score_percent: number;
  maturity_band: string;
  axis_level?: number | null;
  axis_level_label?: string | null;
};

export type FinalReportThemeItem = {
  axis: string;
  capability: string;
  maturity_band: string;
  rationale?: string | null;
  recommendation?: string | null;
  priority?: string | null;
};

export type FinalReportCapabilityItem = {
  capability_id?: number | null;
  maturity_level_number?: number | null;
  axis: string;
  capability: string;
  maturity_band: string;
  assessment_status?: string;
  confidence?: number | null;
  rationale?: string | null;
  recommendation?: string | null;
  priority?: string | null;
};

export type FinalReportBenchmarkItem = {
  title: string;
  url: string;
  site_name?: string | null;
  published_at?: string | null;
  summary?: string | null;
  method_signal?: string | null;
  context_match?: string | null;
};

export type FinalReportCompetitiveEvidenceLink = {
  label: string;
  url: string;
  source_title?: string | null;
};

export type FinalReportCompetitiveCompetitor = {
  key: string;
  company_name: string;
  note?: string | null;
  stage_level: number;
  stage_label: string;
  logo_url?: string | null;
  is_you?: boolean;
  evidence_links: FinalReportCompetitiveEvidenceLink[];
};

export type FinalReportCompetitiveStage = {
  level: number;
  label: string;
  summary: string;
  competitors: FinalReportCompetitiveCompetitor[];
};

export type FinalReportLeaderEvidenceLink = {
  label: string;
  url: string;
  source_title?: string | null;
  mapped_capability?: string | null;
  why_relevant?: string | null;
};

export type FinalReportLeadersSnapshotMetrics = {
  candidates_considered: number;
  candidates_evaluated: number;
  web_search_calls: number;
  rerank_calls: number;
  mistral_calls: number;
  documents_retrieved: number;
  documents_validated: number;
  documents_rejected_indirect: number;
  capability_coverage_count: number;
};

export type FinalReportLeaderItem = {
  key: string;
  company_name: string;
  note?: string | null;
  leader_summary?: string | null;
  logo_url?: string | null;
  evidence_links: FinalReportLeaderEvidenceLink[];
};

export type FinalReportLeadersSnapshot = {
  supported: boolean;
  status: string;
  sector: string;
  respondent_company_name: string;
  message?: string | null;
  metrics?: FinalReportLeadersSnapshotMetrics | null;
  leaders: FinalReportLeaderItem[];
};

export type FinalReportWorkingMissingItem = {
  capability: string;
  maturity_band: string;
  summary?: string | null;
  evidence_snippet?: string | null;
};

export type FinalReportWorkingMissingAxis = {
  axis: string;
  label: string;
  score_percent: number;
  maturity_band: string;
  axis_level?: number | null;
  axis_level_label?: string | null;
  subtitle?: string | null;
  intro?: string | null;
  stat_note?: string | null;
  working: FinalReportWorkingMissingItem[];
  missing: FinalReportWorkingMissingItem[];
};

export type FinalReportQuickWinItem = {
  step: number;
  timeline_label: string;
  title: string;
  owner: string;
  today_text: string;
  after_text: string;
};

export type FinalReportQuickWinsTimeline = {
  section_title: string;
  language?: string | null;
  items: FinalReportQuickWinItem[];
};

export type FinalReport = {
  assessment_id: number;
  hero: FinalReportHero;
  summary: FinalReportSummary;
  axes: FinalReportAxisItem[];
  strengths: FinalReportThemeItem[];
  pain_points: FinalReportThemeItem[];
  capabilities: FinalReportCapabilityItem[];
  benchmarks: FinalReportBenchmarkItem[];
  competitive_landscape: FinalReportCompetitiveStage[];
  leaders_snapshot?: FinalReportLeadersSnapshot | null;
  quick_wins_timeline?: FinalReportQuickWinsTimeline | null;
  working_missing: FinalReportWorkingMissingAxis[];
};
