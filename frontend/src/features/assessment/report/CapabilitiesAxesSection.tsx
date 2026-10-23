import { useEffect, useMemo, useState } from "react";
import { reportCopy } from "./copy";
import type { FinalReportHero, FinalReportWorkingMissingAxis, FinalReportWorkingMissingItem, FinalReportCapabilityItem } from "../../../types/final-report";
import { getMaturityBandDisplayName, getBandClass, axisLabel, levelToStep } from "../../../utils/reportHelpers";
import MaturityRadarChart from "./MaturityRadarChart";
import MaturityStepper from "./MaturityStepper";
import EvidenceModal from "./EvidenceModal";
import CapabilityButton from "./CapabilityButton";
import "./capabilitiesAxesSection.css";

type Props = {
  hero: FinalReportHero;
  axes: FinalReportWorkingMissingAxis[];
  language?: string | null;
  summaryText?: string | null;
  capabilities?: FinalReportCapabilityItem[];
};

type ModalState = {
  item: FinalReportWorkingMissingItem;
  status: "working" | "missing";
  axisLabel: string;
} | null;

export default function CapabilitiesAxesSection({ hero, axes, language, summaryText, capabilities }: Props) {
  const isFrench = language
    ? language.toLowerCase().startsWith("fr")
    : ((hero.overall_maturity_band || "").toLowerCase().includes("établi") || 
       (hero.overall_maturity_band || "").toLowerCase().includes("basique") || 
       (hero.overall_maturity_band || "").toLowerCase().includes("avancé") || 
       (hero.overall_maturity_band || "").toLowerCase().includes("intermédiaire") ||
       (hero.report_title || "").toLowerCase().includes("rapport") ||
       (hero.report_title || "").toLowerCase().includes("maturité"));
  const copy = reportCopy(isFrench);

  const normalizedAxes = useMemo(() => {
    const order = ["manage", "analyze", "improve"];
    const lookup = new Map(axes.map((axis) => [axis.axis.toLowerCase(), axis]));
    return order.map((key) => lookup.get(key)).filter(Boolean) as FinalReportWorkingMissingAxis[];
  }, [axes]);

  // The axis the reader picked, remembered rather than reset.
  //
  // This used to be re-set from an effect whenever `normalizedAxes` changed. That memo depends on
  // the `axes` prop, so any parent re-render handing down a fresh array snapped the reader back
  // to Manage mid-read -- an identity change, not a content change. Falling back only when the
  // chosen axis is genuinely gone keeps the selection and still survives the data changing.
  const [pickedAxis, setPickedAxis] = useState<string | null>(null);
  const activeAxis =
    normalizedAxes.some((a) => a.axis === pickedAxis)
      ? (pickedAxis as string)
      : (normalizedAxes[0]?.axis ?? "manage");
  const setActiveAxis = setPickedAxis;
  const [modalState, setModalState] = useState<ModalState>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setModalState(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (modalState) {
      document.documentElement.style.overflow = "hidden";
    } else {
      document.documentElement.style.overflow = "";
    }
    return () => {
      document.documentElement.style.overflow = "";
    };
  }, [modalState]);

  const currentStep = levelToStep(hero.overall_level);
  
  const overview = useMemo(() => {
    const resolvedCompany = (hero.company_name || "Executive Report").toUpperCase();
    const fallbackOverview = isFrench
      ? `${resolvedCompany} est actuellement au niveau de maturité ${getMaturityBandDisplayName(hero.overall_maturity_band, true)}. L'axe ${axisLabel(hero.strongest_axis, true)} est la zone la plus forte aujourd'hui, tandis que l'axe ${axisLabel(hero.priority_axis, true)} nécessite le plus d'attention ensuite.`
      : `${resolvedCompany} is currently at ${getMaturityBandDisplayName(hero.overall_maturity_band, false)} maturity. ${axisLabel(hero.strongest_axis, false)} is the strongest area today, while ${axisLabel(hero.priority_axis, false)} needs the most attention next.`;

    return (
      hero.hero_message?.trim() ||
      summaryText?.trim() ||
      fallbackOverview
    );
  }, [hero, summaryText, isFrench]);

  const sentences = useMemo(() => {
    if (!overview) return [];
    return overview
      .split(/[.!?]\s+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 3)
      .map((s) => (s.endsWith(".") || s.endsWith("!") || s.endsWith("?") ? s : s + "."));
  }, [overview]);

  const formatSentence = (s: string) => {
    const words = s.split(/\s+/);
    const boldCount = Math.min(4, words.length);
    const boldPart = words.slice(0, boldCount).join(" ");
    const restPart = words.slice(boldCount).join(" ");
    return { boldPart, restPart };
  };

  const activePanel = normalizedAxes.find((axis) => axis.axis === activeAxis) ?? normalizedAxes[0];

  return (
    <div className="report-orbit-shell">
      <div className="hero-glow-layer" aria-hidden="true">
        <div className="hero-glow-a"></div>
        <div className="hero-glow-b"></div>
      </div>

      {/* 3D Logos peeking in from left and right edges */}
      <div className="pointer-events-none absolute left-[-180px] top-[15%] z-0 h-[360px] w-[360px] select-none opacity-[0.38] blur-[1px] print:hidden">
        <img
          src="/d87248c323a11fe6364ab034b73bea1e1c1e77f7.png"
          alt=""
          className="h-full w-full object-contain animate-[aiOrbit_90s_linear_infinite]"
        />
      </div>
      <div className="pointer-events-none absolute right-[-180px] top-[50%] z-0 h-[360px] w-[360px] select-none opacity-[0.38] blur-[1px] print:hidden">
        <img
          src="/d87248c323a11fe6364ab034b73bea1e1c1e77f7.png"
          alt=""
          className="h-full w-full object-contain"
        />
      </div>

      <section className="section">
        <div className="orbital-ring" aria-hidden="true"></div>
        <div className="orbital-ring-small" aria-hidden="true"></div>
        <div className="orbital-ring-left" aria-hidden="true"></div>

        <div className="section-head">
          <span className="section-number">02</span>
          <h2 className="section-title">
            {copy.whereYouStand}
          </h2>
        </div>

        <MaturityStepper currentStep={currentStep} isFrench={isFrench} />

        {/* Executive summary and Radar Chart dashboard */}
        {sentences.length > 0 && (
          <div className="mt-12 md:mt-16 relative z-10 mx-auto max-w-[1140px] print:text-black">
            {/* Unified Glassmorphic Card */}
            <div className="bg-[linear-gradient(180deg,rgba(255,255,255,0.035),rgba(255,255,255,0.01))] border border-white/6 rounded-[32px] p-8 md:p-10 shadow-[0_20px_50px_rgba(0,0,0,0.3)] backdrop-blur-md print:bg-white print:border-black/10 print:shadow-none print:backdrop-blur-none print:p-0">
              <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-8 lg:gap-16 items-center">
                
                {/* Left Column: Key Findings */}
                <div>
                  {/* Header/Subtitle */}
                  <div className="flex items-center gap-3 mb-6 px-1 print:hidden">
                    <div className="h-1.5 w-1.5 rounded-full bg-ey-yellow-soft animate-pulse" />
                    <span className="font-mono text-[0.74rem] uppercase tracking-[0.2em] text-white/50">
                      {copy.keyFindings}
                    </span>
                  </div>

                  <div className="space-y-6 print:space-y-4">
                    {sentences.map((sentence, idx) => {
                      const { boldPart, restPart } = formatSentence(sentence);
                      return (
                        <div key={idx} className="flex items-start gap-4 group print:text-black">
                          <div className="flex-shrink-0 mt-1.5 flex h-[22px] w-[22px] items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_12px_rgba(16,185,129,0.1)] transition-all duration-300 group-hover:scale-110 group-hover:bg-emerald-500/20 group-hover:border-emerald-500/35 group-hover:text-emerald-300 print:bg-emerald-50 print:border-emerald-200 print:text-emerald-600 print:shadow-none print:h-5 print:w-5 print:mt-1">
                            <svg
                              viewBox="0 0 24 24"
                              className="h-2.5 w-2.5 print:h-2 print:w-2"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="3.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          </div>
                          <p className="text-[1.02rem] leading-relaxed text-white/70 transition-colors duration-200 group-hover:text-white/90 m-0 print:text-black/85">
                            <strong className="font-bold text-white transition-colors duration-200 print:text-black">{boldPart}</strong>{" "}
                            {restPart}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right Column: Radar Chart */}
                <div className="flex flex-col items-center justify-center print:hidden">
                  {/* Header/Subtitle */}
                  <div className="flex items-center gap-3 mb-6 px-1 w-full justify-center lg:justify-start">
                    <div className="h-1.5 w-1.5 rounded-full bg-ey-yellow-soft animate-pulse" />
                    <span className="font-mono text-[0.74rem] uppercase tracking-[0.2em] text-white/50">
                      {copy.maturityProfile}
                    </span>
                  </div>

                  {/* Radar Container - border-less and background-less inside the parent card */}
                  <div className="flex items-center justify-center w-full max-w-[500px] aspect-[480/320]">
                    <MaturityRadarChart axes={axes} capabilities={capabilities} isFrench={isFrench} />
                  </div>
                </div>

              </div>
            </div>
          </div>
        )}
      </section>

      <section className="section">
        <div className="orbital-ring" aria-hidden="true"></div>
        <div className="orbital-ring-small" aria-hidden="true"></div>
        <div className="orbital-ring-left" aria-hidden="true"></div>

        <div className="section-head">
          <span className="section-number">03</span>
          <h2 className="section-title">
            {copy.workingMissingTitle}
          </h2>
        </div>

        <div className="panel">
          <div className="panel-inner">
            <div className="axis-tabs" id="axis-tabs">
              {normalizedAxes.map((axis, index) => (
                <button
                  key={axis.axis}
                  className={`axis-tab ${axis.axis === activeAxis ? "active" : ""}`}
                  data-axis={axis.axis}
                  type="button"
                  onClick={() => setActiveAxis(axis.axis)}
                >
                  <div className="axis-kicker">
                    {copy.axisPrefix}{String(index + 1).padStart(2, "0")}
                  </div>
                  <h2 className="axis-name">{axis.label}</h2>
                  <p className="axis-mini">{axis.subtitle}</p>
                  <div className="axis-score-row">
                    <div className="axis-score">{levelToStep(axis.axis_level)}/3</div>
                    <div className="axis-band">{getMaturityBandDisplayName(axis.maturity_band, isFrench)}</div>
                  </div>
                </button>
              ))}
            </div>

            <div id="axis-panels" className="print:hidden">
              {normalizedAxes.map((axis) => (
                <section
                  key={axis.axis}
                  className={`axis-panel ${axis.axis === activeAxis ? "active" : ""}`}
                  data-panel={axis.axis}
                >
                  <div className="axis-panel-head">
                    <div>
                      <h3 className="axis-panel-title">
                        {axis.label}{copy.axisSuffix}
                      </h3>
                      <p className="axis-panel-copy">{axis.intro}</p>
                    </div>
                  </div>

                  <div className="axis-grid">
                    <div className="cap-col working">
                      <div className="cap-col-head">
                        <div>
                          <div className="cap-title-row">
                            <div className="status-icon working" aria-hidden="true">
                              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            </div>
                            <h4 className="cap-col-title">{copy.working}</h4>
                          </div>
                          <p className="cap-col-sub">
                            {copy.workingLead}
                          </p>
                        </div>
                        <div className="cap-count">{axis.working.length}</div>
                      </div>
                      <div className="cap-list">
                        {axis.working.map((item) => (
                          <CapabilityButton
                            key={`${axis.axis}-working-${item.capability}`}
                            item={item}
                            status="working"
                            axisLabel={axis.label}
                            onOpen={setModalState}
                            isFrench={isFrench}
                          />
                        ))}
                      </div>
                    </div>

                    <div className="cap-col missing">
                      <div className="cap-col-head">
                        <div>
                          <div className="cap-title-row">
                            <div className="status-icon missing" aria-hidden="true">
                              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                              </svg>
                            </div>
                            <h4 className="cap-col-title">{copy.missing}</h4>
                          </div>
                          <p className="cap-col-sub">
                            {copy.missingLead}
                          </p>
                        </div>
                        <div className="cap-count">{axis.missing.length}</div>
                      </div>
                      <div className="cap-list">
                        {axis.missing.map((item) => (
                          <CapabilityButton
                            key={`${axis.axis}-missing-${item.capability}`}
                            item={item}
                            status="missing"
                            axisLabel={axis.label}
                            onOpen={setModalState}
                            isFrench={isFrench}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              ))}
            </div>

            <div className="print-axis-list hidden">
              {normalizedAxes.map((axis) => (
                <section key={`print-${axis.axis}`} className="print-axis-card">
                  <div className="axis-kicker">{copy.axisLabel}</div>
                  <h3 className="axis-panel-title">{axis.label}</h3>
                  <p className="print-axis-copy">{axis.intro}</p>
                  <div className="print-axis-grid">
                    <div className="cap-col working">
                      <div className="cap-col-head">
                        <div>
                          <div className="cap-title-row">
                            <div className="status-icon working" aria-hidden="true">
                              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            </div>
                            <h4 className="cap-col-title">{copy.working}</h4>
                          </div>
                          <p className="cap-col-sub">
                            {copy.workingLead}
                          </p>
                        </div>
                      </div>
                      <div className="cap-list">
                        {axis.working.map((item) => (
                          <div key={`print-${axis.axis}-working-${item.capability}`} className="cap-pill">
                            <div className="cap-pill-top">
                              <p className="cap-pill-name">{item.capability}</p>
                              <span className={`cap-tag ${getBandClass(item.maturity_band)}`}>{getMaturityBandDisplayName(item.maturity_band, isFrench)}</span>
                            </div>
                            <p className="cap-pill-summary">{item.summary}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="cap-col missing">
                      <div className="cap-col-head">
                        <div>
                          <div className="cap-title-row">
                            <div className="status-icon missing" aria-hidden="true">
                              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                              </svg>
                            </div>
                            <h4 className="cap-col-title">{copy.missing}</h4>
                          </div>
                          <p className="cap-col-sub">
                            {copy.missingLead}
                          </p>
                        </div>
                      </div>
                      <div className="cap-list">
                        {axis.missing.map((item) => (
                          <div key={`print-${axis.axis}-missing-${item.capability}`} className="cap-pill">
                            <div className="cap-pill-top">
                              <p className="cap-pill-name">{item.capability}</p>
                              <span className={`cap-tag ${getBandClass(item.maturity_band)}`}>{getMaturityBandDisplayName(item.maturity_band, isFrench)}</span>
                            </div>
                            <p className="cap-pill-summary">{item.summary}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Evidence modal */}
      <EvidenceModal modalState={modalState} onClose={() => setModalState(null)} isFrench={isFrench} />

      {!activePanel && null}
    </div>
  );
}
