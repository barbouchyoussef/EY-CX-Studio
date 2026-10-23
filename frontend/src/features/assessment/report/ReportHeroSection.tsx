import { ArrowLeft, Download } from "lucide-react";
import { reportCopy } from "./copy";

import type { FinalReport } from "../../../types/final-report";

type Props = {
  report: FinalReport;
  companyName?: string | null;
  onBack?: () => void;
  language?: string | null;
  /** When shown to an external client: hide consultant-only actions (Back, Add to project, Share). */
  clientView?: boolean;
};

import { getMaturityBandDisplayName, axisLabel } from "../../../utils/reportHelpers";

const DEFINITIONS = {
  en: {
    basic: "Things happen, but informally, without a defined process or clear ownership.",
    established: "A defined process exists with some accountability and tooling, but it isn't fully optimized or consistently applied everywhere.",
    advanced: "The practice is mature, consistently executed, and continuously improved as part of how the organization works.",
    listen: "This axis designates the deployment of voice of customer programs, feedback channels, data collection, and metric tracking.",
    manage: "This axis defines the organizational mechanisms that make customer experience accountable: leadership attention, ownership, governance routines, decision rights, culture, and day-to-day reinforcement.",
    analyze: "This axis designates how the organization listens to customers and turns feedback into usable understanding: feedback capture, journey visibility, cross-channel consistency, pattern recognition, and issue prioritization.",
    improve: "This axis defines how the organization acts on customer pain points and measures improvement over time: execution discipline, action ownership, metric review, validation of fixes, and continuous improvement loops."
  },
  fr: {
    basic: "Les choses se font, mais de manière informelle, sans processus défini ni responsabilité claire.",
    established: "Un processus défini existe avec une certaine responsabilité et des outils, mais il n'est pas pleinement optimisé ni appliqué de manière cohérente partout.",
    advanced: "La pratique est mature, exécutée de manière cohérente et améliorée en continu dans le cadre du fonctionnement de l'organisation.",
    listen: "Cet axe désigne le déploiement des canaux d'écoute client, la collecte continue des feedbacks et le suivi des indicateurs de performance clés.",
    manage: "Cet axe définit les mécanismes organisationnels qui responsabilisent la gestion de l'expérience client : attention de la direction, gouvernance, processus de décision, culture et valorisation de l'impact client au quotidien.",
    analyze: "Cet axe désigne la manière dont l'organisation écoute ses clients et transforme les retours en compréhension exploitable : collecte des feedbacks, vision des parcours, cohérence multicanale, analyse des causes racines et priorisation.",
    improve: "Cet axe définit la manière dont l'organisation traite les points de friction client et mesure le progrès dans le temps : rigueur d'exécution, responsabilité des actions, suivi des indicateurs, validation des correctifs et amélioration continue."
  }
};

function InfoTooltip({ explanation }: { explanation: string }) {
  if (!explanation) return null;
  return (
    <span className="relative group/info inline-flex items-center ml-2.5 print:hidden select-none">
      <svg
        viewBox="0 0 24 24"
        className="h-[15px] w-[15px] text-white/35 hover:text-white/80 transition-colors duration-150 cursor-help"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
      
      {/* Tooltip Card */}
      <span className="absolute bottom-full left-1/2 z-50 mb-3.5 w-80 -translate-x-1/2 scale-95 rounded-xl border border-white/10 bg-[#0f1117]/95 p-4 shadow-[0_12px_36px_rgba(0,0,0,0.5)] backdrop-blur-md opacity-0 transition-all duration-200 pointer-events-none group-hover/info:opacity-100 group-hover/info:scale-100">
        <span className="block text-left font-sans text-[0.92rem] leading-relaxed text-slate-200 font-medium normal-case tracking-normal">
          {explanation}
        </span>
        {/* Arrow */}
        <span className="absolute top-full left-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-[6px] rotate-45 border-r border-b border-white/10 bg-[#0f1117]/95" />
      </span>
    </span>
  );
}

function StageIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[22px] w-[22px]" aria-hidden="true">
      <path d="m12 14 4-4" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.34 19a10 10 0 1 1 17.32 0" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StrongestIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[22px] w-[22px]" aria-hidden="true">
      <path d="M7 7h10v10" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 17 17 7" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PriorityIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[22px] w-[22px]" aria-hidden="true">
      <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M12 8v8" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 12h8" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const getFirstSentence = (text?: string | null) => {
  if (!text) return "";
  const trimmed = text.trim();
  const match = trimmed.match(/^[^.!?]+[.!?](\s|$)/);
  if (match) {
    return match[0].trim();
  }
  return trimmed;
};

export default function ReportHeroSection({ report, companyName, onBack, language, clientView }: Props) {
  const hero = report.hero;
  const summary = report.summary;
  const resolvedCompany = (companyName || hero.company_name || "Executive Report").toUpperCase();

  const isFrench = language
    ? language.toLowerCase().startsWith("fr")
    : (report.quick_wins_timeline?.language?.toLowerCase().startsWith("fr") || 
       (hero.hero_message || summary.executive_summary_text || "").toLowerCase().includes("démontre") || 
       /\b(est|les|le|la|un|une|des|en|pour|dans|sur)\b/i.test((hero.hero_message || summary.executive_summary_text || "").toLowerCase()));
  const copy = reportCopy(isFrench);

  const fallbackOverview = isFrench
    ? `${resolvedCompany} est actuellement au niveau de maturité ${getMaturityBandDisplayName(hero.overall_maturity_band, true)}. L'axe ${axisLabel(hero.strongest_axis, true)} est la zone la plus forte aujourd'hui, tandis que l'axe ${axisLabel(hero.priority_axis, true)} nécessite le plus d'attention ensuite.`
    : `${resolvedCompany} is currently at ${getMaturityBandDisplayName(hero.overall_maturity_band, false)} maturity. ${axisLabel(hero.strongest_axis, false)} is the strongest area today, while ${axisLabel(hero.priority_axis, false)} needs the most attention next.`;

  const overview =
    hero.hero_message?.trim() ||
    summary.executive_summary_text?.trim() ||
    fallbackOverview;

  // Explanations for the tooltips
  const bandKey = (hero.overall_maturity_band || "").toLowerCase().trim();
  const maturityExplanation = 
    bandKey.includes("basic") || bandKey.includes("initial") || bandKey.includes("basique")
      ? (isFrench ? DEFINITIONS.fr.basic : DEFINITIONS.en.basic)
      : bandKey.includes("advanced") || bandKey.includes("avancé")
      ? (isFrench ? DEFINITIONS.fr.advanced : DEFINITIONS.en.advanced)
      : (isFrench ? DEFINITIONS.fr.established : DEFINITIONS.en.established);

  const getAxisExplanation = (axisName?: string | null) => {
    if (!axisName) return "";
    const key = axisName.toLowerCase().trim();
    if (key.includes("listen") || key.includes("écouter")) {
      return isFrench ? DEFINITIONS.fr.listen : DEFINITIONS.en.listen;
    }
    if (key.includes("analyze") || key.includes("analyser")) {
      return isFrench ? DEFINITIONS.fr.analyze : DEFINITIONS.en.analyze;
    }
    if (key.includes("manage") || key.includes("gérer")) {
      return isFrench ? DEFINITIONS.fr.manage : DEFINITIONS.en.manage;
    }
    if (key.includes("improve") || key.includes("améliorer")) {
      return isFrench ? DEFINITIONS.fr.improve : DEFINITIONS.en.improve;
    }
    return "";
  };

  const strongestExplanation = getAxisExplanation(hero.strongest_axis);
  const priorityExplanation = getAxisExplanation(hero.priority_axis);

  const overallLevelNum = hero.overall_level || 2;
  const overallMaturityBandLower = getMaturityBandDisplayName(hero.overall_maturity_band || "Established", isFrench).toLowerCase();
  
  const stageLabelText = isFrench
    ? `Sur l'échelle de 3 niveaux de maturité, vous êtes au niveau ${overallLevelNum} ${overallMaturityBandLower}`
    : `On the 3-level maturity scale, you are at level ${overallLevelNum} ${overallMaturityBandLower}`;

  const levelColors: Record<number, string> = {
    1: "#ffd447",
    2: "#00d4ff",
    3: "#7c5cff",
  };
  const activeColor = levelColors[overallLevelNum] || "#00d4ff";
  const overallMaturityBandName = getMaturityBandDisplayName(hero.overall_maturity_band || "Established", isFrench);

  const strongestLabelText = hero.strongest_axis_description || (copy.strongestAxisTooltip);

  const priorityLabelText = hero.priority_axis_description || (copy.priorityAxisTooltip);



  return (
    <section className="relative overflow-hidden px-3 py-4 text-white sm:px-6 sm:py-6 lg:px-10 lg:py-8 print:px-0 print:py-0 print:text-black">
      {/* Background gradients */}
      <div className="pointer-events-none absolute inset-0 opacity-60 print:hidden">
        <div className="absolute left-[18%] top-[28%] h-24 w-24 rounded-full bg-white/6 blur-3xl" />
        <div className="absolute left-[36%] top-[82%] h-20 w-20 rounded-full bg-white/5 blur-3xl" />
      </div>

      <div className="pointer-events-none absolute -right-[18px] top-[-82px] h-[420px] w-[420px] rounded-full border border-white/15 opacity-35 print:hidden" />
      <div className="pointer-events-none absolute right-[86px] top-7 h-[250px] w-[250px] rounded-full border border-white/15 opacity-20 print:hidden" />
      <div className="pointer-events-none absolute bottom-[92px] left-[-178px] h-[460px] w-[460px] rounded-full border border-white/15 opacity-20 print:hidden" />

      {/* 3D Logos peeking in from left and right edges */}
      <div className="pointer-events-none absolute left-[-180px] top-[10%] z-0 h-[360px] w-[360px] select-none opacity-[0.38] blur-[1px] print:hidden">
        <img
          src="/d87248c323a11fe6364ab034b73bea1e1c1e77f7.png"
          alt=""
          className="h-full w-full object-contain"
        />
      </div>
      <div className="pointer-events-none absolute right-[-180px] top-[40%] z-0 h-[360px] w-[360px] select-none opacity-[0.38] blur-[1px] print:hidden">
        <img
          src="/d87248c323a11fe6364ab034b73bea1e1c1e77f7.png"
          alt=""
          className="h-full w-full object-contain animate-[aiOrbit_90s_linear_infinite]"
        />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1320px] px-4 pb-5 pt-8 sm:px-6 lg:px-11 lg:pb-6 lg:pt-10 print:px-0 print:pt-0">
        
        {/* Sleek Split Header matching the reference image layout, themed to match ORION brand */}
        <div className="relative mb-10">

          {/* The Glassmorphic Card (z-10, backdrop-blur-xl) */}
          <div className="relative z-10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.015))] border border-white/8 rounded-[32px] p-8 md:p-10 lg:p-12 shadow-[0_24px_48px_rgba(0,0,0,0.35)] backdrop-blur-xl text-white print:bg-white print:border-black/10 print:text-black">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-8 md:gap-12">
              <div className="flex-1 min-w-0">
                <span className="font-sans text-[0.72rem] font-black uppercase tracking-[0.2em] text-ey-yellow-soft print:text-black/60">
                  {copy.heroKicker}
                </span>
                
                <h1 className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tight text-white mt-3 mb-2 print:text-black uppercase">
                  {resolvedCompany}
                </h1>
                
                {hero.sector_name && (
                  <div className="font-mono text-sm tracking-widest text-ey-yellow-soft/90 uppercase mb-4 print:text-black/70">
                    {isFrench ? `Secteur : ${hero.sector_name}` : `Sector: ${hero.sector_name}`}
                  </div>
                )}
                
                <p className="text-[1.12rem] leading-relaxed text-white/70 max-w-[62ch] print:text-black/75 font-medium">
                  {getFirstSentence(overview)}
                </p>
                
                <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
                  {onBack && !clientView && (
                    <button
                      type="button"
                      onClick={onBack}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/12 bg-white/5 px-4.5 py-2.5 text-xs font-bold text-white/90 backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white/10"
                    >
                      <ArrowLeft className="h-3.5 w-3.5" />
                      {copy.back}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="inline-flex items-center gap-2.5 rounded-xl bg-ey-yellow-soft px-6 py-3 text-sm font-bold text-[#121318] shadow-[0_8px_20px_rgba(255,212,71,0.2)] transition hover:-translate-y-0.5 hover:bg-[#e5be3f]"
                  >
                    <Download className="h-4 w-4" />
                    {copy.downloadPdfReport}
                  </button>
                </div>
              </div>

              {/* Floating Glass Orb Level Indicator on the right */}
              <div className="relative flex flex-col items-center justify-center shrink-0 self-center md:mr-6 print:hidden group/level select-none">
                
                {/* Dynamic Ambient Backlight Glow */}
                <div
                  className="absolute -inset-6 rounded-full opacity-[0.2] blur-[32px] transition-all duration-500 group-hover/level:opacity-[0.3]"
                  style={{ backgroundColor: activeColor }}
                />
                
                {/* Floating Container (synced with float keyframe) */}
                <div className="relative w-36 h-36 md:w-40 md:h-40 flex items-center justify-center animate-[aiFloat_6s_ease-in-out_infinite]">
                  
                  {/* Glassmorphic 3D Sphere */}
                  <div 
                    className="relative z-10 w-28 h-28 md:w-32 md:h-32 rounded-full border border-white/18 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.18),rgba(255,255,255,0.03)_60%,rgba(255,255,255,0)_100%)] shadow-[inset_0_4px_12px_rgba(255,255,255,0.25),0_12px_24px_rgba(0,0,0,0.4)] backdrop-blur-md flex flex-col items-center justify-center text-center transition-all duration-500"
                    style={{ 
                      boxShadow: `inset 0 4px 12px rgba(255,255,255,0.25), 0 12px 24px rgba(0,0,0,0.4), 0 0 24px ${activeColor}22` 
                    }}
                  >
                    {/* Glossy top reflection highlight */}
                    <div className="absolute top-1.5 left-1/2 -translate-x-1/2 w-12 h-6 md:w-14 md:h-7 rounded-[50%] bg-gradient-to-b from-white/20 to-transparent blur-[0.5px]" />
                    
                    <span className="font-sans text-[0.62rem] md:text-[0.68rem] font-bold uppercase tracking-[0.25em] text-white/40 leading-none">
                      {copy.heroLevel}
                    </span>
                    
                    <span className="text-4xl md:text-5xl font-black text-white leading-none my-1 tracking-tight drop-shadow-[0_2px_4px_rgba(0,0,0,0.2)]">
                      {overallLevelNum}
                    </span>
                    
                    <span
                      className="font-sans text-[0.55rem] md:text-[0.62rem] font-black uppercase tracking-[0.12em] transition-colors duration-500 text-center px-2 select-none"
                      style={{ color: activeColor }}
                    >
                      {overallMaturityBandName}
                    </span>
                  </div>

                  {/* Synced Floating Glow Ring surrounding the sphere */}
                  <div 
                    className="absolute inset-0 rounded-full border border-white/5 opacity-40 transition-all duration-500"
                    style={{ 
                      borderColor: `${activeColor}22`,
                      boxShadow: `0 0 20px ${activeColor}11`
                    }}
                  />
                </div>

                {/* Soft Elliptical Shadow underneath (synced with pulse keyframe) */}
                <div 
                  className="absolute bottom-[-10px] w-20 h-2.5 rounded-full opacity-[0.25] blur-[6px] transition-all duration-500 scale-x-125 animate-[aiPulse_6s_ease-in-out_infinite]"
                  style={{ backgroundColor: activeColor }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* 3 Premium Metric Cards starting directly here */}
        <div className="relative z-20 grid gap-6 md:grid-cols-3 w-full print:break-inside-avoid">
          
          {/* Card 1: Actual Stage */}
          <article className="flex min-h-[180px] flex-col justify-between gap-5 rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.2)] transition-all duration-300 hover:-translate-y-1 hover:border-ey-yellow-soft/30 hover:shadow-[0_20px_48px_rgba(255,212,71,0.08)] group print:border-black/10 print:bg-white print:text-black">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[linear-gradient(135deg,#ffd447_0%,#c8973f_100%)] text-white shadow-[0_12px_24px_rgba(200,151,63,0.3)] transition-transform duration-300 group-hover:scale-105">
                <StageIcon />
              </div>
              <p className="font-sans text-[0.88rem] font-black uppercase tracking-[0.1em] text-white/90 group-hover:text-white print:text-black/85">
                {copy.heroStage}
              </p>
            </div>
            <div className="min-h-[84px] flex flex-col justify-end">
              <p className="text-[clamp(1.55rem,2.4vw,2rem)] font-extrabold leading-[1.05] tracking-[-0.03em] text-white print:text-black flex items-center">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-white/70 group-hover:to-white">{getMaturityBandDisplayName(hero.overall_maturity_band, isFrench)}</span>
                <InfoTooltip explanation={maturityExplanation} />
              </p>
              <p className="mt-2 text-[0.92rem] leading-relaxed text-white/60 group-hover:text-white/80 transition-colors print:text-black/60">{stageLabelText}</p>
            </div>
          </article>

          {/* Card 2: Strongest Axis */}
          <article className="flex min-h-[180px] flex-col justify-between gap-5 rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.2)] transition-all duration-300 hover:-translate-y-1 hover:border-[#00d4ff]/30 hover:shadow-[0_20px_48px_rgba(0,212,255,0.08)] group print:border-black/10 print:bg-white print:text-black">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[linear-gradient(135deg,#85eaff_0%,#00d4ff_100%)] text-white shadow-[0_12px_24px_rgba(0,212,255,0.3)] transition-transform duration-300 group-hover:scale-105">
                <StrongestIcon />
              </div>
              <p className="font-sans text-[0.88rem] font-black uppercase tracking-[0.1em] text-white/90 group-hover:text-white print:text-black/85">
                {copy.heroStrongestAxis}
              </p>
            </div>
            <div className="min-h-[84px] flex flex-col justify-end">
              <p className="text-[clamp(1.55rem,2.4vw,2rem)] font-extrabold leading-[1.05] tracking-[-0.03em] text-white print:text-black flex items-center">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-white/70 group-hover:to-white">{axisLabel(hero.strongest_axis, isFrench)}</span>
                <InfoTooltip explanation={strongestExplanation} />
              </p>
              <p className="mt-2 text-[0.92rem] leading-relaxed text-white/60 group-hover:text-white/80 transition-colors print:text-black/60">{strongestLabelText}</p>
            </div>
          </article>

          {/* Card 3: Priority Axis */}
          <article className="flex min-h-[180px] flex-col justify-between gap-5 rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.2)] transition-all duration-300 hover:-translate-y-1 hover:border-[#9f93ff]/30 hover:shadow-[0_20px_48px_rgba(124,92,255,0.08)] group print:border-black/10 print:bg-white print:text-black">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[linear-gradient(135deg,#7c5cff_0%,#4d22df_100%)] text-white shadow-[0_12px_24px_rgba(77,34,223,0.3)] transition-transform duration-300 group-hover:scale-105">
                <PriorityIcon />
              </div>
              <p className="font-sans text-[0.88rem] font-black uppercase tracking-[0.1em] text-white/90 group-hover:text-white print:text-black/85">
                {copy.heroPriorityAxis}
              </p>
            </div>
            <div className="min-h-[84px] flex flex-col justify-end">
              <p className="text-[clamp(1.55rem,2.4vw,2rem)] font-extrabold leading-[1.05] tracking-[-0.03em] text-[#ffe4eb] print:text-black flex items-center">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#ffe4eb] via-white to-white/70 group-hover:to-white">{axisLabel(hero.priority_axis, isFrench)}</span>
                <InfoTooltip explanation={priorityExplanation} />
              </p>
              <p className="mt-2 text-[0.92rem] leading-relaxed text-white/60 group-hover:text-white/80 transition-colors print:text-black/60">{priorityLabelText}</p>
            </div>
          </article>
          
        </div>
      </div>
    </section>
  );
}
