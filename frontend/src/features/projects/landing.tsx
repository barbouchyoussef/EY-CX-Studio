import { useMemo, useState, type ReactNode } from "react";
import { BRAND } from "../../lib/brand";
import { pickCopy } from "../../lib/i18n";
import { ArrowRight, FolderKanban, Plus, Search, X } from "lucide-react";
import type { Project, StepKey } from "../../lib/projectsApi";

/** One tool on the right-hand side. */
export type ToolEntry = {
  step: number;
  title: string;
  desc: string;
  icon: ReactNode;
  iconBg: string;
  iconColor: string;
  onClick?: () => void;
  comingSoon?: boolean;
};

type Props = {
  projects: Project[];
  stepKeys: readonly StepKey[];
  tools: ToolEntry[];
  language?: string;
  onOpenProject: (p: Project) => void;
  onCreateProject: (name: string, company: string) => Promise<void> | void;
};

const COPY = {
  en: {
    projectsKicker: "Run an engagement",
    projectsTitle: "Work in a project",
    projectsLead:
      "One client, one place. Every assessment, interview, report and issue log stays together, shared with the people on the engagement.",
    newProject: "New project",
    noProjects: "No projects yet.",
    noProjectsHint: "Create one to keep an engagement's work together.",
    search: "Search projects…",
    done: "done",
    toolsKicker: "Or work ad hoc",
    toolsTitle: "Open a tool directly",
    toolsLead:
      "Every tool runs on its own. Use one for a quick piece of work and attach the result to a project later.",
    create: "Create project",
    cancel: "Cancel",
    nameLabel: "Project name",
    namePlaceholder: "e.g. Acme CX diagnostic",
    companyLabel: "Client",
    companyPlaceholder: "e.g. Acme",
    noMatch: "No project matches that.",
    soon: "Soon",
  },
  fr: {
    projectsKicker: "Mener une mission",
    projectsTitle: "Travailler dans un projet",
    projectsLead:
      "Un client, un seul endroit. Diagnostics, entretiens, rapports et registre d'enjeux restent ensemble, partagés avec l'équipe de la mission.",
    newProject: "Nouveau projet",
    noProjects: "Aucun projet.",
    noProjectsHint: "Créez-en un pour regrouper le travail d'une mission.",
    search: "Rechercher un projet…",
    done: "terminées",
    toolsKicker: "Ou au cas par cas",
    toolsTitle: "Ouvrir un outil",
    toolsLead:
      "Chaque outil fonctionne seul. Utilisez-en un pour un travail rapide et rattachez le résultat à un projet plus tard.",
    create: "Créer le projet",
    cancel: "Annuler",
    nameLabel: "Nom du projet",
    namePlaceholder: "ex. Diagnostic CX Acme",
    companyLabel: "Client",
    companyPlaceholder: "ex. Acme",
    noMatch: "Aucun projet ne correspond.",
    soon: "Bientôt",
  },
};

/**
 * The services landing: two ways in, side by side.
 *
 * The two panels carry different surfaces on purpose. A hairline divider was not enough to say
 * "these are two different choices" -- the eye read one long row of cards. Projects sit on the
 * app's navy, tools on the page's own light ground, so the split is legible before a word is
 * read. Both colours are already the product's (#1A1F36 primary, #F6D200 accent); nothing new
 * is introduced.
 */
export default function ServicesLanding({
  projects, stepKeys, tools, language, onOpenProject, onCreateProject,
}: Props) {
  const t = pickCopy(COPY, language);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) =>
      p.name.toLowerCase().includes(q) || (p.company_name ?? "").toLowerCase().includes(q));
  }, [projects, query]);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onCreateProject(name.trim(), company.trim());
      setName(""); setCompany(""); setCreating(false);
    } finally {
      setBusy(false);
    }
  };

  const doneCount = (p: Project) => stepKeys.filter((k) => p.steps[k] === "done").length;

  return (
    <div className="grid min-h-[calc(100vh-4rem)] items-stretch lg:grid-cols-2">

      {/* ══════════════════ projects — the anchored path, on navy ══════════════════ */}
      <section className="relative flex justify-center overflow-hidden bg-ey-navy px-6 pb-14 pt-12 sm:px-10 lg:pt-20">
        {/* one soft gold bloom so the half does not read as a flat block */}
        <div
          aria-hidden
          className="pointer-events-none absolute -left-32 -top-24 h-[26rem] w-[26rem] rounded-full opacity-[0.18] blur-3xl"
          style={{ background: BRAND.yellow }}
        />

        <div className="relative w-full max-w-[560px]">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-ey-yellow">
              {t.projectsKicker}
            </p>
            <h2 className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-white">
              {t.projectsTitle}
            </h2>
            <p className="mt-2 max-w-md text-[13.5px] leading-relaxed text-white/75">
              {t.projectsLead}
            </p>

            {creating ? (
              <div className="mt-6 rounded-2xl border border-white/15 bg-white/[0.06] p-5 backdrop-blur-sm">
                <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-white/65">
                  {t.nameLabel}
                </label>
                <input
                  autoFocus value={name} onChange={(e) => setName(e.target.value)}
                  placeholder={t.namePlaceholder}
                  onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
                  className="mb-3 w-full rounded-lg border border-white/15 bg-white/10 px-3 py-2 text-sm text-white placeholder-white/45 outline-none focus:border-ey-yellow/60"
                />
                <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-white/65">
                  {t.companyLabel}
                </label>
                <input
                  value={company} onChange={(e) => setCompany(e.target.value)}
                  placeholder={t.companyPlaceholder}
                  onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
                  className="mb-4 w-full rounded-lg border border-white/15 bg-white/10 px-3 py-2 text-sm text-white placeholder-white/45 outline-none focus:border-ey-yellow/60"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={submit} disabled={busy || !name.trim()}
                    className="rounded-full bg-ey-yellow px-4 py-2 text-xs font-bold text-ey-navy transition hover:bg-[#ffe23d] disabled:opacity-40"
                  >
                    {t.create}
                  </button>
                  <button
                    onClick={() => { setCreating(false); setName(""); setCompany(""); }}
                    className="inline-flex items-center gap-1 rounded-full border border-white/20 px-3 py-2 text-xs font-semibold text-white/80 transition hover:border-white/50 hover:text-white"
                  >
                    <X className="h-3.5 w-3.5" /> {t.cancel}
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                className="mt-6 flex w-full items-center gap-3 rounded-2xl border border-dashed border-white/25 bg-white/[0.04] px-5 py-4 text-left transition hover:border-ey-yellow/60 hover:bg-white/[0.08]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ey-yellow text-ey-navy">
                  <Plus className="h-5 w-5" strokeWidth={2.5} />
                </span>
                <span className="text-sm font-bold text-white">{t.newProject}</span>
              </button>
            )}

            {projects.length > 4 && (
              <div className="relative mt-4">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/55" />
                <input
                  value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search}
                  className="w-full rounded-lg border border-white/15 bg-white/[0.06] py-2 pl-9 pr-3 text-sm text-white placeholder-white/45 outline-none focus:border-white/35"
                />
              </div>
            )}

            {projects.length === 0 ? (
              <div className="mt-5 rounded-2xl border border-white/10 px-5 py-8 text-center">
                <p className="text-sm font-semibold text-white/85">{t.noProjects}</p>
                <p className="mt-1 text-xs text-white/55">{t.noProjectsHint}</p>
              </div>
            ) : visible.length === 0 ? (
              <p className="mt-5 py-6 text-center text-sm text-white/55">{t.noMatch}</p>
            ) : (
              <ul className="mt-5 space-y-2">
                {visible.map((p) => {
                  const done = doneCount(p);
                  const complete = done === stepKeys.length;
                  return (
                    <li key={p.id}>
                      <button
                        onClick={() => onOpenProject(p)}
                        className="group flex w-full items-center gap-3 rounded-2xl border border-white/15 bg-white/[0.08] px-4 py-3.5 text-left transition hover:border-ey-yellow/50 hover:bg-white/[0.14]"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ey-yellow/20 text-ey-yellow">
                          <FolderKanban className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-bold text-white">{p.name}</span>
                          <span className="block truncate text-xs text-white/60">
                            {p.company_name ? `${p.company_name} · ` : ""}
                            {done}/{stepKeys.length} {t.done}
                          </span>
                        </span>
                        <span className="hidden h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-white/15 sm:block">
                          <span
                            className={`block h-full rounded-full ${complete ? "bg-emerald-400" : "bg-ey-yellow"}`}
                            style={{ width: `${(done / stepKeys.length) * 100}%` }}
                          />
                        </span>
                        <ArrowRight className="h-4 w-4 shrink-0 text-white/40 transition group-hover:translate-x-0.5 group-hover:text-ey-yellow" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

      {/* ══════════════════ tools — the light, à-la-carte path ══════════════════ */}
      <section className="flex justify-center bg-white px-6 pb-14 pt-12 sm:px-10 lg:pt-20">
        <div className="w-full max-w-[560px]">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
            {t.toolsKicker}
          </p>
          <h2 className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-slate-900">
            {t.toolsTitle}
          </h2>
          <p className="mt-2 max-w-lg text-[13.5px] leading-relaxed text-slate-500">{t.toolsLead}</p>

          <ul className="mt-6 grid gap-2.5">
            {tools.map((tool) => (
              <li key={tool.step}>
                <button
                  type="button"
                  onClick={tool.onClick}
                  disabled={tool.comingSoon}
                  className={`group flex h-full w-full items-start gap-3 rounded-2xl border px-4 py-4 text-left transition ${
                    tool.comingSoon
                      ? "cursor-default border-dashed border-slate-200 bg-slate-50/70"
                      : "border-slate-200 bg-white hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
                  }`}
                >
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tool.iconBg} ${tool.iconColor}`}>
                    {tool.icon}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-bold text-slate-900">{tool.title}</span>
                      {tool.comingSoon ? (
                        <span className="shrink-0 rounded-full bg-ey-yellow/25 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-ey-gold-deep">
                          {t.soon}
                        </span>
                      ) : (
                        <span className="shrink-0 font-mono text-[10px] font-bold text-slate-300">
                          {tool.step}
                        </span>
                      )}
                    </span>
                    <span className="mt-1 block text-[12.5px] leading-relaxed text-slate-500">
                      {tool.desc}
                    </span>
                  </span>
                  {!tool.comingSoon && (
                    <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-700" />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
