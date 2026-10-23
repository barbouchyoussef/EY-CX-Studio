import { useState } from "react";
import { projectCopy } from "./copy";
import { BRAND } from "../../lib/brand";
import { FolderKanban, LayoutGrid, Plus, Check, X } from "lucide-react";
import type { Project } from "../../lib/projectsApi";

type Props = {
  projects: Project[];
  activeId: number | null;
  stepKeys: readonly string[];
  isFrench: boolean;
  onSelect: (p: Project) => void;
  onCreate: (name: string, company: string) => void | Promise<void>;
  onHome: () => void;
};

const ACCENTS = [BRAND.gold, BRAND.blue, "#10b981", "#eb6834", "#7C3AED", "#0ea5e9"];
const accentFor = (id: number | string) =>
  ACCENTS[[...String(id)].reduce((a, c) => a + c.charCodeAt(0), 0) % ACCENTS.length];
const initials = (name: string) =>
  name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "P";

/** Hover-expand project rail (PM-style): a slim icon rail that slides open to a full projects
 *  panel on hover/focus, overlaying the page so content never reflows. Light theme; sits BELOW
 *  the top header (top-16), never covering it. */
export default function ProjectSidebar({
  projects,
  activeId,
  stepKeys,
  isFrench,
  onSelect,
  onCreate,
  onHome,
}: Props) {
  const copy = projectCopy(isFrench);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");

  const submit = async () => {
    if (!name.trim()) return;
    await onCreate(name.trim(), company.trim());
    setName("");
    setCompany("");
    setCreating(false);
  };

  const label = "whitespace-nowrap opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100";

  return (
    <aside className="group fixed bottom-0 left-0 top-16 z-30 flex w-16 flex-col overflow-hidden border-r border-slate-200 bg-white shadow-[2px_0_12px_-6px_rgba(15,23,42,0.15)] transition-[width] duration-300 ease-out hover:w-72 focus-within:w-72">
      {/* Section label */}
      <div className="flex h-12 shrink-0 items-center gap-3 px-[18px] text-slate-500">
        <FolderKanban className="h-5 w-5 shrink-0 text-ey-gold" />
        <span className={`text-[11px] font-bold uppercase tracking-wider ${label}`}>
          {copy.projectsHeading}
        </span>
      </div>

      {/* Actions */}
      <div className="px-2.5">
        <button
          type="button"
          onClick={onHome}
          className={`flex w-full items-center gap-3 rounded-lg px-[9px] py-2 text-sm transition ${
            activeId === null ? "bg-ey-gold/10 text-slate-900" : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          }`}
        >
          <LayoutGrid className="h-5 w-5 shrink-0" />
          <span className={`font-medium ${label}`}>{copy.allTools}</span>
        </button>
        <button
          type="button"
          onClick={() => setCreating((c) => !c)}
          className="mt-1 flex w-full items-center gap-3 rounded-lg px-[9px] py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        >
          <Plus className="h-5 w-5 shrink-0" />
          <span className={`font-medium ${label}`}>{copy.newProject}</span>
        </button>
      </div>

      {/* Create form (only meaningful when expanded) */}
      {creating && (
        <div className="mx-2.5 mt-2 hidden rounded-lg border border-slate-200 bg-slate-50 p-2.5 group-hover:block group-focus-within:block">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder={copy.projectNamePlaceholder}
            className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/20"
          />
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder={copy.companyPlaceholder}
            className="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/20"
          />
          <div className="mt-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={submit}
              disabled={!name.trim()}
              className="flex flex-1 items-center justify-center gap-1 rounded-md bg-ey-navy px-2 py-1.5 text-[12px] font-semibold text-white transition hover:bg-ey-navy-hover disabled:opacity-40"
            >
              <Check className="h-3.5 w-3.5" /> {copy.create}
            </button>
            <button
              type="button"
              onClick={() => { setCreating(false); setName(""); setCompany(""); }}
              className="flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-slate-200"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      <div className="mx-3 my-2 h-px bg-slate-100" />

      {/* Project list */}
      <div className="flex-1 overflow-y-auto px-2.5 pb-2">
        {projects.length === 0 ? (
          <p className={`px-2 py-2 text-[11px] leading-relaxed text-slate-400 ${label}`}>
            {copy.emptyNoProjects}
          </p>
        ) : (
          projects.map((p) => {
            const done = stepKeys.filter((k) => p.steps[k] === "done").length;
            const active = p.id === activeId;
            const accent = accentFor(p.id);
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelect(p)}
                className={`mb-0.5 flex w-full items-center gap-3 rounded-lg px-[7px] py-2 text-left transition ${
                  active ? "bg-ey-gold/10" : "hover:bg-slate-100"
                }`}
              >
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold text-white"
                  style={{ background: accent }}
                >
                  {initials(p.name)}
                </span>
                <span className={`min-w-0 flex-1 ${label}`}>
                  <span className={`block truncate text-[13px] font-medium ${active ? "text-slate-900" : "text-slate-700"}`}>
                    {p.name}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1">
                    {stepKeys.map((k) => (
                      <span
                        key={k}
                        className={`h-1.5 w-1.5 rounded-full ${
                          p.steps[k] === "done" ? "bg-emerald-500" : p.steps[k] === "in_progress" ? "bg-amber-400" : "bg-slate-200"
                        }`}
                      />
                    ))}
                    <span className="ml-1 text-[10px] tabular-nums text-slate-400">{done}/{stepKeys.length}</span>
                  </span>
                </span>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
