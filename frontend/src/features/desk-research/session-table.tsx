import { useState } from "react";
import { deskCopy } from "./copy";
import { Plus, ChevronDown, FolderPlus, ArrowRight, FolderOpen, FileText, BarChart3, MoreVertical, Trash2, Users } from "lucide-react";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useProjectArtifactRefs } from "../../lib/use-project-artifacts";
import ShareButton from "../../components/ui/share-button";

export type DeskSessionItem = {
  id: string;
  session_id: string;
  name: string;
  createdAt: number;
  doc_count: number;
  has_report: boolean;
  owned?: boolean;
};

/**
 * The Desk Research dashboard: a clear table of research sessions, mirroring the other module
 * dashboards. Project-aware, with open / share / delete / import + a "New session" button.
 * A session's ref is its server session_id.
 */
export default function DeskSessionTable({
  sessions,
  onOpen,
  onNew,
  onDelete,
  isFrench,
}: {
  sessions: DeskSessionItem[];
  onOpen: (s: DeskSessionItem) => void;
  onNew: () => void;
  onDelete?: (s: DeskSessionItem) => void;
  isFrench: boolean;
}) {
  const copy = deskCopy(isFrench);
  const { project, attach } = useActiveProject();
  const { refs: projectRefs, markAttached } = useProjectArtifactRefs("desk_session");
  const [importing, setImporting] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const fmt = (ms: number) =>
    new Date(ms).toLocaleDateString(copy.dateLocale, { month: "short", day: "numeric", year: "numeric" });

  const inProject = sessions.filter((s) => projectRefs.has(s.session_id));
  const rows = project ? inProject : sessions;
  const others = sessions.filter((s) => !projectRefs.has(s.session_id));

  const doImport = async (s: DeskSessionItem) => {
    await attach("desk_session", s.session_id, "desk_research", s.name);
    markAttached(s.session_id);
  };

  // Render functions, not components. Declaring a component inside another creates a new
  // component type on every render, so React unmounts and remounts the whole table -- losing
  // focus, scroll position and anything else the subtree holds. Returning elements from a
  // plain function does not, because there is no new type for React to compare.
  const renderRow = (s: DeskSessionItem, onImport?: () => void) => {
    const isOwned = s.owned !== false;
    return (
    <tr key={s.session_id} className="border-t border-slate-100 transition hover:bg-slate-50/60">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-500">
            <FolderOpen className="h-3.5 w-3.5" />
          </span>
          <span className="font-semibold text-slate-800">{s.name}</span>
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
          <FileText className="h-3.5 w-3.5 text-slate-400" />
          {s.doc_count} {copy.documentsSuffix}
        </span>
      </td>
      <td className="px-4 py-3">
        {s.has_report ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700">
            <BarChart3 className="h-3 w-3" /> {copy.reportBadge}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-xs tabular-nums text-slate-400">{fmt(s.createdAt)}</td>
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
              onClick={() => onOpen(s)}
              className="btn-secondary-sm"
            >
              {copy.open}
              <ArrowRight className="h-3 w-3" />
            </button>
            {isOwned && <ShareButton kind="desk_session" refId={s.session_id} compact />}
            {onDelete && isOwned && (
              <div className="relative">
                <button
                  onClick={() => setOpenMenu((cur) => (cur === s.session_id ? null : s.session_id))}
                  className="btn-icon"
                  aria-label={copy.moreActions}
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </button>
                {openMenu === s.session_id && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                    <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-left shadow-lg">
                      <button
                        onClick={() => {
                          setOpenMenu(null);
                          onDelete(s);
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

  const renderTable = (data: DeskSessionItem[], onImport?: (s: DeskSessionItem) => void) => (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-2.5">{copy.sessionColumn}</th>
            <th className="px-4 py-2.5">{copy.documentsColumn}</th>
            <th className="px-4 py-2.5">{copy.reportBadge}</th>
            <th className="px-4 py-2.5">{copy.createdColumn}</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {data.map((s) => (
            renderRow(s, onImport ? () => onImport(s) : undefined)
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <FolderOpen className="h-4 w-4 text-indigo-500" />
          {project
            ? `${copy.projectSessions} ${project.name}`
            : copy.sessionsHeading}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">{rows.length}</span>
        </h2>
        <button
          onClick={onNew}
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-ink-hover"
        >
          <Plus className="h-3.5 w-3.5" /> {copy.newSession}
        </button>
      </div>

      {rows.length > 0 ? (
        renderTable(rows)
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">
          {project
            ? copy.emptyInProject
            : copy.emptyNoSessions}
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
            {copy.importSession}
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
