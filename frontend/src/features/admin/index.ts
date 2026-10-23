/**
 * The admin module's public surface.
 *
 * Four entry points rather than one, because App.tsx routes to each screen directly: the
 * dashboard, the two assessment inspectors, and user management. Everything else in this folder
 * is internal to them.
 */

export { default as AdminDashboard } from "./dashboard";
export { default as AdminAssessmentDetail } from "./assessment-detail";
export { default as AdminAssessmentReport } from "./assessment-report";
export { default as AdminUsersPage } from "./users-page";
