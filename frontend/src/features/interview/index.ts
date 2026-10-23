/**
 * The interview module's public surface.
 *
 * Everything else in this folder is internal to the module. TypeScript cannot forbid another file
 * from reaching past this one, but going through it is what makes the folder a module rather than
 * a category: it states the single thing the rest of the app depends on, so the other ten files
 * can be renamed, split or rewritten without a search across the codebase.
 *
 * If a second export ever belongs here, that is worth a moment's thought -- it means something
 * outside now depends on the module's internals, and the question is whether that is the right
 * seam or whether the caller wants something this module should offer deliberately.
 */

export { default } from "./hub";
