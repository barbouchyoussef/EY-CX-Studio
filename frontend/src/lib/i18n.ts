/**
 * Picking the right copy for the current language.
 *
 * The platform ships in French and English. There is no translation library and no key catalogue:
 * each screen keeps its own copy beside the markup it belongs to, as a `{ fr, en }` pair. That
 * suits a two-language product where the copy is prose rather than labels, and it means a wording
 * change is one edit in one file.
 *
 * What was missing was a shared way to *choose* between the two. Eleven screens each wrote their
 * own line, and they had drifted into three shapes -- `TRANSLATIONS[lang] || TRANSLATIONS.en`,
 * `T[lang] || T.en`, and `isFrench ? COPY.fr : COPY.en` -- with one of them falling back to
 * French while every other fell back to English. The fallback is the only real decision here, so
 * it is made once, in `pickCopy`.
 */

/** The two languages the platform ships in. */
export type Language = "fr" | "en";

/** One screen's copy, written once per language. */
export type Copy<T> = Record<Language, T>;

/**
 * The copy for `language`, falling back to English.
 *
 * English is the fallback because it is the default the app starts in and the language of the
 * client deliverables. An unrecognised value means a caller passed something unexpected, and
 * showing the default is better than showing nothing.
 */
export function pickCopy<T>(copy: Copy<T>, language: string | null | undefined): T {
  return language === "fr" ? copy.fr : copy.en;
}

/** True when the given language code is French. For the screens that only need the flag. */
export function isFrench(language: string | null | undefined): boolean {
  return language === "fr";
}
