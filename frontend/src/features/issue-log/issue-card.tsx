/**
 * One finding, expandable to its evidence and editable in place.
 *
 * Editing writes straight through to the saved log, which is why it needs `logId` and why the
 * builder preview passes none -- there is no row to patch until the run has been saved.
 */

import { useState } from "react";
import { AlertTriangle, Loader2, Pencil, Quote, Save, Trash2, Users, X } from "lucide-react";
import { authFetch } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { SEV_CHIP, SEV_ORDER, type Severity, type Issue } from "./types";

export default function IssueCard({ issue, logId, onChanged, onError }: {
  issue: Issue;
  /** Editing is only possible on a saved log — the builder preview has no row to patch yet. */
  logId?: number;
  onChanged?: (updated: Issue | null) => void;
  onError?: (message: string) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({
    finding: issue.finding,
    investigation: issue.investigation,
    severity: issue.severity as Severity,
    comment: issue.comment ?? "",
  });
  const verified = issue.evidence_status === "exact" || issue.evidence_status === "partial";
  const canEdit = typeof logId === "number";

  const save = async () => {
    if (!canEdit) return;
    setBusy(true);
    try {
      const res = await authFetch(`/issue-log/${logId}/issues/${issue.issue_no}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail || `Could not save (${res.status})`);
      }
      onChanged?.(await res.json());
      setEditing(false);
    } catch (e) {
      onError?.(errorMessage(e, "Could not save the change"));
    } finally { setBusy(false); }
  };

  const remove = async () => {
    if (!canEdit) return;
    if (!confirm(`Delete issue ${issue.issue_no}? The remaining issues are renumbered.`)) return;
    setBusy(true);
    try {
      const res = await authFetch(`/issue-log/${logId}/issues/${issue.issue_no}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Could not delete (${res.status})`);
      onChanged?.(null);
    } catch (e) {
      onError?.(errorMessage(e, "Could not delete the issue"));
    } finally { setBusy(false); }
  };

  if (editing) {
    return (
      <div className="rounded-xl border-2 border-ey-navy bg-white p-4">
        <label className="mb-1 block text-[11px] font-bold uppercase tracking-wide text-slate-500">Finding</label>
        <input value={draft.finding} onChange={(e) => setDraft({ ...draft, finding: e.target.value })}
          className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold outline-none focus:border-slate-500" />

        <label className="mb-1 block text-[11px] font-bold uppercase tracking-wide text-slate-500">Investigation</label>
        <textarea value={draft.investigation} rows={5}
          onChange={(e) => setDraft({ ...draft, investigation: e.target.value })}
          className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm leading-relaxed outline-none focus:border-slate-500" />

        <div className="mb-3 flex flex-wrap items-center gap-3">
          <span className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Severity</span>
          {SEV_ORDER.map((sv) => (
            <button key={sv} onClick={() => setDraft({ ...draft, severity: sv })}
              className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase ring-1 ${
                draft.severity === sv ? SEV_CHIP[sv] : "bg-white text-slate-400 ring-slate-200"}`}>
              {sv}
            </button>
          ))}
        </div>

        <label className="mb-1 block text-[11px] font-bold uppercase tracking-wide text-slate-500">Comment</label>
        <input value={draft.comment} placeholder="Optional note for the client workbook"
          onChange={(e) => setDraft({ ...draft, comment: e.target.value })}
          className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500" />

        <div className="flex items-center gap-2">
          <button onClick={save} disabled={busy || !draft.finding.trim()}
            className="inline-flex items-center gap-1.5 rounded-full bg-ey-navy px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save
          </button>
          <button onClick={() => { setEditing(false); setDraft({
              finding: issue.finding, investigation: issue.investigation,
              severity: issue.severity, comment: issue.comment ?? "" }); }}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-4 py-1.5 text-xs font-semibold text-slate-600">
            <X className="h-3.5 w-3.5" /> Cancel
          </button>
          <span className="ml-auto text-[11px] text-slate-400">
            Source and evidence stay as generated
          </span>
        </div>
      </div>
    );
  }


  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] font-semibold text-slate-400">{issue.issue_no}</span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ring-1 ${SEV_CHIP[issue.severity]}`}>
          {issue.severity}
        </span>
        {issue.reports > 1 && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
            {issue.reports} reports
          </span>
        )}
        {(issue.corroboration_count ?? 0) > 1 && (
          <span title={(issue.corroborated_by ?? []).join(" · ")}
            className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
            <Users className="h-3 w-3" /> {issue.corroboration_count} sources agree
          </span>
        )}
        {issue.has_conflict && (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
            <AlertTriangle className="h-3 w-3" /> conflicts with {(issue.conflicts_with ?? []).join(", ")}
          </span>
        )}
        <span className="text-[11px] text-slate-400">
          {issue.strategic_dimension}{issue.sub_category ? ` · ${issue.sub_category}` : ""}
        </span>
        {issue.edited && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
            edited
          </span>
        )}
      </div>

      <div className="flex items-start gap-2">
        <h4 className="flex-1 text-[15px] font-bold leading-snug text-slate-900">{issue.finding}</h4>
        {canEdit && (
          <span className="flex shrink-0 items-center gap-1">
            <button onClick={() => setEditing(true)} title="Edit"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button onClick={remove} disabled={busy} title="Delete"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </span>
        )}
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{issue.investigation}</p>

      {issue.severity_reason && (
        <p className="mt-2 text-xs italic text-slate-500">Why {issue.severity}: {issue.severity_reason}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-slate-100 pt-2.5">
        <span className="truncate text-[11px] text-slate-400" title={issue.inspection_point}>
          {issue.inspection_point}
        </span>
        {issue.evidence && (
          <button
            onClick={() => setShowEvidence((v) => !v)}
            className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              verified ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
            }`}
          >
            <Quote className="h-3 w-3" />
            {verified ? "Evidence verified" : "Evidence unmatched"}
          </button>
        )}
      </div>

      {showEvidence && issue.evidence && (
        <blockquote className="mt-2 border-l-2 border-slate-300 bg-slate-50 px-3 py-2 text-xs italic leading-relaxed text-slate-600">
          “{issue.evidence}”
        </blockquote>
      )}
    </div>
  );
}

/* ─────────────────────────── result renderer ─────────────────────────── */

