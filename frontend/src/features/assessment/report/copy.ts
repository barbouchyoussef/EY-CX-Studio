/**
 * Every word the maturity report puts in front of a reader, in both languages.
 *
 * The report has its own table rather than sharing the assessment chat's, because it is a
 * separate surface with a separate voice: the chat is a conversation, the report is the client
 * deliverable. It is rendered three ways -- for the consultant, for a client opening a
 * passwordless link, and inside the admin screens -- and all three read from here.
 *
 * A table because these are the sentences most likely to be revised without a line of logic
 * changing: a heading a partner wants worded differently, a closing paragraph, the note under a
 * benchmark. None of that should mean opening a report section.
 */

export type ReportCopy = ReturnType<typeof reportCopy>;

export function reportCopy(isFrench: boolean) {
  return {

  // Section headings, in the order the report reads.
  whereYouStand: isFrench ? "Votre position" : "Where You Stand",
  keyFindings: isFrench ? "Diagnostic & constats clés" : "Key diagnostic findings",
  maturityProfile: isFrench ? "Profil de maturité" : "Maturity profile",
  workingMissingTitle: isFrench ? "Ce qui fonctionne et ce qui manque" : "What's Working & What's Missing",
  axisReview: isFrench ? "Examen par axe" : "Axis Review",
  benchmarkLeaders: isFrench ? "Analyse comparative des leaders" : "Benchmark Leaders",
  quickWins: isFrench ? "Gains rapides" : "Quick Wins",
  capabilityDetail: isFrench ? "Détails des capacités" : "Capability Detail",
  goFurther: isFrench ? "Aller plus loin" : "Go Further",
  leadersTitle: isFrench ? "Ce que font les leaders" : "What Leaders Are Doing",

  // The per-axis panels.
  axisPrefix: isFrench ? "Axe " : "Axis ",
  axisSuffix: isFrench ? " : la réalité aujourd'hui" : ": what's real today",
  axisLabel: isFrench ? "Axe" : "Axis",
  working: isFrench ? "Ce qui fonctionne" : "Working",
  workingLead: isFrench ? "Capacités démontrant déjà des preuves opérationnelles crédibles." : "Capabilities already showing credible operating evidence.",
  missing: isFrench ? "Ce qui manque" : "Missing",
  missingLead: isFrench ? "Capacités qui manquent encore de preuves pour être considérées comme systématiques." : "Capabilities that still lack enough evidence to feel systematic.",
  whatIsWorking: isFrench ? "Ce qui fonctionne" : "What is working",
  whatIsWorkingLead: isFrench ? "Preuves crédibles présentes." : "Credible evidence is present.",
  whatIsMissing: isFrench ? "Ce qui manque" : "What is missing",
  whatIsMissingLead: isFrench ? "Des preuves supplémentaires sont requises." : "More evidence is still needed.",
  axisDetailLead: isFrench ? "Détails de l'évaluation pour cet axe." : "Assessment detail for this axis.",

  // The hero, and how each maturity band is described.
  heroKicker: isFrench ? "DIAGNOSTIC EXPÉRIENCE CLIENT" : "CUSTOMER EXPERIENCE AUDIT",
  heroLevel: isFrench ? "NIVEAU" : "LEVEL",
  heroStage: isFrench ? "Niveau Actuel" : "Actual Stage",
  heroStrongestAxis: isFrench ? "Axe le plus Fort" : "Strongest Axis",
  heroPriorityAxis: isFrench ? "Axe Prioritaire" : "Priority Axis",
  strongestAxisTooltip: isFrench ? "C'est l'axe le plus fort selon vos réponses" : "This is the strongest axis according to your answers",
  priorityAxisTooltip: isFrench ? "C'est l'axe le plus prioritaire à traiter selon vos réponses" : "This is the highest priority axis to address according to your answers",
  maturityLandscapeTitle: isFrench ? "Votre position — Paysage de maturité" : "Where You Stand — Maturity Landscape",
  bandBasicLead: isFrench ? "Les routines réactives dominent toujours et les retours clients ne sont pas encore traduits de manière cohérente en actions." : "Reactive routines still dominate and customer evidence is not yet consistently translated into action.",
  bandEstablishedLead: isFrench ? "Les bases sont visibles et répétables, mais l'exécution et la gouvernance restent inégales." : "Foundations are visible and repeatable, but execution and governance remain uneven.",
  bandAdvancedLead: isFrench ? "L'analyse client est intégrée dans la prise de décision, la responsabilité et l'amélioration continue." : "Customer insight is embedded into decision-making, ownership, and sustained improvement.",

  // Capability evidence.
  referenceGuide: isFrench ? "Guide de référence" : "Reference Guide",
  viewReferenceGuide: isFrench ? "Voir le guide de référence" : "View Reference Guide",
  evidenceUsed: isFrench ? "Preuves utilisées" : "Evidence used",
  observedSignal: isFrench ? "Signal observé" : "Observed signal",
  recommendedAction: isFrench ? "Action recommandée" : "Recommended action",

  // Quick wins.
  quickWinToday: isFrench ? "Aujourd'hui" : "Today",
  quickWinAfter: isFrench ? "Après cette action" : "After this",
  quickWinOwner: isFrench ? "Responsable" : "Owner",
  quickWinCurrent: isFrench ? "État actuel" : "Current state",
  quickWinOutcome: isFrench ? "Résultat attendu" : "Expected outcome",
  quickWinClose: isFrench ? "Fermer le quick win" : "Close quick win",
  quickWinOpen: isFrench ? "Ouvrir le quick win" : "Open quick win",

  // The competitor benchmark.
  leadersPreparing: isFrench ? "Le contenu de référence des leaders est en cours de préparation en arrière-plan." : "Leader benchmark content is being prepared in the background.",
  leadersUnavailable: isFrench ? "Le contenu de référence des leaders n'est pas encore disponible pour ce rapport." : "Leader benchmark content is not available for this report yet.",
  leadersLead: isFrench ? "Ces leaders gèrent l'expérience client comme un système de croissance coordonné, et non comme une simple collection de bonnes intentions." : "These leaders run customer experience as a coordinated growth system, not a collection of good intentions.",
  leaderEvidenceNote: isFrench ? "Des données de référence publiques ont été sélectionnées pour ce leader." : "Public benchmark evidence was selected for this leader.",
  leaderEvidenceNoteShort: isFrench ? "Des données de référence publiques ont été sélectionnées pour ce leader." : "Public benchmark evidence selected for this leader.",
  leadersSubheading: isFrench ? "Ce que font les leaders" : "What leaders are doing",
  openSource: isFrench ? "Source ouverte" : "Open source",
  exclusiveThoughtLeadership: isFrench ? "Perspective exclusive" : "Exclusive thought leadership",
  readEyArticle: isFrench ? "Consulter l'article EY" : "Read EY Article",

  // The EY deck preview.
  deckPreviewTitle: isFrench ? "Aperçu de la présentation" : "Presentation Preview",
  deckLocalTitle: isFrench ? "Mode local détecté" : "Local Environment Detected",
  deckLocalLead: isFrench ? "Vous exécutez l'application en mode local. Le visualiseur PowerPoint en ligne ne peut pas se connecter à votre serveur local pour afficher le document en direct." : "You are running this application in a local environment. The online PowerPoint viewer cannot connect to your local server to preview the document live.",
  deckDownload: isFrench ? "Télécharger pour visionner" : "Download to View",
  close: isFrench ? "Fermer" : "Close",

  // Booking a consultation.
  closingKicker: isFrench ? "Orbit | Note de clôture" : "Orbit | Closing note",
  closingLead: isFrench ? "Les gains rapides ci-dessus sont réels et réalisables par vous-même. Pour les organisations prêtes à aller plus vite avec une expertise senior intégrée à leurs équipes et des benchmarks sectoriels à chaque étape, c'est ici qu'Orbit se connecte à EY Studio+." : "The quick wins above are real and achievable on your own. For organizations ready to move faster with senior expertise embedded alongside their team and sector benchmarks at every milestone, this is where Orbit connects to EY Studio+.",
  closingBody: isFrench ? "EY Studio+ accompagne les organisations à chaque niveau de maturité, en concevant l'infrastructure de mesure, les systèmes de personnalisation et l'expérience numérique qui propulsent les acteurs en croissance dans la même catégorie compétitive que les leaders mentionnés dans ce rapport. La collaboration commence par un échange, pas par une proposition commerciale." : "EY Studio+ works with organizations at every maturity stage, designing the measurement infrastructure, personalization systems, and digital experience that move growing operators into the same competitive league as the leaders referenced in this report. Engagement starts with a conversation, not a proposal.",
  bookingTitle: isFrench ? "Prêt à commencer ?" : "Ready to start?",
  bookingLead: isFrench ? "Réservez une session stratégique de 30 minutes avec un spécialiste sectoriel." : "Book a 30-minute strategy session with a sector specialist.",
  bookingReassurance: isFrench ? "Pas de proposition. Pas d'engagement. Première valeur livrée en 4 semaines." : "No proposal. No commitment. First value delivered in 4 weeks.",
  bookConsultation: isFrench ? "Réserver une consultation" : "Book consultation",
  bookingModalTitle: isFrench ? "Réservez une consultation en expérience client" : "Book a customer experience consultation",
  bookingModalLead: isFrench ? "Entrez votre nom uniquement. Gmail s'ouvrira avec un message préparé que vous pourrez relire avant envoi." : "Enter your name only. Gmail will open with a prepared message that you can review before sending.",
  yourNameLabel: isFrench ? "Votre nom" : "Your name",
  nameRequired: isFrench ? "Veuillez entrer votre nom." : "Please enter your name.",
  gmailFailed: isFrench ? "Impossible de préparer le message Gmail." : "Could not prepare the Gmail message.",
  gmailNoUrl: isFrench ? "Le serveur n'a pas renvoyé d'URL Gmail." : "The backend did not return a Gmail URL.",
  preparing: isFrench ? "Préparation..." : "Preparing...",
  openGmail: isFrench ? "Ouvrir Gmail" : "Open Gmail",
  cancel: isFrench ? "Annuler" : "Cancel",

  // Page chrome, and the PDF export.
  back: isFrench ? "Retour" : "Back",
  downloadPdf: isFrench ? "Télécharger le PDF" : "Download PDF",
  downloadPdfReport: isFrench ? "Télécharger le PDF" : "Download PDF Report",
  copyright: isFrench ? "© 2026 EY Studio+ Expérience Client. Tous droits réservés." : "© 2026 EY Studio+ Customer Experience. All rights reserved.",
  pdfTitle: isFrench ? "Rapport d'évaluation de l'expérience client EY Studio+" : "EY Studio+ Customer Experience Assessment Report",
  pdfHeading: isFrench ? "Évaluation de l'expérience client" : "Customer Experience Assessment",
  pdfOverallMaturity: isFrench ? "Maturité globale" : "Overall maturity",
  pdfNoSummary: isFrench ? "Résumé de l'évaluation non disponible." : "Assessment summary unavailable.",
  pdfStage: isFrench ? "Niveau" : "Stage",
  pdfStrongest: isFrench ? "Le plus fort" : "Strongest",
  pdfPriority: isFrench ? "Prioritaire" : "Priority",
  };
}
