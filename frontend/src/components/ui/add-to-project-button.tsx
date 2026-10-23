import { useEffect, useRef, useState, type FormEvent } from "react";
import { FolderPlus, Check, Plus } from "lucide-react";
import {
  listProjects,
  createProject,
  attachArtifact,
  setProjectStep,
  type AnalysisKind,
  type Project,
  type StepKey,
} from "../../lib/projectsApi";
import { useActiveProject } from "../../context/ActiveProjectContext";

type Props = {
  kind: AnalysisKind;
  refId: string;
  stepKey: StepKey;
  title?: string;
  /** Prefill for a new project's name (usually the company/brand). */
  suggestedName?: string;
  compact?: boolean;
};

/** Attach the result you're looking at to a project (existing or new). The counterpart to
 *  auto-attach: it covers the "explore first, organise into a project later" flow. */
export default function AddToProjectButton({
  kind,
  refId,
  stepKey,
  title,
  suggestedName,
  compact,
}: Props) {
  const { project: active, refresh } = useActiveProject();
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [added, setAdded] = useState<Set<number>>(new Set());
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      setNewName(suggestedName ?? "");
      listProjects().then(setProjects).catch(() => setProjects([]));
    }
  };

  const addTo = async (projectId: number) => {
    setBusy(true);
    try {
      await attachArtifact(projectId, { kind, ref_id: refId, step_key: stepKey, title });
      await setProjectStep(projectId, stepKey, "done"); // the step now has a result
      setAdded((prev) => new Set(prev).add(projectId));
      if (active?.id === projectId) await refresh();
    } finally {
      setBusy(false);
    }
  };

  const createAndAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setBusy(true);
    try {
      const p = await createProject({ name: newName.trim(), company_name: suggestedName });
      setProjects((prev) => [p, ...prev]);
      await addTo(p.id);
      setNewName("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={toggle}
        className={
          compact
            ? "inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
            : "inline-flex items-center gap-1.5 rounded-lg bg-ey-navy px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-ey-navy-hover"
        }
      >
        <FolderPlus className="h-3.5 w-3.5" />
        Add to project
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 rounded-xl border border-slate-100 bg-white p-3 shadow-[0_12px_40px_rgba(15,23,42,0.14)]">
          <p className="mb-2 text-xs font-semibold text-slate-700">Add this result to a project</p>

          <div className="max-h-52 space-y-1 overflow-y-auto">
            {projects.length === 0 && (
              <p className="px-1 py-2 text-[11px] text-slate-400">No projects yet — create one below.</p>
            )}
            {projects.map((p) => {
              const isAdded = added.has(p.id);
              return (
                <div key={p.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-1.5">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-slate-700">{p.name}</div>
                    {p.company_name && (
                      <div className="truncate text-[10px] text-slate-400">{p.company_name}</div>
                    )}
                  </div>
                  {isAdded ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                      <Check className="h-3.5 w-3.5" /> Added
                    </span>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => addTo(p.id)}
                      className="rounded-full bg-ey-navy px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-ey-navy-hover disabled:opacity-40"
                    >
                      Add
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          <form onSubmit={createAndAdd} className="mt-2.5 flex items-center gap-1.5 border-t border-slate-100 pt-2.5">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New project name"
              className="flex-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15"
            />
            <button
              type="submit"
              disabled={busy || !newName.trim()}
              title="Create project & add"
              className="flex h-7 items-center gap-1 rounded-lg bg-ey-gold px-2.5 text-[11px] font-bold text-ey-navy hover:opacity-90 disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" /> New
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
