import { FolderKanban, Check, ChevronRight } from "lucide-react";
import { projectCopy } from "./copy";
import { stepLabel } from "../../lib/analysis-kinds";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { PROJECT_STEP_KEYS, type StepKey } from "../../lib/projectsApi";

const STEP_ROUTE: Record<StepKey, string> = {
  assessment: "/assessment",
  interview: "/client-interview-hub",
  desk_research: "/desk-research",
  social: "/social-scraping",
  issue_log: "/issue-log",
};


/**
 * The "you are working inside a project" band, mounted above each module.
 *
 * It sits in normal flow at the top of the page rather than floating. It used to be a small
 * pill fixed to the bottom of the viewport, where it read as a toast and was easy to miss.
 * A fixed or sticky bar at the top was not an option either: half the modules already pin their
 * own header with `sticky top-0`, and two elements competing for that position looks broken.
 * In flow it is prominent on arrival, and each module's own header still behaves normally.
 */
export default function ProjectStepNav({
  currentStep,
  onNavigate,
  isFrench = false,
}: {
  currentStep: StepKey | null;
  onNavigate: (path: string) => void;
  isFrench?: boolean;
}) {
  const copy = projectCopy(isFrench);
  const { project } = useActiveProject();
  if (!project) return null;

  const done = PROJECT_STEP_KEYS.filter((k) => project.steps[k] === "done").length;
  const total = PROJECT_STEP_KEYS.length;

  return (
    <div className="no-print w-full border-b border-slate-200/70 bg-white">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-2 px-6 py-2">

        {/* Project identity → back to the pipeline */}
        <button
          type="button"
          onClick={() => onNavigate("/services")}
          title={copy.openProject}
          className="flex shrink-0 items-center gap-2 rounded-lg px-2 py-1 transition hover:bg-slate-100"
        >
          <FolderKanban className="h-4 w-4 shrink-0 text-ey-gold" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            {copy.project}
          </span>
          <span className="max-w-[13rem] truncate text-[13px] font-bold text-slate-800">
            {project.name}
          </span>
        </button>

        {/* Progress out of five, so the strip says where the work stands at a glance */}
        <span className="flex shrink-0 items-center gap-2">
          <span className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-slate-200 sm:block">
            <span
              className="block h-full rounded-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${(done / total) * 100}%` }}
            />
          </span>
          <span className="text-[11px] font-bold tabular-nums text-slate-500">
            {done}/{total}
          </span>
        </span>

        <span className="hidden h-5 w-px shrink-0 bg-slate-200 lg:block" />

        {/* The pipeline. Labels stay visible -- icons alone were the main reason it read as
            decoration rather than navigation. */}
        <nav
          aria-label={copy.projectSteps}
          className="flex min-w-0 flex-1 flex-wrap items-center gap-y-1"
        >
          {PROJECT_STEP_KEYS.map((k, i) => {
            const status = project.steps[k] ?? "todo";
            const active = k === currentStep;
            const isDone = status === "done";
            const isProgress = status === "in_progress";

            return (
              <div key={k} className="flex items-center">
                <button
                  type="button"
                  onClick={() => onNavigate(STEP_ROUTE[k])}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] font-semibold transition ${
                    active
                      ? "bg-ey-navy text-white"
                      : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  }`}
                >
                  <span
                    className={`flex h-[17px] w-[17px] shrink-0 items-center justify-center rounded-full text-[9.5px] font-bold ${
                      isDone
                        ? "bg-emerald-500 text-white"
                        : active
                          ? "bg-white text-ey-navy"
                          : isProgress
                            ? "bg-ey-yellow text-[#5a4900]"
                            : "border border-slate-300 text-slate-400"
                    }`}
                  >
                    {isDone ? <Check className="h-2.5 w-2.5" strokeWidth={3.5} /> : i + 1}
                  </span>
                  <span className="whitespace-nowrap">
                    {stepLabel(k, isFrench)}
                  </span>
                </button>
                {i < total - 1 && (
                  <ChevronRight
                    className={`h-3.5 w-3.5 shrink-0 ${isDone ? "text-emerald-400" : "text-slate-300"}`}
                    aria-hidden
                  />
                )}
              </div>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
