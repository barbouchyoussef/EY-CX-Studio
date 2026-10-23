/**
 * The five module cards on the services hub.
 *
 * Each carries its own miniature preview -- a fake progress bar, a fake sentiment split -- so the
 * hub shows what a module produces rather than describing it. That is what makes this long: it is
 * illustration, not logic.
 *
 * Kept out of the hub because it was 141 lines sitting between the component's props and its
 * first hook, rebuilt on every render, and because a card's wording, colour and preview are the
 * thing most likely to be edited without touching anything else.
 */

import type { ReactNode } from "react";
import { BRAND } from "../../lib/brand";
import { ClipboardList, FileSearch, Gauge, ListChecks, Quote, Radar } from "lucide-react";

export type HubCard = {
  step: number;
  title: string;
  desc: string;
  cta: string;
  onClick?: () => void;
  comingSoon?: boolean;
  iconBg: string;
  iconColor: string;
  ctaColor: string;
  icon: ReactNode;
  preview: ReactNode;
};


/** What each card needs from the hub: its copy, and where its button goes. */
type CardCopy = Record<string, string>;

type CardHandlers = {
  onOpenAssessment: () => void;
  onOpenInterviewHub: () => void;
  onOpenSocialScraping: () => void;
  onOpenDeskResearch: () => void;
  /** The issue log is reached by route rather than a launcher callback, like the other four. */
  onNavigate?: (path: string) => void;
};

export function hubCards(t: CardCopy, handlers: CardHandlers): HubCard[] {
return [
  {
    step: 1,
    title: t.assessmentTitle,
    desc: t.assessmentDesc,
    cta: t.assessmentCta,
    onClick: handlers.onOpenAssessment,
    iconBg: "bg-[#EEF2FF]",
    iconColor: "text-ey-blue",
    ctaColor: "text-ey-blue",
    icon: <Gauge className="h-6 w-6" aria-hidden="true" />,
    preview: (
      <div className="space-y-2.5">
        {[
          { label: t.axisManage, value: 62, color: BRAND.gold },
          { label: t.axisAnalyze, value: 78, color: BRAND.blue },
          { label: t.axisImprove, value: 54, color: "#2D7A3A" },
        ].map((row) => (
          <div key={row.label}>
            <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-slate-500">
              <span>{row.label}</span>
              <span>{row.value}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200/70">
              <div
                className="h-full rounded-full"
                style={{ width: `${row.value}%`, backgroundColor: row.color }}
              />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    step: 2,
    title: t.interviewTitle,
    desc: t.interviewDesc,
    cta: t.interviewCta,
    onClick: handlers.onOpenInterviewHub,
    iconBg: "bg-[#FBF3E1]",
    iconColor: "text-ey-gold",
    ctaColor: "text-ey-gold",
    icon: <ClipboardList className="h-6 w-6" aria-hidden="true" />,
    preview: (
      <div>
        <Quote className="h-4 w-4 text-ey-gold" aria-hidden="true" />
        <p className="mt-2 text-[12px] italic leading-relaxed text-slate-600">{t.sampleQuestion}</p>
        <span className="mt-2.5 inline-flex items-center rounded-full bg-[#FBF3E1] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-ey-gold-deep">
          {t.followUpTag}
        </span>
      </div>
    ),
  },
  {
    step: 3,
    title: t.scrapingTitle,
    desc: t.scrapingDesc,
    cta: t.scrapingCta,
    onClick: handlers.onOpenSocialScraping,
    iconBg: "bg-[#F0F9F2]",
    iconColor: "text-[#2D7A3A]",
    ctaColor: "text-[#2D7A3A]",
    icon: <Radar className="h-6 w-6" aria-hidden="true" />,
    preview: (
      <div className="space-y-2.5">
        {[
          { label: t.positive, value: 64, color: "#10b981" },
          { label: t.neutral, value: 21, color: "#94a3b8" },
          { label: t.negative, value: 15, color: "#f43f5e" },
        ].map((row) => (
          <div key={row.label}>
            <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-slate-500">
              <span>{row.label}</span>
              <span>{row.value}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200/70">
              <div
                className="h-full rounded-full"
                style={{ width: `${row.value}%`, backgroundColor: row.color }}
              />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    step: 4,
    title: t.deskResearchTitle,
    desc: t.deskResearchDesc,
    cta: t.deskResearchCta,
    onClick: handlers.onOpenDeskResearch,
    iconBg: "bg-[#F3F0FF]",
    iconColor: "text-[#7C3AED]",
    ctaColor: "text-[#7C3AED]",
    icon: <FileSearch className="h-6 w-6" aria-hidden="true" />,
    preview: (
      <div>
        <div className="flex flex-wrap gap-2">
          {["PDF", "XLSX", "PPTX", "DOCX"].map((ext) => (
            <span
              key={ext}
              className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-500"
            >
              {ext}
            </span>
          ))}
        </div>
        <p className="mt-2.5 text-[11px] text-slate-400">Upload → Parse → AI Synthesis</p>
      </div>
    ),
  },
  {
    step: 5,
    title: t.issueLogTitle,
    desc: t.issueLogDesc,
    cta: t.issueLogCta,
    onClick: () => handlers.onNavigate?.("/issue-log"),
    comingSoon: false,
    iconBg: "bg-ey-yellow/20",
    iconColor: "text-ey-gold-deep",
    ctaColor: "text-slate-400",
    icon: <ListChecks className="h-6 w-6" aria-hidden="true" />,
    preview: (
      <div>
        <div className="flex items-center gap-1.5">
          {[BRAND.blue, BRAND.gold, "#10b981", "#7C3AED"].map((c, idx) => (
            <div key={idx} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
              {idx < 3 && <span className="h-px w-3 bg-slate-300" />}
            </div>
          ))}
          <span className="mx-1 text-slate-300">→</span>
          <ListChecks className="h-4 w-4 text-ey-gold-deep" />
        </div>
        <p className="mt-2.5 text-[11px] text-slate-400">{t.issueLogPreviewCaption}</p>
      </div>
    ),
  },
];
}
