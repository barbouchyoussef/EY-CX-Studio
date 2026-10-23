/**
 * Everything the assessment chat says in its own voice, in both languages.
 *
 * Held as a table rather than as if-chains on the axis code. The previous shape asked the same
 * `axis === "MANAGE"` question in two separate functions to return two different strings, which
 * is how one of them ends up reworded and the other quietly left behind.
 *
 * KNOWN GAP: five onboarding messages are still English-only and inline in hub.tsx -- the sector
 * and size retries, the failure to start, and the two answer-submission errors. They belong here.
 * A French consultant currently gets a French greeting followed by English errors. Left alone on
 * purpose: translating them changes what users read, so it is a fix in its own right.
 */

import { dashboardCopy } from "../../lib/dashboard-copy";

/** The three axes, in the order the assessment walks them. */
export const AXIS_ORDER = ["MANAGE", "ANALYZE", "IMPROVE"] as const;

export type AxisCode = (typeof AXIS_ORDER)[number];

/** Where an axis sits in the sequence.
 *
 *  An unknown or missing axis reads as the first one: the progress bar has to point somewhere,
 *  and an assessment always begins at MANAGE. Both call sites used to spell this out inline as
 *  `Math.max(0, AXIS_ORDER.indexOf(axis || AXIS_ORDER[0]))`, twice. */
export const axisIndex = (axis: string | null | undefined): number => {
  const found = AXIS_ORDER.indexOf((axis ?? "") as AxisCode);
  return found < 0 ? 0 : found;
};

type Bilingual = { fr: string; en: string };

const isFrench = (lang: string) => lang === "fr";

/** What each axis is called on screen, and the line describing what it asks about. */
const AXIS_COPY: Record<AxisCode, { name: Bilingual; subtitle: Bilingual }> = {
  MANAGE: {
    name: { fr: "GÉRER", en: "MANAGE" },
    subtitle: {
      fr: "Comment votre organisation s'approprie l'expérience",
      en: "How your organization owns the experience",
    },
  },
  ANALYZE: {
    name: { fr: "ANALYSER", en: "ANALYZE" },
    subtitle: {
      fr: "Comment vous transformez les signaux clients en décisions",
      en: "How you turn customer signals into decisions",
    },
  },
  IMPROVE: {
    name: { fr: "AMÉLIORER", en: "IMPROVE" },
    subtitle: {
      fr: "Comment vous agissez, vous adaptez et avancez",
      en: "How you act, adapt, and move forward",
    },
  },
};

/** An unrecognised axis shows its own code: that is a data problem, and a blank would hide it. */
export const getAxisDisplayName = (axis: string, lang: string): string => {
  const entry = AXIS_COPY[axis as AxisCode];
  if (!entry) return axis;
  return isFrench(lang) ? entry.name.fr : entry.name.en;
};

export const getAxisProgressSubtitle = (axis: string, lang: string): string => {
  const entry = AXIS_COPY[axis as AxisCode];
  if (!entry) return "";
  return isFrench(lang) ? entry.subtitle.fr : entry.subtitle.en;

};


export const getInitialGreeting = (lang: string) =>
  isFrench(lang)
    ? "Bonjour, je suis l'assistant EY. Si vous êtes ici, cela signifie que votre organisation est prête à porter un regard honnête sur l'expérience qu'elle propose. C'est là que j'interviens."
    : "Hello, I’m the EY assistant. If you’re here, it means your organization is ready to take an honest look at the experience it delivers. That’s where I come in.";

export const getAssessmentStartIntro = (lang: string) =>
  isFrench(lang)
    ? "Maintenant que j'ai le contexte de votre entreprise, commençons l'évaluation."
    : "Now that I have your company context, let's begin the assessment.";


/**
 * Everything the assessment's own screens say, in both languages.
 *
 * Separate from the axis tables above, which describe the framework; this is the product's voice.
 * The client chat is in here too, and it is the most externally visible text the platform
 * produces -- a client on a passwordless link reads nothing else of ours.
 */
export type AssessmentCopy = ReturnType<typeof assessmentCopy>;

export function assessmentCopy(french: boolean) {
  return {
    ...dashboardCopy(french),
  // The saved-assessments table.
  statusCompleted: french ? "Terminée" : "Completed",
  statusInProgress: french ? "En cours" : "In progress",
  statusLinkSent: french ? "Lien envoyé" : "Link sent",
  statusOpened: french ? "Ouvert par le client" : "Opened by client",
  awaitingClient: french ? "En attente du client" : "Awaiting client",
  sentTo: french ? "Envoyé à" : "Sent to",
  resume: french ? "Reprendre" : "Resume",
  companyColumn: french ? "Entreprise" : "Company",
  statusColumn: french ? "Statut" : "Status",
  maturityColumn: french ? "Maturité" : "Maturity",
  updatedColumn: french ? "Mise à jour" : "Updated",
  projectAssessments: french ? "Évaluations du projet" : "Assessments in",
  assessmentsHeading: french ? "Évaluations" : "Assessments",
  newAssessment: french ? "Nouvelle évaluation" : "New assessment",
  emptyInProject: french ? "Aucune évaluation dans ce projet. Lancez-en une ou importez-en une ci-dessous." : "No assessments in this project yet. Start one, or import a saved assessment below.",
  emptyNoAssessments: french ? "Aucune évaluation pour le moment. Lancez votre première évaluation." : "No assessments yet. Start your first assessment.",
  importAssessment: french ? "Importer une évaluation" : "Import a saved assessment",
  nothingToImport: french ? "Aucune autre évaluation à importer." : "No other assessments to import.",


  // Onboarding, when the platform cannot work something out on its own.
  //
  // These were English-only until now: a French consultant got a French greeting and then, the
  // moment anything needed clarifying, English. The two that list options take the list, because
  // it is built from whatever the reference tables hold.
  sectorNotUnderstood: french
    ? "Je n'ai pas compris ce choix de secteur. Répondez par un numéro ou le nom exact du secteur."
    : "I did not catch that sector choice. Please reply with a number or exact sector label.",
  sizeNotUnderstood: french
    ? "Je n'ai pas compris ce choix de taille. Répondez par un numéro ou le nom exact de la taille."
    : "I did not catch that size choice. Please reply with a number or exact size label.",
  couldNotStart: french
    ? "Je n'ai pas pu démarrer l'évaluation. Veuillez réessayer."
    : "I could not start the assessment yet. Please try again.",
  outOfSync: french
    ? "Nous nous sommes désynchronisés. J'ai actualisé l'état. Poursuivez avec la dernière question."
    : "We got out of sync. I refreshed the state. Please continue with the latest question.",
  couldNotProcessAnswer: french
    ? "Je n'ai pas pu traiter cette réponse. Veuillez réessayer."
    : "I could not process that answer. Please try once more.",
  chooseSector: (options: string) =>
    french
      ? `Merci. Je n'ai pas pu déduire votre secteur à partir du nom seul. Choisissez votre secteur : ${options}`
      : `Thanks. I could not confidently infer your sector from the name alone. Please choose your sector: ${options}`,
  chooseSize: (options: string) =>
    french
      ? `Parfait. Choisissez maintenant la taille de votre entreprise : ${options}`
      : `Great. Now choose your company size: ${options}`,

  // What a client is told when something goes wrong.
  chooseSectorAndSize: french ? "Veuillez choisir le secteur et la taille." : "Please choose a sector and a company size.",
  somethingWentWrong: french ? "Un problème est survenu. Réessayez." : "Something went wrong. Please try again.",
  sorrySomethingWentWrong: french ? "Désolé, un problème est survenu. Veuillez réessayer." : "Sorry, something went wrong. Please try again.",
  linkExpiredTitle: french ? "Lien invalide ou expiré" : "This link is invalid or has expired",
  linkExpiredLead: french ? "Veuillez demander un nouveau lien à votre contact EY." : "Please ask your EY contact for a fresh link.",

  // The client-facing chat. This is the most externally visible text the platform produces.
  assistantName: french ? "Assistant EY" : "EY Assistant",
  clientGreeting: french ? "Bonjour, je suis l'assistant EY." : "Hello, I’m the EY assistant.",
  clientGreetingBody: french ? "Si vous êtes ici, cela signifie que votre organisation est prête à porter un regard honnête sur l'expérience qu'elle propose.\n\nC'est là que j'interviens.\n\nParlez-moi un peu de votre organisation pour commencer." : "If you’re here, it means your organization is ready to take an honest look at the experience it delivers.\n\nThat’s where I come in.\n\nTell me a little about your organization to get us started.",
  assessmentName: french ? "Diagnostic de maturité CX" : "CX Maturity Assessment",
  journeyTitle: french ? "Parcours d'évaluation" : "Assessment Journey",
  guidedInterview: french ? "Entretien guidé" : "Guided interview",
  progressLabel: french ? "Progression" : "Progress",
  clientGuidance: french ? "Restez concentré sur des exemples concrets. Nous nous occupons de l'analyse." : "Stay focused on practical examples. We handle the analysis.",
  assistantThinking: french ? "L'assistant réfléchit..." : "Assistant is thinking...",
  answerWithOptionsPlaceholder: french ? "Choisissez une option ou écrivez votre réponse…" : "Pick an option or type your answer…",
  answerPlaceholder: french ? "Votre réponse…" : "Your answer…",
  nextQuestion: french ? "Question suivante…" : "Next question…",
  thankYouTitle: french ? "Merci !" : "Thank you!",
  thankYouLead: french ? "Vos réponses ont bien été enregistrées. L'équipe EY analysera les résultats et reviendra vers vous." : "Your responses have been recorded. The EY team will review the results and follow up with you.",
  generatingReport: french ? "Génération de votre rapport…" : "Generating your report…",
  generatingLead: french ? "Merci de patienter quelques instants." : "This may take a few moments.",

  // The company profile a client confirms before the questions start.
  profileWhy: french ? "Le secteur et la taille de l'entreprise servent de contexte structuré, ils ne sont pas devinés à partir du nom." : "Sector and company size are used as structured context, not guessed from the company name.",
  profileTitle: french ? "Profil de l'entreprise" : "Company profile",
  profileHeading: french ? "Définir le contexte" : "Set your context",
  profileLead: french ? "Confirmez le nom de votre entreprise, puis choisissez le secteur et la taille." : "Confirm your company name, then choose the sector and size.",
  companyNameLabel: french ? "Nom de l'entreprise" : "Company name",
  companyNamePlaceholder: french ? "Nom de votre entreprise" : "Your company name",
  sectorLabel: french ? "Secteur d'activité" : "Sector",
  sectorPlaceholder: french ? "Sélectionner un secteur" : "Select sector",
  sizeLabel: french ? "Taille de l'entreprise" : "Company size",
  sizePlaceholder: french ? "Sélectionner la taille" : "Select size",
  startAssessment: french ? "Commencer l'évaluation" : "Start the assessment",

  // The language toggle.
  languageCode: french ? "en" : "fr",
  languageToggle: french ? "EN" : "FR",

  };
}
