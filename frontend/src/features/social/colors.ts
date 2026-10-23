/**
 * The report's colour system.
 *
 * Colour carries two jobs and no others: SENTIMENT is a status scale (emerald / slate / rose),
 * CHANNEL is the one categorical encoding, and a channel keeps its hue everywhere it appears.
 * Topics get none — their label is always beside them, so a hue would add nothing but noise.
 *
 * CHANNEL_HUES is in a validated order, not a hand-picked one: adjacent pairs clear the
 * colourblind-separation gate a stacked bar needs, and the first three clear the stricter
 * all-pairs gate. Three sit under 3:1 against white, so charts using them ship a legend and
 * per-segment counts.
 */

export const CHANNEL_HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];

/* Not Tailwind's rose-500: tuned for small accents, it reads as an alarm across a whole ring. */
export const NEGATIVE_MARK = "#d03b3b";
export const NEUTRAL_MARK = "#cbd5e1";
export const POSITIVE_MARK = "#10b981";

export function buildChannelColors(names: string[]): Record<string, string> {
  const map: Record<string, string> = {
    "Google Maps": "#1A73E8",
    "Facebook": "#1877F2",
    "Instagram": "#E4405F",
    "Trustpilot": "#00B67A",
  };
  Array.from(new Set(names))
    .sort()
    .forEach((name, i) => {
      if (!map[name]) {
        map[name] = CHANNEL_HUES[i % CHANNEL_HUES.length];
      }
    });
  return map;
}


/* Complaint categories are distinct identities, so distinct categorical hues (not a rose ramp):
   a CVD-validated order (adjacent pairs pass every gate), with a labelled legend as the relief
   for the sub-3:1 contrast warn. "Other" always takes a neutral grey, never a categorical slot. */
export const CATEGORY_HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]; // blue·orange·aqua·yellow·magenta
export const OTHER_HUE = "#94a3b8";
