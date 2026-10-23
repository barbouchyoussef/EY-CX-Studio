import { useState } from "react";
import {
  Plus,
  ChevronDown,
  FolderPlus,
  ArrowRight,
  FileText,
  FileBarChart,
  Sparkles,
  MoreVertical,
  RefreshCw,
  Trash2,
  Users,
} from "lucide-react";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useProjectArtifactRefs } from "../../lib/use-project-artifacts";
import { interviewLabels } from "./copy";
import ShareButton from "../../components/ui/share-button";
import type { ProjectReportState } from "./use-project-report";

export type InterviewItem = {
  id: number;
  company_name: string;
  profile: string;
  updated_at: string;
  has_insights?: boolean;
  owned?: boolean;
  assessment_id?: number | null; // source: grounded in a maturity assessment, or from scratch
  owner_name?: string | null; // the consultant who created it
  question_count?: number;
};

/**
 * A clear, detailed table of saved interview guides — the interview module's landing surface,
 * mirroring the maturity-assessment dashboard. Project-aware: standalone it lists all your
 * interviews; inside a project it lists the project's interviews plus an "import" picker.
 */
export default function InterviewHistoryTable({
  interviews,
  onOpen,
  onNew,
  onDelete,
  isFrench,
  projectReport,
  onViewReport,
}: {
  interviews: InterviewItem[];
  onOpen: (id: number) => void;
  onNew: () => void;
  onDelete?: (item: InterviewItem) => void;
  isFrench: boolean;
  /** Owned by the hub so the table and the report page share one instance. */
  projectReport?: ProjectReportState;
  /** Opens the report as its own page, the way every other result in the app opens. */
  onViewReport?: () => void;
}) {
  const labels = interviewLabels(isFrench);
  const { project, attach } = useActiveProject();
  const { refs: projectRefs, markAttached } = useProjectArtifactRefs("interview_guide");
  const [importing, setImporting] = useState(false);
  const [openMenu, setOpenMenu] = useState<number | null>(null);


  const fmt = (d: string) =>
    new Date(d).toLocaleDateString(labels.dateLocale, { month: "short", day: "numeric", year: "numeric" });

  const inProject = interviews.filter((g) => projectRefs.has(String(g.id)));
  const rows = project ? inProject : interviews;
  const others = interviews.filter((g) => !projectRefs.has(String(g.id)));

  const doImport = async (g: InterviewItem) => {
    await attach("interview_guide", String(g.id), "interview", g.company_name);
    markAttached(String(g.id));
  };

  // Render functions, not components. Declaring a component inside another creates a new
  // component type on every render, so React unmounts and remounts the whole table -- losing
  // focus, scroll position and anything else the subtree holds. Returning elements from a
  // plain function does not, because there is no new type for React to compare.
  const renderRow = (g: InterviewItem, onImport?: () => void) => {
    const isOwned = g.owned !== false;
    return (
      <tr key={g.id} className="border-t border-slate-100 transition hover:bg-slate-50/60">
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-500">
              <FileText className="h-3.5 w-3.5" />
            </span>
            <span className="font-semibold text-slate-800">{g.company_name}</span>
            {!isOwned && (
              <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-sky-600">
                <Users className="h-3 w-3" />
                {labels.sharedWithYou}
              </span>
            )}
          </div>
          <div className="mt-1 pl-9 text-[11px] text-slate-400">
            {g.owner_name ? <span>{g.owner_name} · </span> : null}
            {g.assessment_id
              ? labels.sourceFromAssessment
              : labels.sourceFromScratch}
          </div>
        </td>
        <td className="px-4 py-3 text-sm text-slate-600">{g.profile || <span className="text-slate-300">—</span>}</td>
        <td className="px-4 py-3 text-sm tabular-nums text-slate-600">
          {g.question_count ? (
            <span>{g.question_count} <span className="text-slate-400">{labels.questionsSuffix}</span></span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td className="px-4 py-3">
          {g.has_insights ? (
            <button
              onClick={() => onOpen(g.id)}
              title={labels.viewBriefing}
              className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 transition hover:bg-amber-100"
            >
              <Sparkles className="h-3 w-3" /> {labels.viewInsights}
            </button>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-xs tabular-nums text-slate-400">{fmt(g.updated_at)}</td>
        <td className="px-4 py-3 text-right">
          {onImport ? (
            <button
              onClick={onImport}
              className="btn-primary-sm"
            >
              <FolderPlus className="h-3 w-3" /> {labels.add}
            </button>
          ) : (
            <div className="flex items-center justify-end gap-1">
              <button
                onClick={() => onOpen(g.id)}
                className="btn-secondary-sm"
              >
                {labels.open}
                <ArrowRight className="h-3 w-3" />
              </button>
              {isOwned && <ShareButton kind="interview_guide" refId={String(g.id)} compact />}
              {onDelete && isOwned && (
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu((cur) => (cur === g.id ? null : g.id))}
                    className="btn-icon"
                    aria-label={labels.moreActions}
                  >
                    <MoreVertical className="h-3.5 w-3.5" />
                  </button>
                  {openMenu === g.id && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                      <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-left shadow-lg">
                        <button
                          onClick={() => {
                            setOpenMenu(null);
                            onDelete(g);
                          }}
                          className="menu-item-danger"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          {labels.deletePermanently}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </td>
      </tr>
    );
  };

  const renderTable = (data: InterviewItem[], onImport?: (g: InterviewItem) => void) => (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-2.5">{labels.company}</th>
            <th className="px-4 py-2.5">{labels.profile}</th>
            <th className="px-4 py-2.5">{labels.questionsColumn}</th>
            <th className="px-4 py-2.5">{labels.insightsColumn}</th>
            <th className="px-4 py-2.5">{labels.updatedColumn}</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {data.map((g) => (
            renderRow(g, onImport ? () => onImport(g) : undefined)
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <FileText className="h-4 w-4 text-blue-500" />
          {project
            ? `${labels.projectInterviews} ${project.name}`
            : labels.interviewsHeading}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">{rows.length}</span>
        </h2>
        <div className="flex items-center gap-2">
          {project && projectReport && rows.length > 0 && (
            <>
              <button
                onClick={() => void projectReport.generate()}
                disabled={projectReport.generating}
                title={projectReport.stale ? labels.reportStale : undefined}
                className="btn-secondary-sm disabled:cursor-not-allowed disabled:opacity-60"
              >
                {projectReport.generating ? (
                  <>
                    <RefreshCw className="h-3 w-3 animate-spin" /> {labels.reportGenerating}
                  </>
                ) : projectReport.report ? (
                  <>
                    <RefreshCw className="h-3 w-3" /> {labels.regenerateReport}
                  </>
                ) : (
                  <>
                    <FileBarChart className="h-3 w-3" /> {labels.generateReport}
                  </>
                )}
              </button>
              {projectReport.report && onViewReport && (
                <button onClick={onViewReport} className="btn-secondary-sm">
                  <FileBarChart className="h-3 w-3" />
                  {labels.viewReport}
                  {projectReport.stale && (
                    <span className="ml-1 h-1.5 w-1.5 rounded-full bg-amber-400" />
                  )}
                </button>
              )}
            </>
          )}
          <button
            onClick={onNew}
            className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-ink-hover"
          >
            <Plus className="h-3.5 w-3.5" /> {labels.newInterview}
          </button>
        </div>
      </div>

      {project && projectReport?.error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {projectReport.error}
        </p>
      )}

      {rows.length > 0 ? (
        renderTable(rows)
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">
          {project
            ? labels.emptyInProject
            : labels.emptyNoInterviews}
        </p>
      )}

      {project && (
        <div>
          <button
            type="button"
            onClick={() => setImporting((v) => !v)}
            className="btn-quiet"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${importing ? "rotate-180" : ""}`} />
            {labels.importInterview}
          </button>
          {importing &&
            (others.length > 0 ? (
              <div className="mt-2">
                {renderTable(others, doImport)}
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-slate-400">
                {labels.nothingToImport}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}
