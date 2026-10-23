/**
 * The project workspace: where an engagement is assembled from the other modules.
 *
 * The hub is the app's landing surface -- it lists projects, shows the pipeline of a chosen one,
 * and launches the feature modules. The step nav is the band those modules render at the top of
 * their own screens while a project is active, which is why it is exported too.
 */

export { default as ServicesHub } from "./hub";
export { default as ProjectStepNav } from "./step-nav";
