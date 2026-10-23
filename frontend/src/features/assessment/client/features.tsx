import { Sparkles, BarChart3, Lightbulb } from "lucide-react";
import { pickCopy } from "../../../lib/i18n";
import FadeUp from "../../../components/FadeUp";

type FeaturesProps = {
  language?: string;
};

const TRANSLATIONS = {
  fr: {
    heading: "Une approche d'évaluation repensée",
    features: [
      {
        title: "Adaptatif par nature",
        desc: "Notre assistant écoute avant d'interroger. L'échange s'adapte dynamiquement à vos réponses, rompant avec la rigidité des questionnaires classiques.",
      },
      {
        title: "Positionné face à vos pairs",
        desc: "Votre niveau de maturité est évalué au regard des standards de votre secteur, vous offrant un véritable repère concurrentiel plutôt qu'un score abstrait.",
      },
      {
        title: "De l'analyse à l'action",
        desc: "Vous ne recevez pas un simple rapport de plus. Notre diagnostic vous fournit une feuille de route priorisée identifiant vos points de blocage et les actions concrètes sur lesquelles concentrer vos efforts.",
      },
    ],
  },
  en: {
    heading: "A different kind of assessment",
    features: [
      {
        title: "Adaptive by nature",
        desc: "The assistant listens before it asks. Every conversation follows your answers, not a predetermined script.",
      },
      {
        title: "Benchmarked to your reality",
        desc: "Your maturity score is measured against organizations in your industry giving you context, not just a number.",
      },
      {
        title: "Insights, not just results",
        desc: "What you receive isn’t a report. It’s a prioritized picture of where you stand, what’s holding you back, and where to focus next.",
      },
    ],
  },
};

const ICONS = [
  <Sparkles className="h-6 w-6 text-violet-600" />,
  <BarChart3 className="h-6 w-6 text-violet-600" />,
  <Lightbulb className="h-6 w-6 text-violet-600" />,
];

export default function AuditFeatures({ language = "en" }: FeaturesProps) {
  const t = pickCopy(TRANSLATIONS, language);

  const features = t.features.map((f, i) => ({
    ...f,
    icon: ICONS[i] || ICONS[0],
  }));

  return (
    <section id="screens" className="bg-slate-50/50 py-20 md:py-24 border-y border-slate-100">
      <div className="max-w-7xl mx-auto px-6">

        {/* HEADER */}
        <div className="text-center mb-16">
          <FadeUp>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-slate-900">
              {t.heading}
            </h2>
          </FadeUp>
        </div>

        {/* GRID */}
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {features.map((item, i) => (
            <FadeUp key={i} delay={i % 3 === 0 ? "" : i % 3 === 1 ? "delay-1" : "delay-2"}>
              <div
                className="bg-white/70 backdrop-blur-md rounded-3xl p-8 border border-slate-100 shadow-[0_8px_30px_rgba(0,0,0,0.02)] hover:shadow-[0_20px_40px_rgba(15,23,42,0.05)] hover:border-violet-100/50 hover:-translate-y-1 transition-all duration-300"
              >
                {/* ICON */}
                <div className="h-12 w-12 rounded-2xl bg-violet-50 text-violet-600 flex items-center justify-center mb-6 border border-violet-100/30">
                  {item.icon}
                </div>

                {/* TEXT */}
                <h3 className="text-xl font-bold text-slate-900 mb-3 tracking-tight">
                  {item.title}
                </h3>

                <p className="text-[14px] leading-relaxed text-slate-500 font-normal">
                  {item.desc}
                </p>

              </div>
            </FadeUp>
          ))}
        </div>
      </div>
    </section>
  );
}
