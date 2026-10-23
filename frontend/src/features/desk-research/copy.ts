/**
 * Everything the desk-research dashboard puts on screen, in both languages.
 *
 * Spreads the shared dashboard vocabulary, so the row menu and the shared badge read the same
 * here as in every other module and are defined once.
 */

import { dashboardCopy } from "../../lib/dashboard-copy";

export type DeskCopy = ReturnType<typeof deskCopy>;

export function deskCopy(isFrench: boolean) {
  return {
    ...dashboardCopy(isFrench),

  // What a session is, in a row and in a column heading.
  documentsSuffix: isFrench ? "documents" : "documents",
  reportBadge: isFrench ? "Rapport" : "Report",
  sessionColumn: isFrench ? "Session" : "Session",
  documentsColumn: isFrench ? "Documents" : "Documents",
  createdColumn: isFrench ? "Créé" : "Created",

  // The page around the table.
  projectSessions: isFrench ? "Sessions du projet" : "Sessions in",
  sessionsHeading: isFrench ? "Sessions de recherche" : "Research sessions",
  newSession: isFrench ? "Nouvelle session" : "New session",
  emptyInProject: isFrench ? "Aucune session dans ce projet. Créez-en une ou importez-en une ci-dessous." : "No sessions in this project yet. Create one, or import a saved session below.",
  emptyNoSessions: isFrench ? "Aucune session pour le moment. Créez votre première session de desk research." : "No sessions yet. Create your first desk research session.",
  importSession: isFrench ? "Importer une session sauvegardée" : "Import a saved session",
  nothingToImport: isFrench ? "Aucune autre session à importer." : "No other sessions to import.",
  };
}
