/**
 * The social listening module's public surface.
 *
 * Everything else in this folder is internal. Going through here is what makes the folder a
 * module rather than a category: it names the one file the rest of the app depends on, so the
 * other eight can be renamed or split without a search across the codebase.
 */

export { default } from "./hub";
