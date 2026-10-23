/**
 * A finished issue log: its findings, the conflicts between sources, and what to do about them.
 *
 * Three tabs over one payload rather than three fetches -- the run produces all of it at once,
 * and a consultant moves between them constantly while reading.
 */

import { useMemo } from "react";
import { useState } from "react";
import { AlertTriangle, GitCompareArrows, Lightbulb } from "lucide-react";
import IssueCard from "./issue-card";
import { KIND_META, SEV_CHIP, SEV_ORDER, EFFORT_CHIP, type Severity, type Issue, type Conflict, type Recommendation, type SourceStat, type RunRecord } from "./types";

export default function ResultView({
  issues, recommendations, conflicts = [], sources, run, logId, onIssuesChanged, onError,
}: {
  issues: Issue[]; recommendations: Recommendation[]; conflicts?: Conflict[];
  sources?: SourceStat[]; run?: RunRecord | null;
  logId?: number;
  onIssuesChanged?: () => void;
  onError?: (message: string) => void;
}) {
  const [tab, setTab] = useState<"issues" | "conflicts" | "recs">("issues");
  const [sevFilter, setSevFilter] = useState<Severity | "all">("all");
  const [dimFilter, setDimFilter] = useState<string>("all");

  const dimensions = useMemo(
    () => Array.from(new Set(issues.map((i) => i.strategic_dimension))).sort(),
    [issues],
  );

  const visible = useMemo(
    () => issues.filter((i) =>
      (sevFilter === "all" || i.severity === sevFilter) &&
      (dimFilter === "all" || i.strategic_dimension === dimFilter)),
    [issues, sevFilter, dimFilter],
  );

  const sevCounts = useMemo(() => {
    const c: Record<string, number> = {};
    issues.forEach((i) => { c[i.severity] = (c[i.severity] ?? 0) + 1; });
    return c;
  }, [issues]);

  const totalReports = useMemo(
    () => issues.reduce((n, i) => n + (i.reports || 1), 0), [issues]);
  const verified = useMemo(
    () => issues.filter((i) => i.evidence_status === "exact" || i.evidence_status === "partial").length,
    [issues]);
  const corroborated = useMemo(
    () => issues.filter((i) => (i.corroboration_count ?? 0) > 1).length, [issues]);

  return (
    <div className="space-y-4">
      {/* summary strip */}
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { v: issues.length, k: "issues" },
          { v: totalReports, k: "reports behind them" },
          { v: `${issues.length ? Math.round((100 * verified) / issues.length) : 0}%`, k: "evidence verified" },
          { v: corroborated, k: "confirmed by 2+ sources" },
        ].map((s) => (
          <div key={s.k} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xl font-bold text-slate-900">{s.v}</div>
            <div className="text-[11px] text-slate-500">{s.k}</div>
          </div>
        ))}
      </div>

      {sources && sources.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-slate-500">Sources analysed</h3>
          <div className="space-y-1">
            {sources.map((s, idx) => (
              <div key={idx} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50">
                <span className="flex items-center gap-2">
                  <span className={`flex h-5 w-5 items-center justify-center rounded ${KIND_META[s.kind]?.tint ?? "bg-slate-50"}`}>
                    {KIND_META[s.kind]?.icon}
                  </span>
                  <span className="text-slate-700">{s.client || s.ref_id}</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">{s.chunks} {s.chunks === 1 ? "part" : "parts"}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    s.status === "ok" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>
                    {s.status}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {run && run.warnings?.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <h3 className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5" /> Check before publishing
          </h3>
          <ul className="ml-4 list-disc space-y-0.5 text-xs text-amber-800">
            {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200">
        {([["issues", `Issues (${issues.length})`],
           ["conflicts", `Conflicts (${conflicts.length})`],
           ["recs", `Recommendations (${recommendations.length})`]] as const)
          .map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold transition ${
                tab === id ? "border-ey-navy text-slate-900" : "border-transparent text-slate-400 hover:text-slate-600"}`}>
              {label}
            </button>
          ))}
      </div>

      {tab === "issues" ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => setSevFilter("all")}
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                sevFilter === "all" ? "bg-ey-navy text-white" : "bg-slate-100 text-slate-600"}`}>
              All {issues.length}
            </button>
            {SEV_ORDER.filter((s) => sevCounts[s]).map((s) => (
              <button key={s} onClick={() => setSevFilter(s)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase ring-1 ${
                  sevFilter === s ? SEV_CHIP[s] : "bg-white text-slate-500 ring-slate-200"}`}>
                {s} {sevCounts[s]}
              </button>
            ))}
            {dimensions.length > 1 && (
              <select value={dimFilter} onChange={(e) => setDimFilter(e.target.value)}
                className="ml-auto rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 outline-none">
                <option value="all">All dimensions</option>
                {dimensions.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
          </div>

          {visible.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">No issues match this filter.</p>
          ) : (
            <div className="space-y-2.5">
              {visible.map((i) => (
                <IssueCard key={i.issue_no} issue={i} logId={logId}
                  onChanged={() => onIssuesChanged?.()} onError={onError} />
              ))}
            </div>
          )}
        </>
      ) : tab === "conflicts" ? (
        conflicts.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">
            No sources contradicted each other.
          </p>
        ) : (
          <div className="space-y-2.5">
            <p className="text-xs text-slate-500">
              Two sources made claims that cannot both be true. Resolve these before the log goes
              to the client.
            </p>
            {conflicts.map((c) => (
              <div key={c.ref} className="rounded-xl border border-rose-200 bg-rose-50/40 p-4">
                <div className="mb-2 flex items-center gap-2">
                  <GitCompareArrows className="h-4 w-4 text-rose-600" />
                  <span className="font-mono text-[11px] font-semibold text-rose-700">{c.ref}</span>
                  <span className="font-mono text-[11px] text-slate-400">
                    issues {c.issue_a} / {c.issue_b}
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {([[c.source_a, c.a_claims], [c.source_b, c.b_claims]] as const).map(([src, claim], n) => (
                    <div key={n} className="rounded-lg border border-slate-200 bg-white p-3">
                      <p className="mb-1 truncate text-[11px] font-semibold text-slate-500" title={src}>{src}</p>
                      <p className="text-sm leading-relaxed text-slate-700">{claim}</p>
                    </div>
                  ))}
                </div>
                {c.why_it_matters && (
                  <p className="mt-2 text-xs italic text-slate-600">{c.why_it_matters}</p>
                )}
              </div>
            ))}
          </div>
        )
      ) : recommendations.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400">No recommendations generated.</p>
      ) : (
        <div className="space-y-2.5">
          {recommendations.map((r) => (
            <div key={r.ref} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-slate-400">{r.ref}</span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${EFFORT_CHIP[r.effort] ?? "bg-slate-100"}`}>
                  {r.effort}
                </span>
                <span className="text-[11px] text-slate-500">{r.impact} impact</span>
                {r.issues_addressed > 0 && (
                  <span className="text-[11px] text-slate-400">· fixes {r.issues_addressed} issue{r.issues_addressed > 1 ? "s" : ""}</span>
                )}
              </div>
              <h4 className="flex items-start gap-2 text-[15px] font-bold leading-snug text-slate-900">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                {r.action}
              </h4>
              {r.rationale && <p className="mt-1.5 pl-6 text-sm leading-relaxed text-slate-600">{r.rationale}</p>}
              {r.addresses.length > 0 && (
                <p className="mt-2 pl-6 font-mono text-[11px] text-slate-400">
                  Issues: {r.addresses.join(", ")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── input picker ─────────────────────────── */

