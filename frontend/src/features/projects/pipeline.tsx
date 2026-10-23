import { useEffect, useRef, useState, type ReactNode } from "react";
import { projectCopy } from "./copy";
import { ArrowRight, Check, Circle, Clock, FileText, Trash2, MoreHorizontal, FolderMinus } from "lucide-react";
import type { Project, ProjectArtifact, StepKey, StepStatus } from "../../lib/projectsApi";
import ProjectMembersPanel from "./members-panel";
import { analysisKindLabel } from "../../lib/analysis-kinds";

/** One attached result, with a menu to remove it from the project (keep it) or delete it for good. */
function ArtifactRow({
  a,
  isFrench,
  onOpen,
  onDetach,
  onDelete,
}: {
  a: ProjectArtifact;
  isFrench: boolean;
  onOpen: () => void;
  onDetach: () => void;
  onDelete: () => void;
}) {
  const copy = projectCopy(isFrench);
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
      <button onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
        <FileText className="h-3.5 w-3.5 shrink-0 text-ey-gold" />
        <span className="min-w-0 flex-1 truncate font-medium text-slate-700">
          {a.title || analysisKindLabel(a.kind, isFrench)}
        </span>
      </button>
      <span className="shrink-0 text-[10px] uppercase tracking-wide text-slate-400">
        {analysisKindLabel(a.kind, isFrench)}
      </span>
      <div ref={ref} className="relative shrink-0">
        <button
          onClick={() => setMenu((o) => !o)}
          className="rounded-md p-1 text-slate-400 transition hover:bg-slate-200 hover:text-slate-600"
          title="Options"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
        {menu && (
          <div className="absolute right-0 z-10 mt-1 w-52 overflow-hidden rounded-lg border border-slate-100 bg-white py-1 shadow-[0_12px_40px_rgba(15,23,42,0.14)]">
            <button
              onClick={() => { setMenu(false); onDetach(); }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 transition hover:bg-slate-50"
            >
              <FolderMinus className="h-3.5 w-3.5 text-slate-400" />
              {copy.removeFromProject}
            </button>
            <button
              onClick={() => { setMenu(false); onDelete(); }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-600 transition hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {copy.deletePermanently}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export type PipelineStepMeta = {
  key: string;
  step: number;
  title: string;
  desc: string;
  icon: ReactNode;
  iconBg: string;
  iconColor: string;
  comingSoon?: boolean;
};

type Props = {
  project: Project;
  steps: PipelineStepMeta[];
  artifacts: ProjectArtifact[];
  isFrench: boolean;
  onOpenStep: (key: StepKey) => void;
  onSetStatus: (key: StepKey, status: StepStatus) => void;
  onDelete: () => void;
  onAddMember: (email: string) => Promise<void>;
  onRemoveMember: (userId: number) => void | Promise<void>;
  onDetachArtifact: (artifactId: number) => void | Promise<void>;
  onDeleteArtifact: (a: ProjectArtifact) => void | Promise<void>;
};

const STATUS_META: Record<StepStatus, { ring: string; dot: string; label: (fr: boolean) => string }> = {
  done: { ring: "border-emerald-500 bg-emerald-500 text-white", dot: "bg-emerald-500", label: (fr) => (fr ? "Validé" : "Done") },
  in_progress: { ring: "border-amber-400 bg-amber-50 text-amber-600", dot: "bg-amber-400", label: (fr) => (fr ? "En cours" : "In progress") },
  todo: { ring: "border-slate-300 bg-white text-slate-400", dot: "bg-slate-300", label: (fr) => (fr ? "À faire" : "To do") },
};

const ORDER: StepStatus[] = ["todo", "in_progress", "done"];

export default function ProjectPipeline({
  project,
  steps,
  artifacts,
  isFrench,
  onOpenStep,
  onSetStatus,
  onDelete,
  onAddMember,
  onRemoveMember,
  onDetachArtifact,
  onDeleteArtifact,
}: Props) {
  const copy = projectCopy(isFrench);
  // "Coming soon" steps (e.g. Issue Log) are shown but excluded from progress.
  const realSteps = steps.filter((s) => !s.comingSoon);
  const artifactsByStep = artifacts.reduce<Record<string, ProjectArtifact[]>>((acc, a) => {
    (acc[a.step_key] ??= []).push(a);
    return acc;
  }, {});
  const doneCount = realSteps.filter((s) => project.steps[s.key] === "done").length;
  const pct = realSteps.length ? Math.round((doneCount / realSteps.length) * 100) : 0;

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10">
        {/* Project header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ey-navy/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-ey-navy">
              {copy.project}
            </span>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink">{project.name}</h1>
            {(project.company_name || project.sector) && (
              <p className="mt-1 text-sm text-slate-500">
                {[project.company_name, project.sector].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onDelete}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {copy.delete}
          </button>
        </div>

        {/* Progress */}
        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-slate-700">
              {copy.pipelineProgress}
            </span>
            <span className="tabular-nums font-semibold text-slate-500">
              {doneCount}/{steps.length} · {pct}%
            </span>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* Team / collaborators */}
        <ProjectMembersPanel
          members={project.members}
          myRole={project.my_role}
          isFrench={isFrench}
          onAdd={onAddMember}
          onRemove={onRemoveMember}
        />

        {/* Pipeline steps */}
        <div className="mt-8 space-y-4">
          {steps.map((s, i) => {
            if (s.comingSoon) {
              return (
                <div key={s.key} className="relative rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                    <div className="flex items-center gap-4">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-slate-300 bg-white text-slate-400">
                        <span className="text-sm font-bold">{s.step}</span>
                      </div>
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.iconBg} ${s.iconColor}`}>
                        {s.icon}
                      </div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-[15px] font-bold text-slate-700">{s.title}</h3>
                        <span className="rounded-full bg-ey-yellow/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ey-gold-deep">
                          {copy.soonBadge}
                        </span>
                      </div>
                      <p className="mt-1 text-[13px] leading-relaxed text-slate-400">{s.desc}</p>
                    </div>
                    <span className="shrink-0 inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-400">
                      {copy.comingSoon}
                    </span>
                  </div>
                </div>
              );
            }
            const status = project.steps[s.key] ?? "todo";
            const meta = STATUS_META[status];
            return (
              <div key={s.key} className="relative rounded-2xl border border-slate-200 bg-white p-5">
                {/* Connector down to the next step, drawn ONLY in the gap between cards.
                    It is aligned with the status circle (card p-5 = 20px, circle h-11 = 44px,
                    so centre x = 42px) and runs from the card's bottom edge (top-full) across
                    the 16px list gap (space-y-4) to the next card. Drawing it from under the
                    circle instead would cut straight through this card's own content, which is
                    where the "Attached results" rows sit. */}
                {i < steps.length - 1 && (
                  <span
                    className={`pointer-events-none absolute left-[41px] top-full h-4 w-px ${
                      status === "done" ? "bg-emerald-300" : "bg-slate-200"
                    }`}
                    aria-hidden
                  />
                )}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  {/* status circle */}
                  <div className="flex items-center gap-4">
                    <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 ${meta.ring}`}>
                      {status === "done" ? (
                        <Check className="h-5 w-5" />
                      ) : status === "in_progress" ? (
                        <Clock className="h-5 w-5" />
                      ) : (
                        <span className="text-sm font-bold">{s.step}</span>
                      )}
                    </div>
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.iconBg} ${s.iconColor}`}>
                      {s.icon}
                    </div>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-[15px] font-bold text-slate-900">{s.title}</h3>
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        status === "done" ? "bg-emerald-50 text-emerald-600"
                          : status === "in_progress" ? "bg-amber-50 text-amber-600"
                          : "bg-slate-100 text-slate-400"
                      }`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                        {meta.label(isFrench)}
                      </span>
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-slate-500">{s.desc}</p>
                  </div>

                  {/* controls */}
                  <div className="flex shrink-0 items-center gap-2">
                    {/* status segmented control */}
                    <div className="flex items-center rounded-lg border border-slate-200 p-0.5">
                      {ORDER.map((st) => (
                        <button
                          key={st}
                          type="button"
                          onClick={() => onSetStatus(s.key as StepKey, st)}
                          title={STATUS_META[st].label(isFrench)}
                          className={`flex h-7 w-7 items-center justify-center rounded-md transition ${
                            status === st ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-100"
                          }`}
                        >
                          {st === "done" ? <Check className="h-3.5 w-3.5" /> : st === "in_progress" ? <Clock className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenStep(s.key as StepKey)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-ey-navy px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-ey-navy-hover"
                    >
                      {copy.open}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {(artifactsByStep[s.key]?.length ?? 0) > 0 && (
                  <div className="mt-4 space-y-1.5 border-t border-slate-100 pt-3">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                      {copy.attachedResults}
                    </p>
                    {artifactsByStep[s.key].map((a) => (
                      <ArtifactRow
                        key={a.id}
                        a={a}
                        isFrench={isFrench}
                        onOpen={() => onOpenStep(s.key as StepKey)}
                        onDetach={() => onDetachArtifact(a.id)}
                        onDelete={() => onDeleteArtifact(a)}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </main>
  );
}
