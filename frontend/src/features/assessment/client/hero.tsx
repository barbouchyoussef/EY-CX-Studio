import { lazy, Suspense } from "react";
import { pickCopy } from "../../../lib/i18n";
import FadeUp from "../../../components/FadeUp";
import { Spotlight } from "../../../components/ui/spotlight";

type HeroProps = {
  onStartConversation?: () => void;
  language?: string;
};

const SplineScene = lazy(() => import("../../../components/ui/splite").then((module) => ({ default: module.SplineScene })));
const HERO_SPLINE_SCENE = "https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode";

function HeroRobotFallback() {
  return (
    <div className="relative h-full w-full">
      <div className="absolute inset-x-[28%] top-[20%] h-64 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.85),rgba(255,255,255,0))] blur-3xl" />
    </div>
  );
}

const TRANSLATIONS = {
  fr: {
    bannerLabel: "Chaque interaction est décisive",
    bannerDesc: "Découvrez l'aptitude de votre organisation à transformer ces moments en fidélité, croissance et impact.",
    heading: "Derrière chaque client fidèle se cache une organisation mature",
    subtitle: "Mesurez la maturité de votre expérience client et identifiez les leviers clés pour franchir un cap.",
    cta: "Lancer mon diagnostic de maturité",
  },
  en: {
    bannerLabel: "Every interaction is a make-or-break moment",
    bannerDesc: "Discover how mature your organization is at turning those moments into loyalty, growth, and impact.",
    heading: "Behind every loyal customer is a mature organization",
    subtitle: "Find out where yours stands and discover what it takes to get to the next level.",
    cta: "Start your assessment",
  },
};

export default function Hero({ onStartConversation, language = "en" }: HeroProps) {
  const t = pickCopy(TRANSLATIONS, language);

  return (
    <section
      id="start"
      className="relative overflow-hidden bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] py-16 text-ink sm:py-20 lg:py-24"
    >
      <div className="pointer-events-none absolute right-[-8%] top-[6%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(226,232,240,0.4),rgba(255,255,255,0))] blur-3xl" />
      <div className="pointer-events-none absolute left-[-10%] bottom-[8%] h-[24rem] w-[24rem] rounded-full bg-[radial-gradient(circle,rgba(248,250,252,0.88),rgba(255,255,255,0))] blur-3xl" />
      <div className="relative mx-auto grid w-full max-w-7xl items-center gap-14 px-6 lg:grid-cols-[minmax(0,1.02fr)_minmax(480px,0.98fr)] lg:px-12">
        <div className="relative z-10 flex max-w-2xl flex-col items-center text-center lg:items-start lg:text-left">
          <FadeUp>
            <h1 className="mb-6 text-4xl font-medium leading-[1.05] tracking-[-0.04em] text-ink sm:text-5xl md:text-7xl max-w-2xl">
              {t.heading}
            </h1>
          </FadeUp>

          <FadeUp delay="delay-1">
            <p className="max-w-xl text-lg font-light leading-8 text-[#374151] md:text-2xl md:leading-10">
              {t.subtitle}
            </p>
          </FadeUp>

          <FadeUp delay="delay-2">
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4 lg:justify-start">
              <button
                type="button"
                onClick={onStartConversation}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-8 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover"
              >
                {t.cta}
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </FadeUp>
        </div>

        <div className="relative z-10 hidden h-[600px] w-full animate-[heroRobotIn_720ms_ease-out] lg:block">
          <div className="absolute inset-x-[24%] top-[16%] h-24 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.82),rgba(255,255,255,0))] blur-3xl" />
          <div className="absolute inset-x-[26%] bottom-[19%] h-12 rounded-full bg-[radial-gradient(circle,rgba(148,163,184,0.12),rgba(255,255,255,0))] blur-2xl" />
          <div className="relative h-full w-full">
            <Spotlight className="z-0 opacity-35" size={220} />
            <Suspense fallback={<HeroRobotFallback />}>
              <SplineScene
                scene={HERO_SPLINE_SCENE}
                className="relative z-10 h-full w-full opacity-100"
              />
            </Suspense>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes heroRobotIn {
          0% {
            opacity: 0;
            transform: translateX(18px) translateY(10px) scale(0.985);
          }
          100% {
            opacity: 1;
            transform: translateX(0) translateY(0) scale(1);
          }
        }
      `}</style>
    </section>
  );
}
