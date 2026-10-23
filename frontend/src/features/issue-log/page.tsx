import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, ArrowLeft, ClipboardList, Download, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { authFetch } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { listArtifacts, type AnalysisKind } from "../../lib/projectsApi";
import { useActiveProject } from "../../context/ActiveProjectContext";
import StudioNav from "../../components/ui/studio-nav";
import ShareButton from "../../components/ui/share-button";
import ModuleHeader from "../../components/ui/module-header";
import ResultView from "./result-view";
import InputSection from "./input-section";
import {
  KIND_META, STATUS_CHIP, fmtDate, loadAllArtifacts, downloadWorkbook,
  type Input, type Issue, type Conflict, type Recommendation, type SourceStat, type GenerateResult, type Preview, type SavedItem,
} from "./types";

export default function IssueLogPage(
  { onBack, topSlot }: { onBack: () => void; topSlot?: ReactNode },
) {
  const { project } = useActiveProject();
  const [view, setView] = useState<"dashboard" | "builder" | "viewer">("dashboard");

  const [saved, setSaved] = useState<SavedItem[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(true);

  const [inputs, setInputs] = useState<Input[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [openKind, setOpenKind] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [focus, setFocus] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  // Kept after the job finishes so the result is editable straight away, without a
  // round trip through the dashboard.
  const [resultLogId, setResultLogId] = useState<number | null>(null);
  const [jobProgress, setJobProgress] = useState<string | null>(null);

  const [viewing, setViewing] = useState<
    { id: number; name: string; created_at: string; findings: Issue[];
      recommendations: Recommendation[]; conflicts: Conflict[]; sources: SourceStat[] } | null
  >(null);
  const [loadingView, setLoadingView] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const keyOf = (i: Input) => `${i.kind}:${i.ref_id}`;

  const loadSaved = useCallback(async () => {
    setLoadingSaved(true); setError(null);
    try {
      const r = await authFetch("/issue-log");
      setSaved(r.ok ? await r.json() : []);
    } catch (e) { setError(errorMessage(e, "Failed to load issue logs")); }
    finally { setLoadingSaved(false); }
  }, []);

  useEffect(() => { loadSaved(); }, [loadSaved]);

  /* Keep the dashboard live while anything is still running. Runs outlive this page, so a
     consultant who starts one, leaves, and comes back should see it finish without pressing
     Refresh. Polling stops on its own once nothing is in flight. */
  const anyRunning = useMemo(
    () => saved.some((s) => s.status === "pending" || s.status === "running"), [saved]);

  useEffect(() => {
    if (view !== "dashboard" || !anyRunning) return;
    const timer = setInterval(loadSaved, 5000);
    return () => clearInterval(timer);
  }, [view, anyRunning, loadSaved]);

  /* Poll a running job. Every 4 s: slow enough to be cheap, quick enough to feel live.
     The payload stays small until the run finishes, when it carries the whole result. */
  useEffect(() => {
    if (jobId == null) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const r = await authFetch(`/issue-log/${jobId}/status`);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        setJobProgress(d.progress ?? null);
        if (d.status === "completed") {
          setResult({ issues: d.issues ?? [], recommendations: d.recommendations ?? [],
                      conflicts: d.conflicts ?? [], sources: d.sources ?? [], run: d.run });
          setGenerating(false); setJobId(null); loadSaved();
        } else if (d.status === "failed") {
          setError(d.error || "The run failed.");
          setGenerating(false); setJobId(null); loadSaved();
        }
      } catch { /* a dropped poll is harmless; the next one catches up */ }
    };

    tick();
    const timer = setInterval(tick, 4000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [jobId, loadSaved]);

  const loadInputs = useCallback(async () => {
    setLoading(true); setError(null); setResult(null); setPreview(null); setSelected(new Set());
    try {
      const items = project
        ? (await listArtifacts(project.id)).map((a) => ({ kind: a.kind as AnalysisKind, ref_id: a.ref_id, title: a.title || a.ref_id }))
        : await loadAllArtifacts();
      setInputs(items);
    } catch (e) {
      setError(errorMessage(e, "Failed to load inputs"));
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  const startNew = () => {
    setView("builder"); setResult(null); setPreview(null); setFocus("");
    setName(project ? `${project.name} — Issue Log` : "");
    loadInputs();
  };

  const openSaved = async (id: number) => {
    setView("viewer"); setLoadingView(true); setViewing(null); setError(null);
    try {
      const r = await authFetch(`/issue-log/${id}`);
      if (!r.ok) throw new Error(`Failed to open (${r.status})`);
      const d = await r.json();
      setViewing({
        id: d.id, name: d.name, created_at: d.created_at,
        findings: d.findings ?? [], recommendations: d.recommendations ?? [],
        conflicts: d.conflicts ?? [], sources: d.sources ?? [],
      });
    } catch (e) { setError(errorMessage(e, "Failed to open issue log")); }
    finally { setLoadingView(false); }
  };

  const removeSaved = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this issue log?")) return;
    try {
      await authFetch(`/issue-log/${id}`, { method: "DELETE" });
      setSaved((prev) => prev.filter((s) => s.id !== id));
    } catch (err) { setError(errorMessage(err, "Delete failed")); }
  };

  const toggle = (i: Input) => setSelected((prev) => {
    const n = new Set(prev); const k = keyOf(i);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });

  const setSection = (items: Input[], on: boolean) => setSelected((prev) => {
    const n = new Set(prev);
    items.forEach((i) => (on ? n.add(keyOf(i)) : n.delete(keyOf(i))));
    return n;
  });

  const selections = () => inputs.filter((i) => selected.has(keyOf(i))).map((i) => ({ kind: i.kind, ref_id: i.ref_id }));
  const selectedCount = inputs.filter((i) => selected.has(keyOf(i))).length;

  /** Cheap check of what will actually be read, before spending on generation. */
  const runPreview = async () => {
    setPreviewing(true); setError(null); setResult(null);
    try {
      const res = await authFetch("/issue-log/preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selections: selections() }),
      });
      if (!res.ok) throw new Error(`Preview failed (${res.status})`);
      setPreview(await res.json());
    } catch (e) { setError(errorMessage(e, "Preview failed")); }
    finally { setPreviewing(false); }
  };

  /** Start the run and follow it. The job keeps going server-side even if this page closes,
   *  so leaving mid-run only stops the polling, never the work. */
  const generate = async () => {
    setGenerating(true); setError(null); setResult(null);
    try {
      const res = await authFetch("/issue-log/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || "Issue Log",
          project_id: project?.id ?? null,
          selections: selections(),
          focus: focus.trim() || null,
          sweep: true, recommendations: true, max_issues: 200,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `Could not start (${res.status})`);
      }
      const job = await res.json();
      setJobId(job.id);
      setResultLogId(job.id);
      setJobProgress(job.progress ?? "Queued");
      loadSaved();                     // it appears in the dashboard immediately
    } catch (e) {
      setError(errorMessage(e, "Could not start the run"));
      setGenerating(false);
    }
  };

  const byKind = useMemo(() => {
    const g: Record<string, Input[]> = {};
    inputs.forEach((i) => { (g[i.kind] ??= []).push(i); });
    return g;
  }, [inputs]);

  const header = (
    <div className="mb-1 flex items-center gap-2">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ey-yellow/25 text-ey-gold-deep">
        <ClipboardList className="h-5 w-5" />
      </span>
      <h1 className="text-2xl font-bold text-slate-900">Issue Log</h1>
    </div>
  );

  const errorBar = error && (
    <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-700">
      <AlertTriangle className="h-4 w-4" /> {error}
    </div>
  );

  /* ─────────────── DASHBOARD ─────────────── */
  if (view === "dashboard") {
    return (
      <div className="min-h-screen bg-slate-50">
        <ModuleHeader title="Issue Log" subtitle="Consolidated client issues" onBack={onBack} right={
          <button onClick={loadSaved} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-300">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        } />
        {topSlot}
        <div className="mx-auto max-w-5xl px-5 py-8">


          {header}
          <p className="mb-6 text-sm text-slate-500">
            Turn your analyses into a client-ready issue log
            {project ? <> for <span className="font-semibold text-slate-700">{project.name}</span></> : null}.
          </p>

          {errorBar}

          <button onClick={startNew}
            className="mb-5 flex w-full items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-4 text-left transition hover:border-ey-navy hover:bg-slate-50">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ey-navy text-white"><Plus className="h-5 w-5" /></span>
            <span>
              <span className="block text-sm font-bold text-slate-900">New issue log</span>
              <span className="block text-xs text-slate-500">Pick your analyses and generate issues with recommendations.</span>
            </span>
          </button>

          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Saved issue logs</h2>
          {loadingSaved ? (
            <div className="flex items-center gap-2 py-8 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
          ) : saved.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-400">
              No issue logs yet — create your first one above.
            </div>
          ) : (
            <div className="space-y-2.5">
              {saved.map((s) => (
                <div key={s.id} onClick={() => openSaved(s.id)}
                  className="flex cursor-pointer items-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 transition hover:border-slate-300 hover:shadow-sm">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ey-yellow/25 text-ey-gold-deep"><ClipboardList className="h-5 w-5" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-bold text-slate-900">{s.name}</span>
                      {s.status !== "completed" && (
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_CHIP[s.status]}`}>
                          {s.status === "running" || s.status === "pending" ? (
                            <span className="inline-flex items-center gap-1">
                              <Loader2 className="h-2.5 w-2.5 animate-spin" /> {s.status}
                            </span>
                          ) : s.status}
                        </span>
                      )}
                    </span>
                    <span className="block truncate text-xs text-slate-400">
                      {s.status === "completed"
                        ? `${s.findings_count} issues · ${s.recommendations_count} recommendations · ${fmtDate(s.created_at)}`
                        : s.status === "failed"
                          ? (s.error || "Run failed")
                          : (s.progress || "Queued") + " — you can close this page"}
                    </span>
                  </span>
                  {s.status === "completed" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); downloadWorkbook(s.id, s.name, setError); }}
                      title="Download Excel"
                      className="rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:border-emerald-300 hover:text-emerald-600">
                      <Download className="h-4 w-4" />
                    </button>
                  )}
                  {/* Sharing is the owner's to give away; a recipient cannot re-share or delete. */}
                  {s.owned !== false && (
                    <span onClick={(e) => e.stopPropagation()}>
                      <ShareButton kind="issue_log" refId={String(s.id)} compact />
                    </span>
                  )}
                  {s.owned !== false && (
                    <button onClick={(e) => removeSaved(s.id, e)} title="Delete"
                      className="rounded-lg border border-slate-200 p-2 text-slate-400 transition hover:border-rose-300 hover:text-rose-500">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ─────────────── VIEWER ─────────────── */
  if (view === "viewer") {
    return (
      <div className="min-h-screen bg-slate-50">
        {topSlot}
        <div className="mx-auto max-w-5xl px-5 py-8">
          <div className="mb-6 flex items-center justify-between">
            <button onClick={() => setView("dashboard")} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800">
              <ArrowLeft className="h-4 w-4" /> All issue logs
            </button>
            <div className="flex items-center gap-3">
              {viewing && (
                <>
                  <ShareButton kind="issue_log" refId={String(viewing.id)} compact />
                  <button onClick={() => downloadWorkbook(viewing.id, viewing.name, setError)}
                    className="inline-flex items-center gap-1.5 rounded-full bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700">
                    <Download className="h-3.5 w-3.5" /> Excel
                  </button>
                </>
              )}
              <StudioNav />
            </div>
          </div>
          {errorBar}
          {loadingView ? (
            <div className="flex items-center gap-2 py-16 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
          ) : viewing ? (
            <>
              <h1 className="mb-1 text-2xl font-bold text-slate-900">{viewing.name}</h1>
              <p className="mb-6 text-sm text-slate-500">{fmtDate(viewing.created_at)}</p>
              <ResultView issues={viewing.findings} recommendations={viewing.recommendations}
                conflicts={viewing.conflicts} sources={viewing.sources}
                logId={viewing.id} onError={setError}
                onIssuesChanged={() => openSaved(viewing.id)} />
            </>
          ) : null}
        </div>
      </div>
    );
  }

  /* ─────────────── BUILDER ─────────────── */
  return (
    <div className="min-h-screen bg-slate-50">
        {topSlot}
      <div className="mx-auto max-w-5xl px-5 py-8">
        <div className="mb-6 flex items-center justify-between">
          <button onClick={() => setView("dashboard")} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800">
            <ArrowLeft className="h-4 w-4" /> All issue logs
          </button>
          <StudioNav />
        </div>

        {header}
        <p className="mb-6 text-sm text-slate-500">
          Pick the analyses to draw from. Each document is read on its own; customer reviews are read together.
        </p>

        {errorBar}

        <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-5">
          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Issue Log"
            className="mb-4 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" />

          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
            Focus <span className="font-normal normal-case text-slate-400">(optional)</span>
          </label>
          <input value={focus} onChange={(e) => setFocus(e.target.value)}
            placeholder="e.g. concentrate on the call centre and the mobile app"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" />
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-16 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading analyses…</div>
        ) : inputs.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-400">
            No analyses available yet.
          </div>
        ) : (
          <div className="space-y-2.5">
            {Object.entries(byKind).map(([kind, items]) => (
              <InputSection key={kind} kind={kind} items={items}
                isOpen={openKind === kind} onToggleOpen={() => setOpenKind(openKind === kind ? null : kind)}
                selected={selected} keyOf={keyOf} onToggle={toggle} onSetSection={setSection} />
            ))}
          </div>
        )}

        {preview && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">What will be read</h3>
            <p className="mb-3 text-sm text-slate-600">
              <span className="font-bold text-slate-900">{preview.chunks}</span> parts ·{" "}
              <span className="font-bold text-slate-900">{preview.tokens.toLocaleString()}</span> tokens of source material
            </p>
            <div className="space-y-1">
              {preview.sources.map((s, idx) => (
                <div key={idx} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm">
                  <span className="flex items-center gap-2">
                    <span className={`flex h-5 w-5 items-center justify-center rounded ${KIND_META[s.kind]?.tint ?? "bg-slate-50"}`}>
                      {KIND_META[s.kind]?.icon}
                    </span>
                    <span className="text-slate-700">{s.client || s.ref_id}</span>
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    s.status === "ok" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-700"}`}>
                    {s.status === "ok" ? `${s.chunks} part${s.chunks > 1 ? "s" : ""}` : s.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="sticky bottom-0 mt-5 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-slate-50/95 py-4 backdrop-blur">
          <span className="text-sm text-slate-500">{selectedCount} selected</span>
          <button onClick={runPreview} disabled={selectedCount === 0 || previewing || generating}
            className="ml-auto rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 disabled:opacity-40">
            {previewing ? <Loader2 className="h-4 w-4 animate-spin" /> : "Check sources"}
          </button>
          <button onClick={generate} disabled={selectedCount === 0 || generating}
            className="inline-flex items-center gap-2 rounded-full bg-ey-navy px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#2a3050] disabled:opacity-40">
            {generating ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</> : "Generate issue log"}
          </button>
          {result && (
            <button onClick={() => setView("dashboard")}
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700">
              Done
            </button>
          )}
        </div>

        {generating && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-sky-800">
              <Loader2 className="h-4 w-4 animate-spin" />
              {jobProgress || "Starting…"}
            </p>
            <p className="mt-1 text-xs text-sky-700">
              Each source is read on its own, so this takes a few minutes. The run continues on the
              server — you can leave this page and open it from the dashboard when it finishes.
            </p>
          </div>
        )}

        {result && (
          <div className="mt-4">
            <ResultView issues={result.issues} recommendations={result.recommendations}
              conflicts={result.conflicts} sources={result.sources} run={result.run}
              logId={resultLogId ?? undefined} onError={setError}
              onIssuesChanged={async () => {
                if (resultLogId == null) return;
                const r = await authFetch(`/issue-log/${resultLogId}`);
                if (!r.ok) return;
                const d = await r.json();
                setResult({ issues: d.findings ?? [], recommendations: d.recommendations ?? [],
                            conflicts: d.conflicts ?? [], sources: d.sources ?? [], run: d.run });
              }} />
          </div>
        )}
      </div>
    </div>
  );
}
