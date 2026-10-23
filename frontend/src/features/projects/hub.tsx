import { useEffect, useState } from "react";
import { isFrench, pickCopy } from "../../lib/i18n";
import { Home } from "lucide-react";

import ProjectPipeline, { type PipelineStepMeta } from "./pipeline";
import ProjectSidebar from "./sidebar";
import ServicesLanding from "./landing";
import { hubCards } from "./cards";
import { useProjectArtifacts } from "../../lib/use-project-artifacts";
import UserMenu from "../../components/ui/user-menu";
import {
  createProject,
  deleteProject as apiDeleteProject,
  listProjects,
  addProjectMember,
  removeProjectMember,
  detachArtifact,
  deleteAnalysis,
  PROJECT_STEP_KEYS,
  type Project,
  type ProjectArtifact,
  type AnalysisKind,
  type StepKey,
  type StepStatus,
} from "../../lib/projectsApi";
import { useActiveProject } from "../../context/ActiveProjectContext";


type ServicesHubProps = {
  language?: string;
  onBack: () => void;
  onOpenAssessment: () => void;
  onOpenInterviewHub: () => void;
  onOpenSocialScraping: () => void;
  onOpenDeskResearch: () => void;
  user?: { full_name: string; role: string } | null;
  onNavigate?: (path: string) => void;
  onLogout?: () => void;
};

const TRANSLATIONS = {
  fr: {
    brand: "CX Studio",
    back: "Accueil",
    eyebrow: "Suite CX EY",
    heading: "Votre pipeline CX",
    subtitle: "Cinq outils qui mènent une mission CX du diagnostic de maturité jusqu'au registre d'enjeux priorisé.",
    assessmentTitle: "Diagnostic de maturité",
    assessmentDesc: "Évaluez votre maturité CX sur les axes Piloter, Analyser et Améliorer.",
    assessmentCta: "Lancer le diagnostic",
    axisManage: "Piloter",
    axisAnalyze: "Analyser",
    axisImprove: "Améliorer",
    interviewTitle: "Guide d'entretien",
    interviewDesc: "Générez un guide d'entretien sur mesure selon le profil de votre interlocuteur.",
    interviewCta: "Ouvrir l'Interview Hub",
    sampleQuestion: "Racontez-moi la dernière fois où un retour client a changé une décision.",
    followUpTag: "Relance incluse",
    scrapingTitle: "Écoute sociale",
    scrapingDesc: "Récupérez les avis publics et obtenez sentiment, thèmes et plaintes par IA.",
    scrapingCta: "Ouvrir le Social Scraping",
    positive: "Positif",
    neutral: "Neutre",
    negative: "Négatif",
    deskResearchTitle: "Desk Research",
    deskResearchDesc: "Importez les documents client et obtenez une synthèse structurée par l'IA.",
    deskResearchCta: "Ouvrir le Desk Research",
    issueLogTitle: "Registre des enjeux",
    issueLogDesc: "Consolide les constats de chaque module en un registre d'enjeux priorisé — le fil qui relie tout le parcours.",
    issueLogCta: "Ouvrir le registre",
    issueLogPreviewCaption: "Relier les constats aux enjeux priorisés",
    comingSoon: "Bientôt disponible",
    soon: "Bientôt",
    stepLabel: "Étape",
    pipelineNote: "Suivez-les dans l'ordre, ou ouvrez celui qu'il vous faut.",
  },
  en: {
    brand: "CX Studio",
    back: "Home",
    eyebrow: "EY CX Suite",
    heading: "Your CX Pipeline",
    subtitle: "Five tools that take a CX engagement from the maturity assessment through to a prioritized issue log.",
    assessmentTitle: "Maturity Assessment",
    assessmentDesc: "Score your CX maturity across Manage, Analyze, and Improve dimensions.",
    assessmentCta: "Start the assessment",
    axisManage: "Manage",
    axisAnalyze: "Analyze",
    axisImprove: "Improve",
    interviewTitle: "Interview Guide",
    interviewDesc: "Generate a tailored interview guide for your next stakeholder conversation.",
    interviewCta: "Open Interview Hub",
    sampleQuestion: "Tell me about the last time customer feedback actually changed a decision.",
    followUpTag: "Follow-up included",
    scrapingTitle: "Social Listening",
    scrapingDesc: "Pull public reviews and get AI-classified sentiment, themes, and complaints.",
    scrapingCta: "Open Social Scraping",
    positive: "Positive",
    neutral: "Neutral",
    negative: "Negative",
    deskResearchTitle: "Desk Research",
    deskResearchDesc: "Upload client documents and get an AI-structured synthesis with citations.",
    deskResearchCta: "Open Desk Research",
    issueLogTitle: "Issue Log",
    issueLogDesc: "Consolidates every module's findings into one prioritized issue log — the thread that connects the whole journey.",
    issueLogCta: "Open the Issue Log",
    issueLogPreviewCaption: "Connect findings → prioritized issues",
    comingSoon: "Coming soon",
    soon: "Soon",
    stepLabel: "Step",
    pipelineNote: "Run them in order, or open whichever one you need.",
  },
};

/* ---- small arrow connector between pipeline cards ---- */



export default function ServicesHub({
  language = "en",
  onBack,
  onOpenAssessment,
  onOpenInterviewHub,
  onOpenSocialScraping,
  onOpenDeskResearch,
  user,
  onNavigate,
  onLogout,
}: ServicesHubProps) {
  const t = pickCopy(TRANSLATIONS, language);
  const french = isFrench(language);
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;

  const CARDS = hubCards(t, {
    onOpenAssessment, onOpenInterviewHub, onOpenSocialScraping, onOpenDeskResearch, onNavigate,
  });

  // ── Projects: a tracked pipeline over the modules ──────────────────────────
  const [projects, setProjects] = useState<Project[]>([]);
  // The ACTIVE project lives in app-level context so it survives launching a module.
  const {
    project: activeProject,
    open: openActive,
    exit: exitActive,
    setStepStatus,
    refresh: refreshActive,
  } = useActiveProject();

  // Map each pipeline step to the module launcher it opens (modules stay untouched).
  const stepAction: Record<StepKey, () => void> = {
    assessment: onOpenAssessment,
    interview: onOpenInterviewHub,
    desk_research: onOpenDeskResearch,
    social: onOpenSocialScraping,
    issue_log: () => onNavigate?.("/issue-log"),
  };

  // Reuse the module cards' visuals for the pipeline steps, in engagement order.
  const cardByAction = new Map(CARDS.map((c) => [c.onClick, c]));
  const realSteps: PipelineStepMeta[] = (
    [
      { key: "assessment" as StepKey, action: onOpenAssessment },
      { key: "interview" as StepKey, action: onOpenInterviewHub },
      { key: "social" as StepKey, action: onOpenSocialScraping },
      { key: "desk_research" as StepKey, action: onOpenDeskResearch },
    ]
  ).map((s, idx) => {
    const c = cardByAction.get(s.action)!;
    return { key: s.key, step: idx + 1, title: c.title, desc: c.desc, icon: c.icon, iconBg: c.iconBg, iconColor: c.iconColor };
  });
  // The Issue Log is the consolidation capstone (step 5) — an openable step that navigates
  // to the module (it doesn't attach a per-step artifact, but it tracks status like the rest).
  const issueCard = CARDS.find((c) => c.step === 5);
  const pipelineSteps: PipelineStepMeta[] = issueCard
    ? [
        ...realSteps,
        {
          key: "issue_log",
          step: realSteps.length + 1,
          title: issueCard.title,
          desc: issueCard.desc,
          icon: issueCard.icon,
          iconBg: issueCard.iconBg,
          iconColor: issueCard.iconColor,
        },
      ]
    : realSteps;

  const reloadProjects = () => listProjects().then(setProjects).catch(() => setProjects([]));

  // Load the projects list for the sidebar (the ACTIVE project is restored by its context).
  useEffect(() => {
    reloadProjects();
  }, []);

  // Results attached to the active project (shown under each pipeline step).
  const { artifacts, reload: reloadArtifacts } = useProjectArtifacts();

  const openProject = (p: Project) => openActive(p);
  const exitProject = () => {
    exitActive();
    reloadProjects();
  };
  const handleCreateProject = async (name: string, company: string) => {
    const p = await createProject({ name, company_name: company || undefined });
    setProjects((prev) => [p, ...prev]);
    openActive(p);
  };
  const handleSetStatus = (key: StepKey, status: StepStatus) => setStepStatus(key, status);
  const handleOpenStep = (key: StepKey) => {
    // Opening a not-started step nudges it to "in progress", then launches the module.
    if (activeProject && (activeProject.steps[key] ?? "todo") === "todo") {
      setStepStatus(key, "in_progress");
    }
    stepAction[key]?.();
  };
  const handleDeleteProject = async () => {
    if (!activeProject) return;
    await apiDeleteProject(activeProject.id);
    exitProject();
  };

  // Re-fetch the active project (via context) + refresh the sidebar list.
  const refreshActiveProject = async () => {
    await refreshActive();
    reloadProjects();
  };

  const handleAddMember = async (email: string) => {
    if (!activeProject) return;
    // Errors (e.g. "user not found") propagate to the panel to display.
    await addProjectMember(activeProject.id, email);
    await refreshActiveProject();
  };

  const handleRemoveMember = async (userId: number) => {
    if (!activeProject) return;
    await removeProjectMember(activeProject.id, userId);
    await refreshActiveProject();
  };

  const handleDetachArtifact = async (artifactId: number) => {
    if (!activeProject) return;
    await detachArtifact(activeProject.id, artifactId);
    reloadArtifacts();
  };
  const handleDeleteArtifact = async (a: ProjectArtifact) => {
    const label = a.title || a.kind;
    const msg =
      language === "fr"
        ? `Supprimer « ${label} » définitivement ? L'analyse sera aussi retirée des outils.`
        : `Delete “${label}” permanently? This also removes the analysis from the tools.`;
    if (!window.confirm(msg)) return;
    try {
      await deleteAnalysis(a.kind as AnalysisKind, a.ref_id);
    } catch {
      window.alert(
        language === "fr"
          ? "Suppression impossible — vous ne pouvez supprimer que vos propres analyses. Utilisez « Retirer du projet »."
          : "Couldn't delete — you can only permanently delete analyses you own. Use “Remove from project” instead.",
      );
      return;
    }
    reloadArtifacts();
  };

  return (
    <div className="relative min-h-screen overflow-x-clip bg-[#f6f7fb] text-ink">
      {/* Shared full-width top header (spans the whole width; the rail sits below it) */}
      {/* Solid, not translucent: the landing's navy half scrolls underneath, and an 85%-white bar
          tinted grey-blue on the left while staying white on the right -- a header that changed
          colour as you scrolled. It is the same bar on every page (chrome, not content), separated
          from the split below by its own border and shadow. */}
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-5 shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
        <div className="flex items-center gap-3">
          <img src={logoSrc} alt="EY" className="h-7 w-auto" />
          <span className="h-4 w-px bg-slate-200" />
          <span className="text-sm font-medium text-slate-500">{t.brand}</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="btn-secondary"
          >
            <Home className="h-3.5 w-3.5" aria-hidden="true" />
            {t.back}
          </button>
          {user && onNavigate && onLogout && (
            <UserMenu fullName={user.full_name} role={user.role} onNavigate={onNavigate} onLogout={onLogout} />
          )}
        </div>
      </header>

      {/* Hover-expand project rail (PM-style), overlays the page so content never reflows.
          Only while a project is open: on the landing the split panel already lists projects,
          and two navigations for the same thing is one too many. */}
      {activeProject && (
        <ProjectSidebar
          projects={projects}
          activeId={activeProject?.id ?? null}
          stepKeys={PROJECT_STEP_KEYS}
          isFrench={french}
          onSelect={openProject}
          onCreate={handleCreateProject}
          onHome={exitProject}
        />
      )}

      <div className={activeProject ? "pl-16" : ""}>
        {activeProject ? (
          <ProjectPipeline
            project={activeProject}
            steps={pipelineSteps}
            artifacts={artifacts}
            isFrench={french}
            onOpenStep={handleOpenStep}
            onSetStatus={handleSetStatus}
            onDelete={handleDeleteProject}
            onAddMember={handleAddMember}
            onRemoveMember={handleRemoveMember}
            onDetachArtifact={handleDetachArtifact}
            onDeleteArtifact={handleDeleteArtifact}
          />
        ) : (
          <ServicesLanding
            projects={projects}
            stepKeys={PROJECT_STEP_KEYS}
            language={language}
            onOpenProject={openProject}
            onCreateProject={handleCreateProject}
            tools={CARDS.map((c) => ({
              step: c.step,
              title: c.title,
              desc: c.desc,
              icon: c.icon,
              iconBg: c.iconBg,
              iconColor: c.iconColor,
              onClick: c.onClick,
              comingSoon: c.comingSoon,
            }))}
          />
        )}
      </div>
    </div>
  );
}
