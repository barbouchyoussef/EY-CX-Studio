/**
 * The brand palette, for the places that need a colour as a JavaScript value.
 *
 * Markup should use the Tailwind tokens instead — `bg-ey-gold`, `text-ey-navy` and so on, which
 * come from the `@theme` block in `index.css`. This module is for the cases where a class name
 * cannot reach:
 *
 *   * data that carries its own colour (a chart series, an axis in a preview, a legend);
 *   * `hexToRgba` and friends, which PARSE the value — a `var(--color-ey-gold)` string would
 *     turn into NaN rather than a colour.
 *
 * These values must stay in step with the `@theme` block. CSS custom properties cannot be read
 * from JavaScript without going through the DOM, so the two are kept aligned by hand; there is a
 * test asserting they match, so a change to one that misses the other fails rather than drifts.
 */

export const BRAND = {
  /** The accent used across the whole platform. */
  gold: "#C5A04F",
  /** Gold text on a light gold ground, where the accent itself is unreadable. */
  goldDeep: "#8A6D00",
  /** EY's own yellow, for the brand mark and its highlights. */
  yellow: "#F6D200",
  /** The dark surface: nav bands, the report hero, primary buttons. */
  navy: "#1A1F36",
  /** Primary text, and the near-black used for solid dark buttons. */
  ink: "#111827",
  /** The single chromatic accent, used by the assessment module. */
  blue: "#3858E9",
} as const;

export type BrandColor = (typeof BRAND)[keyof typeof BRAND];
