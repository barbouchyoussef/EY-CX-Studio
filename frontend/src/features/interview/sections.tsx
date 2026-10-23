/**
 * How each interview section is presented: its title, icon, colours and expected duration.
 *
 * This is a table, not logic. It sat inline in the hub and was rebuilt on every render, which made
 * a 60-line block of styling look like part of the component's behaviour. Adding a section, or
 * restyling one, is now an edit here and nowhere else.
 *
 * The durations are the consultant's planning aid -- they are what the guide claims the interview
 * will take, so they add up to the 49 minutes quoted to the client.
 */

import { Flag, Layers, Search, Users, Wrench } from "lucide-react";

import { SECTION_KEYS, type SectionKey } from "./guide";

export type InterviewSectionPresentation = {
  key: SectionKey;
  title: string;
  icon: React.ReactNode;
  accentColor: string;
  borderColor: string;
  bgColor: string;
  iconBg: string;
  badgeBg: string;
  duration: string;
};

type SectionStyle = Omit<InterviewSectionPresentation, "key" | "title"> & {
  titleFr: string;
  titleEn: string;
};

const SECTION_STYLES: Record<SectionKey, SectionStyle> = {
  introduction: {
    titleFr: "Introduction & État Général",
    titleEn: "Warm-up & General State",
    icon: <Users className="h-4 w-4" />,
    accentColor: "slate",
    borderColor: "border-slate-200",
    bgColor: "bg-slate-50",
    iconBg: "bg-slate-100 text-slate-600",
    badgeBg: "bg-slate-800",
    duration: "5 min",
  },
  manage: {
    titleFr: "Pilotage / Manage",
    titleEn: "Governance / Manage",
    icon: <Layers className="h-4 w-4" />,
    accentColor: "yellow",
    borderColor: "border-yellow-200",
    bgColor: "bg-yellow-50/40",
    iconBg: "bg-yellow-100 text-yellow-700",
    badgeBg: "bg-yellow-500",
    duration: "12 min",
  },
  analyze: {
    titleFr: "Analyse / Analyze",
    titleEn: "Analysis / Analyze",
    icon: <Search className="h-4 w-4" />,
    accentColor: "blue",
    borderColor: "border-blue-200",
    bgColor: "bg-blue-50/40",
    iconBg: "bg-blue-100 text-blue-700",
    badgeBg: "bg-blue-500",
    duration: "15 min",
  },
  improve: {
    titleFr: "Amélioration / Improve",
    titleEn: "Improvement / Improve",
    icon: <Wrench className="h-4 w-4" />,
    accentColor: "emerald",
    borderColor: "border-emerald-200",
    bgColor: "bg-emerald-50/40",
    iconBg: "bg-emerald-100 text-emerald-700",
    badgeBg: "bg-emerald-500",
    duration: "12 min",
  },
  closure: {
    titleFr: "Clôture",
    titleEn: "Closure",
    icon: <Flag className="h-4 w-4" />,
    accentColor: "violet",
    borderColor: "border-violet-200",
    bgColor: "bg-violet-50/40",
    iconBg: "bg-violet-100 text-violet-700",
    badgeBg: "bg-violet-500",
    duration: "5 min",
  },
};

/** The five sections in interview order, titled in the guide's language. */
export function interviewSections(isFrench: boolean): InterviewSectionPresentation[] {
  return SECTION_KEYS.map((key) => {
    const { titleFr, titleEn, ...style } = SECTION_STYLES[key];
    return { key, title: isFrench ? titleFr : titleEn, ...style };
  });
}
