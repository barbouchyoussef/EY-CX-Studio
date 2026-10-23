/**
 * The words the project workspace puts on screen, in both languages.
 *
 * Spreads the shared dashboard vocabulary, so "Add", "Open" and "Delete permanently" read the
 * same here as on every module dashboard and are defined once.
 */

import { dashboardCopy } from "../../lib/dashboard-copy";

export type ProjectCopy = ReturnType<typeof projectCopy>;

export function projectCopy(isFrench: boolean) {
  return {
    ...dashboardCopy(isFrench),

  // Who can see a project.
  team: isFrench ? "Équipe" : "Team",
  owner: isFrench ? "Propriétaire" : "Owner",
  remove: isFrench ? "Retirer" : "Remove",
  collaboratorPlaceholder: isFrench ? "email du collaborateur" : "collaborator@company.com",
  adding: isFrench ? "Ajout…" : "Adding…",
  mustHaveAccount: isFrench ? "Le collaborateur doit déjà avoir un compte. Invitez-le d'abord via « Équipe & accès »." : "The person must already have an account. Invite them first via “Team & access.”",

  // A project and the pipeline it moves through.
  project: isFrench ? "Projet" : "Project",
  delete: isFrench ? "Supprimer" : "Delete",
  removeFromProject: isFrench ? "Retirer du projet" : "Remove from project",
  pipelineProgress: isFrench ? "Progression du pipeline" : "Pipeline progress",
  soonBadge: isFrench ? "Bientôt" : "Soon",
  comingSoon: isFrench ? "Bientôt disponible" : "Coming soon",
  attachedResults: isFrench ? "Résultats attachés" : "Attached results",
  projectSteps: isFrench ? "Étapes du projet" : "Project steps",
  openProject: isFrench ? "Ouvrir le projet" : "Open project",

  // The projects sidebar.
  projectsHeading: isFrench ? "Projets" : "Projects",
  allTools: isFrench ? "Tous les outils" : "All tools",
  newProject: isFrench ? "Nouveau projet" : "New project",
  projectNamePlaceholder: isFrench ? "Nom du projet" : "Project name",
  companyPlaceholder: isFrench ? "Entreprise" : "Company",
  create: isFrench ? "Créer" : "Create",
  emptyNoProjects: isFrench ? "Aucun projet. Créez-en un pour démarrer un pipeline." : "No projects yet. Create one to start a pipeline.",
  };
}
