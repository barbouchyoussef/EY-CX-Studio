/**
 * The brand palette is written twice on purpose, and this is what stops the two drifting.
 *
 * `index.css` declares it as Tailwind theme tokens so markup can say `bg-ey-gold`.
 * `src/lib/brand.ts` declares it as JavaScript values for the places a class name cannot reach —
 * chart series, and helpers like hexToRgba that parse the hex rather than render it.
 *
 * CSS custom properties are not readable from JS without a DOM, so the two cannot share one
 * source. They can be checked against each other, which is what this does.
 */

import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");
const ts = readFileSync(new URL("../src/lib/brand.ts", import.meta.url), "utf8");

/** Which key in BRAND corresponds to which CSS token. */
const PAIRS = {
  gold: "ey-gold",
  goldDeep: "ey-gold-deep",
  yellow: "ey-yellow",
  navy: "ey-navy",
  ink: "ink",
  blue: "ey-blue",
};

const HEX = "(#[0-9A-Fa-f]{6})";

function cssValue(token) {
  const found = css.match(new RegExp("--color-" + token + ":\\s*" + HEX));
  return found ? found[1].toUpperCase() : null;
}

function tsValue(key) {
  const found = ts.match(new RegExp("\\b" + key + ':\\s*"' + HEX + '"'));
  return found ? found[1].toUpperCase() : null;
}

const problems = [];
for (const [key, token] of Object.entries(PAIRS)) {
  const inCss = cssValue(token);
  const inTs = tsValue(key);
  if (!inCss) problems.push(`index.css has no --color-${token}`);
  else if (!inTs) problems.push(`brand.ts has no ${key}`);
  else if (inCss !== inTs) problems.push(`${key}: brand.ts ${inTs} vs --color-${token} ${inCss}`);
}

if (problems.length) {
  console.error("Brand palette out of step:");
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}
console.log(
  `brand palette: ${Object.keys(PAIRS).length} colours match between index.css and brand.ts`,
);
