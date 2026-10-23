import { Sparkles, Wand2, ArrowUpRight, Bot, Cpu } from "lucide-react";
import { BRAND } from "../../../lib/brand";
import { pickCopy } from "../../../lib/i18n";
import { useEffect, useRef, useState } from "react";
import FadeUp from "../../../components/FadeUp";

type CoreFeaturesShowcaseProps = {
  language?: string;
};

const TRANSLATIONS = {
  fr: {
    headingPart1: "Vous ne cherchez pas des réponses,",
    headingPart2: "vous cherchez de la clarté.",
    subHeadingPart1: "Vous ne repartez pas avec un score,",
    subHeadingPart2: "vous repartez avec une feuille de route.",
    lead: "À l'issue du diagnostic, notre plateforme structure l'ensemble de vos retours pour dresser une cartographie fidèle et actionnable de votre organisation.",
    features: [
      {
        step: "1",
        title: "Niveau de maturité",
        subtitle: "L'état actuel de votre gestion de l'expérience",
        desc: "Une évaluation précise de votre positionnement sur l'ensemble des dimensions clés.",
      },
      {
        step: "2",
        title: "Diagnostic structurel",
        subtitle: "Identification des zones de friction et de blocage",
        desc: "Comprendre précisément ce qui freine vos initiatives et limite vos performances.",
      },
      {
        step: "3",
        title: "Plan d'action priorisé",
        subtitle: "Des actions adaptées à votre contexte",
        desc: "Les leviers d'amélioration stratégiques à activer en priorité pour maximiser votre impact.",
      },
    ],
    resultsSnapshot: "Aperçu du diagnostic",
    strengths: "Forces",
    painPoints: "Points de friction",
    priorities: "Priorités",
    guidedResults: "Restitution guidée",
    builtForDecisionMaking: "Aide à la décision",
    overallPercentage: "68% global",
    scoreRows: [
      ["Stratégie & gouvernance", "62%", BRAND.gold],
      ["Compréhension client", "78%", "#2D7A3A"],
      ["Design de parcours", "51%", "#EAAA08"],
      ["Mesures & KPIs", "68%", BRAND.blue],
    ],
    benchmarkInsight: "Analyse comparative",
    benchmarkText: "Vos performances clés se rapprochent des leaders du secteur",
    benchmarkPts: "+12 pts",
    peerMedian: "Médiane sectorielle",
    bestInClass: "Meilleur de sa catégorie",
    recommendedFocus: "Actions prioritaires",
    recommendationText: "Le diagnostic centralise vos priorités majeures en un seul endroit pour aligner rapidement vos équipes sur les premières actions.",
  },
  en: {
    headingPart1: "You don’t leave with answers",
    headingPart2: "You leave with clarity",
    subHeadingPart1: "You don’t leave with a score",
    subHeadingPart2: "You leave with a strategy",
    lead: "At the end of the conversation, the platform synthesizes everything into a structured picture of where your organization truly stands.",
    features: [
      {
        step: "1",
        title: "A maturity signal",
        subtitle: "How your experience is currently managed",
        desc: "Where you stand today, across every dimension that matters.",
      },
      {
        step: "2",
        title: "A structural diagnosis",
        subtitle: "Where data supports or limits your decisions",
        desc: "What’s holding your organization back, and why.",
      },
      {
        step: "3",
        title: "Clear priorities, not generic advice",
        subtitle: "Which levers can create real impact",
        desc: "The exact levers to pull first, based on your specific context.",
      },
    ],
    resultsSnapshot: "Results snapshot",
    strengths: "Strengths",
    painPoints: "Pain points",
    priorities: "Priorities",
    guidedResults: "Guided results",
    builtForDecisionMaking: "Built for decision-making",
    overallPercentage: "68% overall",
    scoreRows: [
      ["Strategy & governance", "62%", BRAND.gold],
      ["Customer understanding", "78%", "#2D7A3A"],
      ["Journey design", "51%", "#EAAA08"],
      ["Measurement", "68%", BRAND.blue],
    ],
    benchmarkInsight: "Benchmark insight",
    benchmarkText: "Your strongest capabilities are approaching sector leaders",
    benchmarkPts: "+12 pts",
    peerMedian: "Peer median",
    bestInClass: "Best-in-class",
    recommendedFocus: "Recommended focus",
    recommendationText: "The results bring the most important priorities into one place, making it easier to align on where action should begin.",
  },
};

export default function CoreFeaturesShowcase({ language = "en" }: CoreFeaturesShowcaseProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);
  const t = pickCopy(TRANSLATIONS, language);

  useEffect(() => {
    const node = sectionRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.25 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="summary" ref={sectionRef} className="bg-white py-16 sm:py-20 lg:py-24 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          {/* LEFT */}
          <div>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-slate-900 leading-[1.15]">
              {t.headingPart1} <span className="block text-slate-950">{t.headingPart2}</span>
            </h2>
            <p className="mt-3 text-xl md:text-2xl font-semibold text-slate-500">
              {t.subHeadingPart1} <span className="text-slate-500">{t.subHeadingPart2}</span>
            </p>
            <p className="text-base text-gray-600 mb-8 mt-4 leading-relaxed">
              {t.lead}
            </p>

            <div className="mt-10 space-y-8">
              {t.features.map(item => (
                <div key={item.step} className="flex gap-5">
                  <div className="shrink-0">
                    <div className="h-11 w-11 rounded-full bg-indigo-600 text-white flex items-center justify-center font-semibold">
                      {item.step}
                    </div>
                  </div>

                  <div className="min-w-0">
                    <div className="text-lg font-bold text-gray-900 leading-none">{item.title}</div>
                    <p className="mt-2 text-sm font-semibold text-slate-800 leading-snug">{item.subtitle}</p>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-gray-500 max-w-xl font-normal">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* RIGHT */}
          <div className="mt-12 lg:mt-0">
            <FadeUp delay="delay-2">
              <div className="relative min-h-[100px] md:min-h-[430px]">
                <div className="absolute -left-2 -top-10 z-20 hidden lg:block">
                  <div className="relative mx-auto flex h-[12rem] w-[12rem] items-center justify-center md:mx-0">
                    <div className="absolute inset-0 rounded-full border border-ey-blue/12" />
                    <div className="absolute inset-4 rounded-full border border-[#E5E7EB] bg-white/35 backdrop-blur-[2px]" />
                    <div className="absolute inset-1 rounded-full border border-ey-gold/18" style={{ animation: "aiOrbit 16s linear infinite" }}>
                      <span className="absolute left-6 top-5 h-2.5 w-2.5 rounded-full bg-ey-blue" />
                      <span className="absolute bottom-6 right-5 h-2.5 w-2.5 rounded-full bg-ey-gold" />
                    </div>
                    <div className="absolute inset-7 rounded-full border border-ey-blue/10" style={{ animation: "aiOrbit 11s linear infinite reverse" }}>
                      <span className="absolute bottom-5 left-8 h-2.5 w-2.5 rounded-full bg-[#2D7A3A]" />
                    </div>
                    <div className="absolute bottom-5 h-16 w-36 rounded-full bg-ey-blue/12 blur-2xl" style={{ animation: "aiPulse 3.2s ease-in-out infinite" }} />
                    <div className="relative flex h-24 w-24 items-center justify-center rounded-[2rem] border border-white/90 bg-[linear-gradient(180deg,#FFFFFF,#EEF2FF)] shadow-[0_24px_54px_rgba(17,24,39,0.16)]" style={{ animation: "aiFloat 4.8s ease-in-out infinite" }}>
                      <div className="absolute -top-3 flex gap-1.5">
                        <span className="h-2.5 w-2.5 rounded-full bg-ey-gold" />
                        <span className="h-2.5 w-2.5 rounded-full bg-ey-blue" />
                        <span className="h-2.5 w-2.5 rounded-full bg-[#2D7A3A]" />
                      </div>
                      <Bot className="h-9 w-9 text-ey-blue" aria-hidden="true" />
                      <div className="absolute -right-3 -top-2 rounded-full border border-white/80 bg-white p-2 shadow-[0_8px_20px_rgba(17,24,39,0.10)]">
                        <Sparkles className="h-4 w-4 text-ey-gold" aria-hidden="true" />
                      </div>
                      <div className="absolute -left-3 -bottom-2 rounded-full border border-white/80 bg-white p-2 shadow-[0_8px_20px_rgba(17,24,39,0.10)]">
                        <Cpu className="h-4 w-4 text-ey-blue" aria-hidden="true" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="absolute right-3 top-0 hidden w-40 rounded-[1.2rem] border border-white/70 bg-white/82 p-3 shadow-[0_12px_30px_rgba(17,24,39,0.08)] backdrop-blur md:block">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#667085]">
                    {t.resultsSnapshot}
                  </p>
                  <div className="mt-4 space-y-3 text-sm text-ink">
                    <div className="rounded-xl bg-[#F0F9F2] px-3 py-2">{t.strengths}</div>
                    <div className="rounded-xl bg-[#FFF4E8] px-3 py-2">{t.painPoints}</div>
                    <div className="rounded-xl bg-[#EEF2FF] px-3 py-2">{t.priorities}</div>
                  </div>
                </div>

                <div className="absolute left-0 top-10 h-[320px] w-full rounded-4xl bg-[linear-gradient(135deg,rgba(214,244,237,0.72),rgba(255,240,230,0.72)_55%,rgba(255,255,255,0.98))] shadow-[0_18px_40px_rgba(17,24,39,0.08)]" />

                <div className="absolute left-3 top-14 w-[calc(100%-2rem)] rounded-3xl border border-[#E5E7EB] bg-white/90 p-5 shadow-[0_18px_42px_rgba(17,24,39,0.10)] backdrop-blur md:left-6 md:w-[74%]">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#667085]">
                        {t.guidedResults}
                      </p>
                      <h3 className="mt-2 text-[1.35rem] font-semibold tracking-[-0.03em] text-ink">
                        {t.builtForDecisionMaking}
                      </h3>
                    </div>
                    <div className="rounded-full bg-ink px-3 py-1.5 text-xs font-semibold text-white">
                      {t.overallPercentage}
                    </div>
                  </div>

                  <div className="mt-6 space-y-4">
                    {t.scoreRows.map(([label, value, color], index) => (
                      <div key={label}>
                        <div className="mb-2 flex items-center justify-between text-sm">
                          <span className="text-ink">{label}</span>
                          <span className="font-semibold text-ink">{value}</span>
                        </div>
                        <div className="h-2.5 overflow-hidden rounded-full bg-[#ECEFF1]">
                          <div
                            className="h-full rounded-full transition-all duration-700 hover:brightness-105"
                            style={{
                              width: inView ? value : "0%",
                              backgroundColor: color,
                              transitionDelay: `${index * 90}ms`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6 grid gap-2 sm:grid-cols-3">
                    {[
                      [t.strengths, "#F0F9F2", "#2D7A3A"],
                      [t.painPoints, "#FFF1F1", "#B42318"],
                      [t.priorities, "#EEF2FF", BRAND.blue],
                    ].map(([label, background, color]) => (
                      <div
                        key={label}
                        className="rounded-[1rem] px-3 py-3 text-xs font-semibold shadow-[0_8px_18px_rgba(17,24,39,0.05)] transition duration-500 hover:-translate-y-0.5"
                        style={{ backgroundColor: background, color }}
                      >
                        {label}
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-[1rem] border border-[#E5E7EB] bg-[#F8FAFC] p-3.5">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#667085]">
                          {t.benchmarkInsight}
                        </p>
                        <p className="mt-1 text-xs font-semibold text-ink">
                          {t.benchmarkText}
                        </p>
                      </div>
                      <div className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-ey-blue shadow-[0_6px_18px_rgba(17,24,39,0.06)]">
                        {t.benchmarkPts}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[#667085]">
                      <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1.5 shadow-[0_6px_16px_rgba(17,24,39,0.05)]">
                        {t.peerMedian}
                        <ArrowUpRight className="h-3.5 w-3.5 text-ey-blue" />
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1.5 shadow-[0_6px_16px_rgba(17,24,39,0.05)]">
                        {t.bestInClass}
                        <Sparkles className="h-3.5 w-3.5 text-ey-gold" />
                      </span>
                    </div>
                  </div>
                </div>

                <div className="absolute bottom-2 right-2 w-44 rounded-[1rem] border border-white/80 bg-white/86 p-3 shadow-[0_12px_30px_rgba(17,24,39,0.08)] backdrop-blur">
                  <div className="flex items-center gap-2 text-ey-gold">
                    <Wand2 className="h-4 w-4" />
                    <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                      {t.recommendedFocus}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-6 text-[#4B5563]">
                    {t.recommendationText}
                  </p>
                </div>
              </div>
            </FadeUp>
          </div>
        </div>
      </div>
    </section>
  );
}
