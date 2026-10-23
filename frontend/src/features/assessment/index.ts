/**
 * The maturity-assessment module's public surface.
 *
 * Four exports rather than one, because the assessment is reached from four places: the
 * consultant runs it, a client answers it through a passwordless link, and the admin screens
 * inspect the report it produces. Everything else in this folder -- including the whole report/
 * tree -- is internal to those.
 */

export { default as AssessmentChat } from "./hub";
export { default as ClientAssessmentPage } from "./client/page";
export { default as AssessmentReport } from "./report/AssessmentReport";
export { default as AssessmentGeneratingPage } from "./generating-page";
