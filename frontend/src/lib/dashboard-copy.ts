/**
 * The words every module dashboard uses, regardless of what it lists.
 *
 * The four dashboards — assessments, interviews, social reports, desk sessions — are the same
 * screen over different data, so they share a vocabulary: a row menu, an import action, a badge
 * for something a colleague shared with you, a date format. Each had written its own copy of it,
 * and all four agreed by luck rather than by construction.
 *
 * A module's own table spreads this in, so a component still reads everything through one
 * accessor and the shared words have one definition:
 *
 *     export function interviewLabels(isFrench: boolean) {
 *       return { ...dashboardCopy(isFrench), ...(the module's own words) };
 *     }
 *
 * What belongs here is only what is genuinely about being a dashboard. "Research sessions" and
 * "Social listening reports" name the thing each module holds, so they stay with their module.
 */

export type DashboardCopy = ReturnType<typeof dashboardCopy>;

export function dashboardCopy(isFrench: boolean) {
  return {
    /** Passed to toLocaleDateString, so every dashboard formats a date the same way. */
    dateLocale: isFrench ? "fr-FR" : "en-US",

    // A row someone else owns, and the actions available on any row.
    sharedWithYou: isFrench ? "Partagé avec vous" : "Shared with you",
    open: isFrench ? "Ouvrir" : "Open",
    moreActions: isFrench ? "Plus d'actions" : "More actions",
    deletePermanently: isFrench ? "Supprimer définitivement" : "Delete permanently",
    viewReport: isFrench ? "Voir le rapport" : "View report",

    /** Attach an existing result to the open project. */
    add: isFrench ? "Ajouter" : "Add",
  };
}
