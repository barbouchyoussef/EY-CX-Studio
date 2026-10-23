/**
 * Everything the social listening dashboard puts on screen, in both languages.
 *
 * Spreads the shared dashboard vocabulary, so the row menu and the shared badge read the same
 * here as in every other module and are defined once.
 */

import { dashboardCopy } from "../../lib/dashboard-copy";

export type SocialTableCopy = ReturnType<typeof socialTableCopy>;

export function socialTableCopy(isFrench: boolean) {
  return {
    ...dashboardCopy(isFrench),

  // What a report is, in a row and in a column heading.
  reviewsSuffix: isFrench ? "avis" : "reviews",
  brandColumn: isFrench ? "Marque" : "Brand",
  reviewsColumn: isFrench ? "Avis" : "Reviews",
  dateColumn: isFrench ? "Date" : "Date",

  // The page around the table.
  projectReports: isFrench ? "Rapports du projet" : "Reports in",
  reportsHeading: isFrench ? "Rapports d'écoute sociale" : "Social listening reports",
  newAnalysis: isFrench ? "Nouvelle analyse" : "New analysis",
  emptyInProject: isFrench ? "Aucun rapport dans ce projet. Lancez une analyse ou importez-en un ci-dessous." : "No reports in this project yet. Run an analysis, or import a saved report below.",
  emptyNoReports: isFrench ? "Aucun rapport pour le moment. Lancez votre première analyse d'écoute sociale." : "No reports yet. Run your first social listening analysis.",
  importReport: isFrench ? "Importer un rapport sauvegardé" : "Import a saved report",
  nothingToImport: isFrench ? "Aucun autre rapport à importer." : "No other reports to import.",
  };
}
