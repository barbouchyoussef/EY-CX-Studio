/**
 * Shared helper functions for report components.
 * These were previously duplicated across CapabilitiesAxesSection,
 * ReportHeroSection, and ReportPdfDocument.
 */

export const getMaturityBandDisplayName = (band?: string | null, isFr?: boolean) => {
  if (!band) return "";
  if (!isFr) return band;
  const key = band.toLowerCase().trim();
  if (key === "basic") return "Basique";
  if (key === "established") return "Établi";
  if (key === "advanced") return "Avancé";
  return band;
};

export const getBandClass = (band?: string | null) => {
  if (!band) return "cap-tag-established";
  const key = band.toLowerCase().trim();
  if (key.includes("basic") || key.includes("basique") || key.includes("initial")) return "cap-tag-basic";
  if (key.includes("advanced") || key.includes("avancé")) return "cap-tag-advanced";
  return "cap-tag-established";
};

export const axisLabel = (value?: string | null, isFr?: boolean) => {
  if (!value) return "Unknown";
  const key = value.toLowerCase().trim();
  if (key.includes("manage") || key.includes("gérer")) return isFr ? "Gérer" : "Manage";
  if (key.includes("analyze") || key.includes("analyser")) return isFr ? "Analyser" : "Analyze";
  if (key.includes("improve") || key.includes("améliorer")) return isFr ? "Améliorer" : "Improve";
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
};

export function levelToStep(level?: number | null) {
  if (level === 3) return 3;
  if (level === 2) return 2;
  return 1;
}
