/**
 * The four kinds of analysis the platform produces, and what to call them.
 *
 * Shared because they are a domain concept: a project attaches them, the issue log consolidates
 * them, sharing grants access to them.
 *
 * Two lengths, and the difference matters: a step-nav chip has room for "Assessment", a row
 * listing what a project holds says "Maturity assessment".
 */

/** The analysis kinds, as they are stored — these match `AnalysisKind` in projectsApi. */
export type AnalysisKindName = "assessment" | "interview_guide" | "desk_session" | "social_report";

/** The pipeline steps a project moves through. A step is not quite a kind: the issue log is a
 *  step that consumes the others rather than producing an analysis of its own. */
export type StepName = "assessment" | "interview" | "desk_research" | "social" | "issue_log";

type Bilingual = { en: string; fr: string };

/** Short for a chip or a tab; long for a row that has to say what the thing is. */
type KindLabels = { short: Bilingual; long: Bilingual };

export const ANALYSIS_KIND_LABELS: Record<AnalysisKindName, KindLabels> = {
  assessment: {
    short: { en: "Assessment", fr: "Évaluation" },
    long: { en: "Maturity assessment", fr: "Évaluation de maturité" },
  },
  interview_guide: {
    short: { en: "Interview", fr: "Entretien" },
    long: { en: "Interview guide", fr: "Guide d'entretien" },
  },
  desk_session: {
    short: { en: "Desk research", fr: "Recherche documentaire" },
    long: { en: "Desk research", fr: "Recherche documentaire" },
  },
  social_report: {
    short: { en: "Social", fr: "Social" },
    long: { en: "Social report", fr: "Rapport social" },
  },
};

export const STEP_LABELS: Record<StepName, Bilingual> = {
  assessment: ANALYSIS_KIND_LABELS.assessment.short,
  interview: ANALYSIS_KIND_LABELS.interview_guide.short,
  desk_research: ANALYSIS_KIND_LABELS.desk_session.short,
  social: ANALYSIS_KIND_LABELS.social_report.short,
  issue_log: { en: "Issue Log", fr: "Registre des enjeux" },
};

/** What to call a kind. Falls back to the raw stored value, so an unknown kind is visible as
 *  itself rather than blank -- if a new kind ships without a label, that should be obvious. */
export function analysisKindLabel(
  kind: string,
  french: boolean,
  length: "short" | "long" = "long",
): string {
  const entry = ANALYSIS_KIND_LABELS[kind as AnalysisKindName];
  if (!entry) return kind;
  return french ? entry[length].fr : entry[length].en;
}

/** What to call a pipeline step. */
export function stepLabel(step: string, french: boolean): string {
  const entry = STEP_LABELS[step as StepName];
  if (!entry) return step;
  return french ? entry.fr : entry.en;
}
