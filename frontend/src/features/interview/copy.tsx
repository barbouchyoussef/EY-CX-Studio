/**
 * Every word the interview hub puts on screen, in both languages.
 *
 * Pulled out of the component because it is copy, not behaviour: three separate screens read from
 * these tables, and rewording a persona or fixing a translation should not mean opening a
 * 1,600-line React file. Both are functions of the language rather than constants, because the
 * guide's language is chosen per interview and can change while the hub is open.
 */

import { MessageSquareText, Settings2, Target, TrendingUp, Users } from "lucide-react";
import { dashboardCopy } from "../../lib/dashboard-copy";

export type InterviewLabels = ReturnType<typeof interviewLabels>;

export function interviewLabels(isFrench: boolean) {
  return {
    ...dashboardCopy(isFrench),
  title: "Client Interview Hub",
  subtitle: isFrench ? "Générateur intelligent de guides d'entretiens sémantiques" : "Semantic AI Interview Guide Generator",
  back: isFrench ? "Retour" : "Back",
  print: isFrench ? "Imprimer (PDF)" : "Print (PDF)",
  exportExcel: isFrench ? "Exporter Excel" : "Export Excel",
  answerPlaceholder: isFrench ? "Notes de l'entretien — réponse du client, observations, verbatims..." : "Interview notes — client answer, observations, verbatims...",
  noteLabel: isFrench ? "Notes / Réponse" : "Notes / Answer",
  savedLabel: isFrench ? "Sauvegardé" : "Saved",
  loadSaved: isFrench ? "Charger la dernière session" : "Load last session",
  generate: isFrench ? "Générer le Guide d'Entretien" : "Generate Interview Guide",
  setupTitle: isFrench ? "Paramètres de l'Entretien" : "Interview Configuration",
  sourceLabel: isFrench ? "Source de données" : "Data Source",
  scratchOption: isFrench ? "Démarrer de zéro (Sans historique)" : "Start from Scratch (No history)",
  companyLabel: isFrench ? "Entreprise" : "Company",
  sectorLabel: isFrench ? "Secteur" : "Sector",
  sizeLabel: isFrench ? "Taille" : "Size",
  regionLabel: isFrench ? "Région" : "Region",
  profileLabel: isFrench ? "Profil de l'interlocuteur" : "Target Stakeholder Persona",
  contextLabel: isFrench ? "Remarques & éléments à inclure" : "Remarks & Elements to Include",
  contextPlaceholder: isFrench ? "Ex: Tensions entre IT et Marketing, projet de migration Salesforce T4, résiliations en hausse sur le segment PME..." : "E.g., Active friction between IT and marketing, Q4 Salesforce migration project, rising churn in SMB segment...",
  summary: isFrench ? "Synthèse sémantique" : "Semantic Synthesis",
  gaps: isFrench ? "Gaps identifiés à explorer" : "Identified Gaps to Explore",
  questions: isFrench ? "Guide d'entretien structuré" : "Structured Interview Guide",
  insightTitle: isFrench ? "Diagnostic chargé" : "Loaded Assessment",
  insightStatus: isFrench ? "Statut" : "Status",
  insightMaturity: isFrench ? "Maturité" : "Maturity",
  modifySettings: isFrench ? "Modifier" : "Modify",

  // Things that go wrong, shown in the page's error banner.
  insightsFailed: isFrench ? "Échec de la génération des insights." : "Failed to generate insights.",
  networkError: isFrench ? "Erreur réseau." : "Network error.",
  generateFailed: isFrench ? "Échec de la génération du guide d'entretien." : "Failed to generate custom interview guide.",
  excelExportFailed: isFrench ? "Erreur lors de l'export Excel." : "Error exporting Excel.",

  // Navigation and page headings.
  backToInterviews: isFrench ? "Entretiens" : "Interviews",
  guidesHeading: isFrench ? "Guides d'entretien" : "Interview guides",
  guideHeading: isFrench ? "Guide d'entretien" : "Interview Guide",

  // The delete confirmation.
  deleteTitle: isFrench ? "Supprimer l'entretien ?" : "Delete interview?",
  cancel: isFrench ? "Annuler" : "Cancel",
  delete: isFrench ? "Supprimer" : "Delete",

  // How dates are formatted for the reader.

  // One section of the guide.
  totalQuestions: isFrench ? "questions au total" : "total questions",
  sectionDuration: isFrench ? "Section estimée à" : "Section estimated duration:",
  emptySection: isFrench ? "Aucune question dans cette section. Cliquez sur 'Ajouter' pour en créer une." : "No questions in this section. Click 'Add' to create one.",

  // One question, as it reads.
  answered: isFrench ? "Répondu" : "Answered",
  toAsk: isFrench ? "À poser" : "To Ask",
  edit: isFrench ? "Modifier" : "Edit",
  emptyQuestion: isFrench ? "(Question vide)" : "(Empty question)",
  whyHeading: isFrench ? "💡 Pourquoi cette question ?" : "💡 Why this question?",
  noObjective: isFrench ? "Aucun objectif spécifié" : "No objective specified",
  followUpsHeading: isFrench ? "📌 Relances potentielles" : "📌 Potential follow-ups",
  noProbes: isFrench ? "Aucune relance spécifiée" : "No probes specified",
  notesHeading: isFrench ? "📝 Notes" : "📝 Notes",

  // One question, while it is being edited.
  mainQuestionLabel: isFrench ? "Question principale" : "Main Question",
  mainQuestionPlaceholder: isFrench ? "Saisir la question..." : "Enter the question...",
  whyLabel: isFrench ? "Pourquoi cette question ?" : "Why this question?",
  whyPlaceholder: isFrench ? "Pourquoi poser cette question..." : "Why ask this question...",
  followUpsLabel: isFrench ? "Relances potentielles" : "Potential follow-ups",
  followUpsPlaceholder: isFrench ? "Quelles relances utiliser..." : "What follow-ups to use...",
  save: isFrench ? "Enregistrer" : "Save",

  // The interview analysis.
  analysisTitle: isFrench ? "Analyse de l'entretien" : "Interview analysis",
  generatedOn: isFrench ? "Généré le " : "Generated ",
  analysing: isFrench ? "Analyse..." : "Analysing...",
  regenerate: isFrench ? "Regénérer" : "Regenerate",
  analysisRunning: isFrench ? "Analyse en cours..." : "Analysing...",
  analyseInterview: isFrench ? "Analyser l'entretien" : "Analyse this interview",

  // The assistant chat.
  assistantTitle: isFrench ? "Assistant d'entretien" : "Interview Assistant",
  assistantSubtitle: isFrench ? "Interroger ce guide" : "Ask about this guide",
  assistantPlaceholder: isFrench ? "Poser une question sur le guide..." : "Ask about the guide...",

  // The saved-interviews table.
  sourceFromAssessment: isFrench ? "à partir d'une évaluation" : "from a maturity assessment",
  sourceFromScratch: isFrench ? "de zéro" : "from scratch",
  questionsSuffix: isFrench ? "questions" : "questions",
  viewBriefing: isFrench ? "Voir l'analyse" : "View the briefing",
  viewInsights: isFrench ? "Voir l'analyse" : "View insights",
  company: isFrench ? "Entreprise" : "Company",
  profile: isFrench ? "Profil" : "Profile",
  questionsColumn: isFrench ? "Questions" : "Questions",
  insightsColumn: isFrench ? "Analyse" : "Insights",
  updatedColumn: isFrench ? "Mise à jour" : "Updated",
  projectInterviews: isFrench ? "Entretiens du projet" : "Interviews in",
  newInterview: isFrench ? "Nouvel entretien" : "New interview",
  importInterview: isFrench ? "Importer un entretien sauvegardé" : "Import a saved interview",
  nothingToImport: isFrench ? "Aucun autre entretien à importer." : "No other interviews to import.",

  // The project-level interview report: one write-up across every interview in the project.
  generateReport: isFrench ? "Générer le rapport" : "Generate report",
  regenerateReport: isFrench ? "Régénérer" : "Regenerate",
  viewReport: isFrench ? "Voir le rapport" : "View report",
  projectReportHeading: isFrench ? "Rapport d'entretiens" : "Interview report",
  projectReportLead: isFrench
    ? "Tous les entretiens de ce projet, lus ensemble."
    : "Every interview in this project, read together.",
  projectReportEmpty: isFrench
    ? "Aucun rapport pour ce projet."
    : "There is no report for this project yet.",
  reportGenerating: isFrench ? "Génération en cours…" : "Generating…",
  reportStale: isFrench
    ? "Des entretiens ont changé depuis ce rapport."
    : "Interviews have changed since this report was generated.",
  reportGeneratedAt: isFrench ? "Généré le" : "Generated",
  reportNeedsInterviews: isFrench
    ? "Ajoutez au moins un entretien au projet pour générer un rapport."
    : "Add at least one interview to the project to generate a report.",

  // The three-step setup form.
  stepSourceLabel: isFrench ? "Source & Entreprise" : "Source & Company",
  stepPersonaLabel: isFrench ? "Profil cible" : "Target Persona",
  stepGenerateLabel: isFrench ? "Génération" : "Generate",
  step1Title: isFrench ? "Étape 1 — Source de données & informations entreprise" : "Step 1 — Data Source & Company Information",
  stepCompleted: isFrench ? "Complété" : "Completed",
  continueToStep2: isFrench ? "Continuer vers l'Étape 2" : "Continue to Step 2",
  step2Title: isFrench ? "Étape 2 — Profil de l'interlocuteur" : "Step 2 — Target Stakeholder Persona",
  customProfileTitle: isFrench ? "Spécifications du profil personnalisé" : "Custom Profile Specifications",
  customRoleLabel: isFrench ? "Nom du rôle" : "Role Name",
  customRolePlaceholder: isFrench ? "Ex: Responsable Filiale..." : "Ex: Subsidiary Manager...",
  customDescriptionLabel: isFrench ? "Description / Persona et spécifications" : "Description / Persona & specifications",
  backToStep1: isFrench ? "Retour à l'Étape 1" : "Back to Step 1",
  continueToStep3: isFrench ? "Continuer vers l'Étape 3" : "Continue to Step 3",
  step3Title: isFrench ? "Étape 3 — Contexte & remarques" : "Step 3 — Context & Remarks",
  backToStep2: isFrench ? "Retour à l'Étape 2" : "Back to Step 2",

  // Sheet names and headings in the Excel deliverable.
  sheetIntroduction: isFrench ? "Introduction" : "Introduction",
  sheetManage: isFrench ? "Piloter (Manage)" : "Manage",
  sheetAnalyze: isFrench ? "Analyser (Analyze)" : "Analyze",
  sheetImprove: isFrench ? "Améliorer (Improve)" : "Improve",
  sheetClosure: isFrench ? "Clôture (Closure)" : "Closure",
  sheetSummary: isFrench ? "Synthèse" : "Summary",
  sheetLanguage: isFrench ? "Langue" : "Language",
  sheetExecutiveSummary: isFrench ? "Synthèse de l'évaluation" : "Assessment Executive Summary",
  sheetKeyGaps: isFrench ? "Zones d'ombre à approfondir" : "Key Gaps / Blind Spots to Explore",

  // Longer copy: empty states, explanations and validation messages.
  interviewsHeading: isFrench ? "Entretiens" : "Interviews",
  emptyInProject: isFrench ? "Aucun entretien dans ce projet. Créez-en un ou importez-en un ci-dessous." : "No interviews in this project yet. Create one, or import a saved interview below.",
  emptyNoInterviews: isFrench ? "Aucun entretien pour le moment. Créez votre premier guide d'entretien." : "No interviews yet. Create your first interview guide.",
  deleteNotOwner: isFrench ? "Suppression impossible (vous n'êtes peut-être pas le propriétaire)." : "Could not delete (you may not be the owner).",
  noOrionHistory: isFrench ? "Aucune conversation d'auto-évaluation Orion à croiser avec cet entretien." : "No Orion self-assessment conversation to cross-reference with this interview.",
  guidesLead: isFrench ? "Vos entretiens : ouvrez-les, partagez-les, supprimez-les, ou créez-en un nouveau." : "Your interviews — open, share, delete, or create a new one.",
  analysisExplainer: isFrench ? "Compare les réponses à l'auto-évaluation Orion, relève les écarts et ce que l'entretien a révélé en plus. Enregistré avec le guide." : "Compares the answers with the Orion self-assessment, flags where they disagree, and captures what the interview added. Saved with the guide.",
  assistantHint: isFrench ? "Interprétez une réponse, repérez les lacunes, proposez des relances." : "Interpret an answer, spot gaps, suggest follow-ups.",
  noAssessmentInProject: isFrench ? "Ajoutez une évaluation de maturité à ce projet pour l'utiliser comme source." : "Add a maturity assessment to this project to use it as a source.",
  customDescriptionPlaceholder: isFrench ? "Décrivez le périmètre, les responsabilités et les points d'intérêt à explorer..." : "Describe the scope, responsibilities, and key topics to explore...",
  companyRequired: isFrench ? "Veuillez saisir le nom de l'entreprise." : "Please enter a company name.",
  customRoleRequired: isFrench ? "Veuillez saisir le nom du profil personnalisé." : "Please enter a custom profile name.",
  customDescriptionRequired: isFrench ? "Veuillez saisir la description du profil personnalisé." : "Please enter custom profile specifications.",
};
}

/**
 * The stakeholder profiles an interview can be aimed at.
 *
 * Each one steers the generated questions, so the description is not decoration -- it is what the
 * consultant picks from. "Other" carries no built-in context, which is why choosing it requires a
 * name and specifications of its own.
 */
export type InterviewPersona = {
  code: string;
  title: string;
  desc: string;
  icon: React.ReactNode;
  accent: string;
};

export function interviewPersonas(isFrench: boolean): InterviewPersona[] {
  return [
  {
    code: "CEO",
    title: isFrench ? "Directeur Général / CEO" : "Chief Executive Officer",
    desc: isFrench ? "Vision stratégique, arbitrages budgétaires, gouvernance." : "Strategic vision, budget trade-offs, governance.",
    icon: <Target className="h-5 w-5" />,
    accent: "yellow",
  },
  {
    code: "Marketing",
    title: isFrench ? "Directeur Marketing" : "Marketing Director",
    desc: isFrench ? "Promesse de marque, canaux, segmentation." : "Brand promise, channels, segmentation.",
    icon: <TrendingUp className="h-5 w-5" />,
    accent: "blue",
  },
  {
    code: "Call Center",
    title: isFrench ? "Responsable Centre de Contacts" : "Customer Service Manager",
    desc: isFrench ? "Opérations terrain, remontée des irritants." : "Frontline operations, issue escalation.",
    icon: <MessageSquareText className="h-5 w-5" />,
    accent: "emerald",
  },
  {
    code: "IT Lead",
    title: isFrench ? "Directeur Digital / IT / Data" : "Digital / IT / Data Lead",
    desc: isFrench ? "Données, CRM, IA, outils prédictifs." : "Data, CRM, AI, predictive tools.",
    icon: <Settings2 className="h-5 w-5" />,
    accent: "violet",
  },
  {
    code: "Other",
    title: isFrench ? "Autre profil / Personnalisé" : "Other Profile / Custom",
    desc: isFrench ? "Définissez un profil sur mesure et ses spécifications d'audit." : "Define a bespoke profile and its audit specifications.",
    icon: <Users className="h-5 w-5" />,
    accent: "slate",
  }
];
}
