import { useState } from "react";
import { socialTableCopy } from "./table-copy";
import { Plus, ChevronDown, FolderPlus, ArrowRight, Radio, MessagesSquare, MoreVertical, Trash2, Users } from "lucide-react";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useProjectArtifactRefs } from "../../lib/use-project-artifacts";
import ShareButton from "../../components/ui/share-button";

export type SocialReportItem = {
  filename: string;
  brand_name: string;
  scraped_at: string;
  total_reviews: number;
  owned?: boolean;
};

/**
 * The Social Listening dashboard: a clear table of saved reports, mirroring the maturity-assessment
 * and interview dashboards. Project-aware, with open / share / delete / import + a "New analysis"
 * button. The report ref is its filename.
 */
export default function SocialReportTable({
  reports,
  onOpen,
  onNew,
  onDelete,
  isFrench,
}: {
  reports: SocialReportItem[];
  onOpen: (filename: string) => void;
  onNew: () => void;
  onDelete?: (filename: string) => void;
  isFrench: boolean;
}) {
  const copy = socialTableCopy(isFrench);
  const { project, attach } = useActiveProject();
  const { refs: projectRefs, markAttached } = useProjectArtifactRefs("social_report");
  const [importing, setImporting] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const fmt = (d: string) =>
    new Date(d).toLocaleDateString(copy.dateLocale, { month: "short", day: "numeric", year: "numeric" });

  const inProject = reports.filter((r) => projectRefs.has(r.filename));
  const rows = project ? inProject : reports;
  const others = reports.filter((r) => !projectRefs.has(r.filename));

  const doImport = async (r: SocialReportItem) => {
    await attach("social_report", r.filename, "social", r.brand_name);
    markAttached(r.filename);
  };

  // Render functions, not components. Declaring a component inside another creates a new
  // component type on every render, so React unmounts and remounts the whole table -- losing
  // focus, scroll position and any open menu. Returning elements from a plain function does
  // not, because there is no new type for React to compare.
  const renderRow = (r: SocialReportItem, onImport?: () => void) => {
    const isOwned = r.owned !== false;
    return (
    <tr key={r.filename} className="border-t border-slate-100 transition hover:bg-slate-50/60">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-500">
            <Radio className="h-3.5 w-3.5" />
          </span>
          <span className="font-semibold text-slate-800">{r.brand_name}</span>
          {!isOwned && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-sky-600">
              <Users className="h-3 w-3" />
              {copy.sharedWithYou}
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          <MessagesSquare className="h-3.5 w-3.5 text-slate-400" />
          {r.total_reviews} {copy.reviewsSuffix}
        </span>
      </td>
      <td className="px-4 py-3 text-xs tabular-nums text-slate-400">{fmt(r.scraped_at)}</td>
      <td className="px-4 py-3 text-right">
        {onImport ? (
          <button
            onClick={onImport}
            className="btn-primary-sm"
          >
            <FolderPlus className="h-3 w-3" /> {copy.add}
          </button>
        ) : (
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={() => onOpen(r.filename)}
              className="btn-secondary-sm"
            >
              {copy.viewReport}
              <ArrowRight className="h-3 w-3" />
            </button>
            {isOwned && <ShareButton kind="social_report" refId={r.filename} compact />}
            {onDelete && isOwned && (
              <div className="relative">
                <button
                  onClick={() => setOpenMenu((cur) => (cur === r.filename ? null : r.filename))}
                  className="btn-icon"
                  aria-label={copy.moreActions}
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </button>
                {openMenu === r.filename && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                    <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-left shadow-lg">
                      <button
                        onClick={() => {
                          setOpenMenu(null);
                          onDelete(r.filename);
                        }}
                        className="menu-item-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {copy.deletePermanently}
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

  const renderTable = (data: SocialReportItem[], onImport?: (r: SocialReportItem) => void) => (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="w-full min-w-[600px] text-sm">
        <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-2.5">{copy.brandColumn}</th>
            <th className="px-4 py-2.5">{copy.reviewsColumn}</th>
            <th className="px-4 py-2.5">{copy.dateColumn}</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {data.map((r) => (
            renderRow(r, onImport ? () => onImport(r) : undefined)
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <Radio className="h-4 w-4 text-emerald-500" />
          {project
            ? `${copy.projectReports} ${project.name}`
            : copy.reportsHeading}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">{rows.length}</span>
        </h2>
        <button
          onClick={onNew}
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-ink-hover"
        >
          <Plus className="h-3.5 w-3.5" /> {copy.newAnalysis}
        </button>
      </div>

      {rows.length > 0 ? (
        renderTable(rows)
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">
          {project
            ? copy.emptyInProject
            : copy.emptyNoReports}
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
            {copy.importReport}
          </button>
          {importing &&
            (others.length > 0 ? (
              <div className="mt-2">
                {renderTable(others, doImport)}
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-slate-400">
                {copy.nothingToImport}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}
