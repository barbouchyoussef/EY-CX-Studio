import { useState } from "react";
import { assessmentCopy } from "./copy";
import { Plus, ChevronDown, FolderPlus, ArrowRight, ClipboardList, MoreVertical, Trash2, Send, Users } from "lucide-react";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useProjectArtifactRefs } from "../../lib/use-project-artifacts";
import ShareButton from "../../components/ui/share-button";

export type AssessmentItem = {
  id: number;
  company_name: string;
  sector?: string;
  size?: string;
  region?: string | null;
  status: string;
  overall_maturity_band?: string | null;
  updated_at: string;
  current_axis?: string | null;
  recipient_status?: string | null; // client-link status: sent | opened | completed
  recipient_name?: string | null; // who the link was sent to
  recipient_role?: string | null;
  owned?: boolean; // false when the row was shared with the caller (not their own)
};

/** Status → label + colour. Room is left for the client-link statuses that Step 5 will add
 *  (e.g. a link was sent but the client hasn't finished). */
function statusMeta(status: string, isFrench: boolean): { label: string; cls: string } {
  const copy = assessmentCopy(isFrench);
  switch (status) {
    case "completed":
      return { label: copy.statusCompleted, cls: "bg-emerald-50 text-emerald-700" };
    case "active":
      return { label: copy.statusInProgress, cls: "bg-amber-50 text-amber-700" };
    case "sent":
    case "awaiting_client":
      return { label: copy.statusLinkSent, cls: "bg-blue-50 text-blue-700" };
    case "opened":
      return { label: copy.statusOpened, cls: "bg-indigo-50 text-indigo-700" };
    default:
      return { label: status, cls: "bg-slate-100 text-slate-500" };
  }
}

/** Choose the badge: a live client-link status wins over a plain "active"/"pending" assessment
 *  status, but a genuinely completed assessment always shows as completed. */
function displayStatus(a: AssessmentItem): string {
  if (a.status === "completed") return "completed";
  if (a.recipient_status && a.recipient_status !== "revoked") return a.recipient_status;
  return a.status;
}

/**
 * A clear, detailed table of assessment conversations. Project-aware: standalone it lists all
 * your assessments; inside a project it lists the project's assessments plus an "import" picker.
 */
export default function AssessmentHistoryTable({
  assessments,
  onOpen,
  onNew,
  onDelete,
  isFrench,
}: {
  assessments: AssessmentItem[];
  onOpen: (id: number, status: string) => void;
  onNew: () => void;
  onDelete?: (a: AssessmentItem) => void;
  isFrench: boolean;
}) {
  const copy = assessmentCopy(isFrench);
  const { project, attach } = useActiveProject();
  const { refs: projectRefs, markAttached } = useProjectArtifactRefs("assessment");
  const [importing, setImporting] = useState(false);
  const [openMenu, setOpenMenu] = useState<number | null>(null);

  const fmt = (d: string) =>
    new Date(d).toLocaleDateString(copy.dateLocale, { month: "short", day: "numeric", year: "numeric" });

  const inProject = assessments.filter((a) => projectRefs.has(String(a.id)));
  const rows = project ? inProject : assessments;
  const others = assessments.filter((a) => !projectRefs.has(String(a.id)));

  const doImport = async (a: AssessmentItem) => {
    await attach("assessment", String(a.id), "assessment", a.company_name);
    markAttached(String(a.id));
  };

  // Render functions, not components. Declaring a component inside another creates a new
  // component type on every render, so React unmounts and remounts the whole table -- losing
  // focus, scroll position and anything else the subtree holds. Returning elements from a
  // plain function does not, because there is no new type for React to compare.
  const renderRow = (a: AssessmentItem, onImport?: () => void) => {
    const s = statusMeta(displayStatus(a), isFrench);
    // A client-link assessment that the client hasn't finished: the consultant can't "resume" it.
    const awaitingClient = Boolean(a.recipient_status) && a.status !== "completed";
    const isOwned = a.owned !== false; // default true for legacy payloads
    return (
      <tr key={a.id} className="border-t border-slate-100 transition hover:bg-slate-50/60">
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-800">{a.company_name}</span>
            {!isOwned && (
              <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-sky-600">
                <Users className="h-3 w-3" />
                {copy.sharedWithYou}
              </span>
            )}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-400">
            {[a.sector, a.size, a.region].filter(Boolean).join(" · ") || "—"}
          </div>
          {a.recipient_name && (
            <div className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-violet-600">
              <Send className="h-3 w-3" />
              {copy.sentTo} {a.recipient_name}
              {a.recipient_role ? ` · ${a.recipient_role}` : ""}
            </div>
          )}
        </td>
        <td className="px-4 py-3">
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${s.cls}`}>{s.label}</span>
        </td>
        <td className="px-4 py-3 text-sm text-slate-600">
          {a.overall_maturity_band || <span className="text-slate-300">—</span>}
        </td>
        <td className="px-4 py-3 text-xs tabular-nums text-slate-400">{fmt(a.updated_at)}</td>
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
              {a.status === "completed" ? (
                <button
                  onClick={() => onOpen(a.id, a.status)}
                  className="btn-secondary-sm"
                >
                  {copy.viewReport}
                  <ArrowRight className="h-3 w-3" />
                </button>
              ) : awaitingClient ? (
                <span className="text-[11px] font-medium italic text-slate-400">
                  {copy.awaitingClient}
                </span>
              ) : (
                <button
                  onClick={() => onOpen(a.id, a.status)}
                  className="btn-secondary-sm"
                >
                  {copy.resume}
                  <ArrowRight className="h-3 w-3" />
                </button>
              )}
              {/* Share is done here, from the dashboard — only for assessments you own. */}
              {isOwned && <ShareButton kind="assessment" refId={String(a.id)} compact />}
              {onDelete && isOwned && (
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu((cur) => (cur === a.id ? null : a.id))}
                    className="btn-icon"
                    aria-label={copy.moreActions}
                  >
                    <MoreVertical className="h-3.5 w-3.5" />
                  </button>
                  {openMenu === a.id && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                      <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-left shadow-lg">
                        <button
                          onClick={() => {
                            setOpenMenu(null);
                            onDelete(a);
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

  const renderTable = (data: AssessmentItem[], onImport?: (a: AssessmentItem) => void) => (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="w-full min-w-[560px] text-sm">
        <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-2.5">{copy.companyColumn}</th>
            <th className="px-4 py-2.5">{copy.statusColumn}</th>
            <th className="px-4 py-2.5">{copy.maturityColumn}</th>
            <th className="px-4 py-2.5">{copy.updatedColumn}</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {data.map((a) => (
            renderRow(a, onImport ? () => onImport(a) : undefined)
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <ClipboardList className="h-4 w-4 text-violet-500" />
          {project
            ? `${copy.projectAssessments} ${project.name}`
            : copy.assessmentsHeading}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
            {rows.length}
          </span>
        </h2>
        <button
          onClick={onNew}
          className="inline-flex items-center gap-1.5 rounded-full bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-violet-700"
        >
          <Plus className="h-3.5 w-3.5" /> {copy.newAssessment}
        </button>
      </div>

      {rows.length > 0 ? (
        renderTable(rows)
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">
          {project
            ? copy.emptyInProject
            : copy.emptyNoAssessments}
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
            {copy.importAssessment}
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
