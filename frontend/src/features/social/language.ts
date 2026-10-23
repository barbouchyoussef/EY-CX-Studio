/**
 * Heuristic language and dialect detection for anonymous customer comments.
 *
 * Extracted from the report view, where it drives the language-mix donut. It is pure
 * string work with no React, so it lives on its own — it can be read, reasoned about and changed
 * without opening a 2,900-line component.
 *
 * **What it does and does not claim.** This is good enough for a distribution chart and nothing
 * more. It looks at three signals: which script the text is written in, whether French or English
 * function words appear, and whether the text contains Tunisian Derja markers — in Arabic script
 * or in Arabizi, the Latin transliteration that substitutes digits for Arabic letters ("3lech",
 * "n7eb", "9ad"). No demographic inference of any kind is attempted, because comment text carries
 * no signal for it.
 *
 * Derja matters here specifically because the alternative is wrong rather than merely imprecise:
 * without it, Tunisian comments in Arabic script are all reported as "Arabic", and the Arabizi
 * ones fall through to "Other" — so the chart would understate the dialect the client's customers
 * actually write in.
 */

import { BRAND } from "../../lib/brand";

/** Arabic Unicode block. */
const ARABIC_SCRIPT = /[؀-ۿ]/;
/** Accented characters are a strong French signal, so they are weighted more than a single word. */
const FRENCH_ACCENTS = /[éèêàâçùûîïôœ]/i;

const DERJA_ARABIC = [
  "برشا", "ماكش", "ياسر", "شنوة", "باهي", "فمة", "قداش", "زادة", "موش", "كيفاش", "علاش", "بربي", "ماكانش",
];

/** Arabizi: Derja written in Latin script, where digits stand in for Arabic letters. */
const DERJA_LATIN = [
  "barcha", "barsha", "chnou", "behi", "famma", "n7eb", "7aja", "ya3tik", "sa7a", "3lech",
  "3andi", "yezi", "5dma", "9ad",
];

/** Function words and everyday vocabulary — padded with spaces so " le " does not match "level". */
const FRENCH_WORDS = [
  " je ", " tu ", " nous ", " vous ", " avec ", " très ", " pas ", " ne ", " est ", " sont ",
  " une ", " des ", " le ", " la ", " les ", "bonjour", "merci", "bien", "mauvais", "problème",
  "rapide", "personnel", "recommande", "banque", "agence", "pour", "sur", "vraiment", "toujours",
  "jamais",
];

const ENGLISH_WORDS = [
  " the ", " is ", " are ", " very ", " with ", "your", "please", "worst", "great", " good ",
  " bad ", " and ", "this", "that", " for ", " you ", "they", "have", "money", "account",
  "never", "always", "customer",
];

export type LangBucket = "Arabic" | "French" | "English" | "Tunisian dialect" | "Other";

/** Fixed display order, so the chart legend does not reshuffle between reports. */
export const LANG_ORDER: LangBucket[] = ["Arabic", "French", "English", "Tunisian dialect", "Other"];

export const LANG_COLORS: Record<LangBucket, string> = {
  Arabic: "#2a78d6",
  French: "#eb6834",
  English: "#1baf7a",
  "Tunisian dialect": BRAND.gold,
  Other: "#94a3b8",
};

/** Share of the text's letters that are Arabic script, ignoring digits and punctuation. */
export function arabicRatio(text: string): number {
  const letters = [...text].filter((c) => /[a-zA-Z؀-ۿ]/.test(c));
  if (!letters.length) return 0;
  return letters.filter((c) => ARABIC_SCRIPT.test(c)).length / letters.length;
}

/**
 * Best-effort bucket for one comment.
 *
 * Script is decided first: past 40% Arabic letters the text is Arabic, and Derja markers then
 * separate dialect from standard. Otherwise Latin script is scored by counting French against
 * English markers, with accents worth two. A tie goes to French, and text matching nothing at all
 * is "Other" rather than guessed at.
 */
export function detectLanguage(text: string): LangBucket {
  const raw = text || "";
  const padded = ` ${raw.toLowerCase()} `;

  if (arabicRatio(raw) > 0.4) {
    return DERJA_ARABIC.some((w) => raw.includes(w)) ? "Tunisian dialect" : "Arabic";
  }
  if (DERJA_LATIN.some((w) => padded.includes(w))) return "Tunisian dialect";

  const french = FRENCH_WORDS.filter((w) => padded.includes(w)).length + (FRENCH_ACCENTS.test(raw) ? 2 : 0);
  const english = ENGLISH_WORDS.filter((w) => padded.includes(w)).length;
  if (french === 0 && english === 0) return "Other";
  return french >= english ? "French" : "English";
}
