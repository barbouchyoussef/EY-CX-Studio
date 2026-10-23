/**
 * Static configuration data for maturity levels and capabilities.
 * Extracted from CapabilitiesAxesSection for reuse and cleaner separation.
 */

export const MATURITY_CARDS = {
  en: {
    1: {
      title: "Basic",
      desc: "Things happen, but informally, without a defined process or clear ownership.",
      tooltip: ""
    },
    2: {
      title: "Established",
      desc: "A defined process exists with some accountability and tooling, but it isn't fully optimized or consistently applied everywhere.",
      tooltip: ""
    },
    3: {
      title: "Advanced",
      desc: "The practice is mature, consistently executed, and continuously improved as part of how the organization works.",
      tooltip: ""
    },
    yourPosition: "Your position"
  },
  fr: {
    1: {
      title: "Basique",
      desc: "Les choses se font, mais de manière informelle, sans processus défini ni responsabilité claire.",
      tooltip: ""
    },
    2: {
      title: "Intermédiaire",
      desc: "Un processus défini existe avec une certaine responsabilité et des outils, mais il n'est pas pleinement optimisé ni appliqué de manière cohérente partout.",
      tooltip: ""
    },
    3: {
      title: "Avancé",
      desc: "La pratique est mature, exécutée de manière cohérente et améliorée en continu dans le cadre du fonctionnement de l'organisation.",
      tooltip: ""
    },
    yourPosition: "Votre position"
  }
};

export const STATIC_CAPABILITIES = [
  { key: "cx culture", axis: "manage", en: "Customer experience culture", fr: "Culture de l'expérience client" },
  { key: "ownership and governance", axis: "manage", en: "Ownership & governance", fr: "Ownership & gouvernance" },
  { key: "decision-making", axis: "manage", en: "Decision-making", fr: "Prise de décision" },
  { key: "feedback collection", axis: "analyze", en: "Feedback collection", fr: "Collecte des retours" },
  { key: "use of insights", axis: "analyze", en: "Use of insights", fr: "Exploitation des insights" },
  { key: "channel consistency", axis: "analyze", en: "Channel consistency", fr: "Cohérence des canaux" },
  { key: "journey visibility", axis: "analyze", en: "Journey visibility", fr: "Visibilité des parcours" },
  { key: "measurement and continuous improvement", axis: "improve", en: "Measurement & improvement", fr: "Mesure & amélioration" },
  { key: "acting on pain points", axis: "improve", en: "Acting on pain points", fr: "Traitement des irritants" }
] as const;

export function getCanonicalCapabilityKey(name: string): string {
  const norm = name.toLowerCase().trim();
  if (norm.includes("culture")) return "cx culture";
  if (norm.includes("decision") || norm.includes("décision")) return "decision-making";
  if (norm.includes("governance") || norm.includes("gouvernance") || norm.includes("ownership")) return "ownership and governance";
  if (norm.includes("feedback") || norm.includes("collecte des retours") || norm.includes("collection")) return "feedback collection";
  if (norm.includes("insights") || norm.includes("exploitation")) return "use of insights";
  if (norm.includes("channel") || norm.includes("canal") || norm.includes("canaux") || norm.includes("cohérence")) return "channel consistency";
  if (norm.includes("journey") || norm.includes("parcours") || norm.includes("visibilité")) return "journey visibility";
  if (norm.includes("measurement") || norm.includes("mesure") || norm.includes("continuous") || norm.includes("amélioration continue")) return "measurement and continuous improvement";
  if (norm.includes("acting on") || norm.includes("irritant") || norm.includes("pain point")) return "acting on pain points";
  return norm;
}

export function getMaturityScore(maturityBand: string, maturityLevelNumber?: number | null): number {
  if (maturityLevelNumber) return maturityLevelNumber;
  const bandNorm = maturityBand.toLowerCase();
  if (bandNorm.includes("advanced") || bandNorm.includes("avancé")) return 3;
  if (bandNorm.includes("basic") || bandNorm.includes("basique")) return 1;
  return 2;
}
