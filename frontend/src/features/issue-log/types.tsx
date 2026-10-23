/**
 * What an issue log is made of, and the small pieces every screen in this module needs.
 *
 * The consolidation runs on the backend; this side only renders what it produced. So these types
 * describe a payload, not a domain model, and the lookup tables are pure presentation -- which
 * chip colour a severity gets, which icon a source kind shows.
 */

import type { JSX } from "react";
import { ClipboardList, FileText, MessageSquare, Radio } from "lucide-react";
import { authFetch } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import type { AnalysisKind } from "../../lib/projectsApi";

export type Input = { kind: AnalysisKind; ref_id: string; title: string };

export type Severity = "critical" | "high" | "medium" | "low";

/** One row of the issue log — mirrors what /issue-log/generate returns. */
export type Issue = {
  issue_no: string;
  finding: string;
  investigation: string;
  evidence: string | null;
  evidence_status: "exact" | "partial" | "absent" | "missing" | "too_short";
  reports: number;
  severity: Severity;
  severity_reason: string | null;
  strategic_dimension: string;
  sub_category: string | null;
  channel: string | null;
  inspection_point: string;
  client: string | null;
  source_kind: string | null;
  /* Added by the cross-source pass. Generation reads each source alone, so these are the
     only signals that several sources agree, or that two of them contradict each other. */
  corroboration_count?: number;
  corroborated_by?: string[];
  corroborates?: string | null;
  has_conflict?: boolean;
  conflicts_with?: string[];
  edited?: boolean;
  comment?: string | null;
};

export type Conflict = {
  ref: string;
  issue_a: string; issue_b: string;
  source_a: string; source_b: string;
  a_claims: string; b_claims: string;
  why_it_matters: string | null;
};

export type Recommendation = {
  ref: string;
  client: string;
  action: string;
  rationale: string | null;
  addresses: string[];
  issues_addressed: number;
  effort: "quick win" | "medium" | "major programme";
  impact: "high" | "medium" | "low";
};

export type SourceStat = {
  kind: string; ref_id: string; status: string;
  client?: string; chunks: number; tokens?: number;
};

export type RunRecord = {
  raw_issues: number; calls: number; tokens_in: number; tokens_out: number;
  dropped_no_finding: number; dropped_off_taxonomy: number; dropped_duplicate: number;
  evidence_exact: number; evidence_partial: number; evidence_absent: number;
  fabricated_numbers: number; warnings: string[];
};

export type GenerateResult = {
  issues: Issue[];
  recommendations: Recommendation[];
  conflicts: Conflict[];
  sources: SourceStat[];
  run: RunRecord;
};

export type Preview = {
  chunks: number; tokens: number;
  clients: Record<string, number>;
  sources: SourceStat[];
};

export type JobStatus = "pending" | "running" | "completed" | "failed";

export type SavedItem = {
  id: number; name: string; project_id: number | null;
  status: JobStatus; progress: string | null; error: string | null;
  findings_count: number; recommendations_count: number; created_at: string;
  /** False when the log is visible only because someone shared it. */
  owned?: boolean;
};

/* ─────────────────────────── constants ─────────────────────────── */

export const KIND_META: Record<string, { label: string; icon: JSX.Element; tint: string }> = {
  assessment: { label: "Assessment", icon: <ClipboardList className="h-3.5 w-3.5" />, tint: "bg-indigo-50 text-indigo-500" },
  interview_guide: { label: "Interview", icon: <MessageSquare className="h-3.5 w-3.5" />, tint: "bg-amber-50 text-amber-600" },
  social_report: { label: "Social", icon: <Radio className="h-3.5 w-3.5" />, tint: "bg-emerald-50 text-emerald-600" },
  desk_session: { label: "Desk research", icon: <FileText className="h-3.5 w-3.5" />, tint: "bg-sky-50 text-sky-600" },
};

export const SEV_CHIP: Record<Severity, string> = {
  critical: "bg-rose-100 text-rose-700 ring-rose-200",
  high: "bg-orange-100 text-orange-700 ring-orange-200",
  medium: "bg-amber-100 text-amber-700 ring-amber-200",
  low: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};
export const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export const STATUS_CHIP: Record<JobStatus, string> = {
  pending: "bg-slate-100 text-slate-600",
  running: "bg-sky-100 text-sky-700",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
};

export const EFFORT_CHIP: Record<string, string> = {
  "quick win": "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  "major programme": "bg-slate-100 text-slate-600",
};

/* ─────────────────────────── helpers ─────────────────────────── */

export async function fetchList<T>(path: string): Promise<T[]> {
  try {
    const r = await authFetch(path);
    if (!r.ok) return [];
    const d = await r.json();
    return Array.isArray(d) ? d : (d.items ?? d.sessions ?? []);
  } catch { return []; }
}

/** Only the fields this picker reads from each artifact endpoint. Deliberately partial: the
 *  responses carry far more, and narrowing to what is used keeps the picker from breaking when
 *  something unrelated in those payloads changes. */
type AssessmentRow = { id: number | string; company_name?: string | null };
type InterviewGuideRow = { id: number | string; company_name?: string | null; profile?: string | null };
type SocialReportRow = { filename: string; brand_name?: string | null };
type DeskSessionRow = { session_id: string; title?: string | null };

export async function loadAllArtifacts(): Promise<Input[]> {
  // Four unrelated endpoints, so they go out together. Awaiting them in turn made opening the
  // picker take as long as the slowest four combined, for no reason -- none depends on another.
  const [assessments, guides, reports, sessions] = await Promise.all([
    fetchList<AssessmentRow>("/assessments?limit=100"),
    fetchList<InterviewGuideRow>("/assessments/interview-guide/list"),
    fetchList<SocialReportRow>("/scraping/reports"),
    fetchList<DeskSessionRow>("/desk-research/sessions"),
  ]);
  return [
    ...assessments.map((a) => ({
      kind: "assessment" as const, ref_id: String(a.id),
      title: a.company_name || `Assessment ${a.id}`,
    })),
    ...guides.map((g) => ({
      kind: "interview_guide" as const, ref_id: String(g.id),
      title: `${g.company_name}${g.profile ? " — " + g.profile : ""}`,
    })),
    ...reports.map((r) => ({
      kind: "social_report" as const, ref_id: r.filename, title: r.brand_name || r.filename,
    })),
    ...sessions.map((s) => ({
      kind: "desk_session" as const, ref_id: s.session_id, title: s.title || s.session_id,
    })),
  ];
}

export function fmtDate(iso: string): string {
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return iso; }
}

/** Download the workbook. The endpoint streams bytes, so this goes through fetch + blob
 *  rather than a plain link — a bare <a href> would not carry the bearer token. */
export async function downloadWorkbook(id: number, name: string, onError: (m: string) => void) {
  try {
    const res = await authFetch(`/issue-log/${id}/export.xlsx`);
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(name || "issue-log").replace(/[^\w -]/g, "")}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    onError(errorMessage(e, "Export failed"));
  }
}

/* ─────────────────────────── one issue row ─────────────────────────── */

