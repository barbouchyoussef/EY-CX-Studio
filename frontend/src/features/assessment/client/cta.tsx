import React from "react";
import { pickCopy } from "../../../lib/i18n";

type CTASectionProps = {
  onStartConversation?: () => void;
  language?: string;
};

const TRANSLATIONS = {
  fr: {
    title: "Prêt à évaluer la maturité réelle de votre organisation ?",
    subtitle: "Une conversation simple. Une clarté nouvelle pour orienter vos décisions stratégiques.",
    cta: "Lancer le diagnostic",
  },
  en: {
    title: "Ready to see where your organization really stands?",
    subtitle: "A simple conversation. A clarity that changes how you lead.",
    cta: "Start your diagnostic",
  },
};

const CTASection: React.FC<CTASectionProps> = ({
  onStartConversation,
  language = "en",
}) => {
  const t = pickCopy(TRANSLATIONS, language);

  return (
    <section id="cta" className="py-16 sm:py-20 md:py-24 bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-950 border-t border-slate-900">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        
        <div className="text-center">
          
          {/* TITLE */}
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 sm:mb-6 text-white tracking-tight">
            {t.title}
          </h2>

          {/* SUBTITLE */}
          <p className="text-base sm:text-lg md:text-xl mb-8 sm:mb-10 max-w-3xl mx-auto text-indigo-200 font-light leading-relaxed">
            {t.subtitle}
          </p>

          <div className="flex justify-center items-center">
            <button
              type="button"
              onClick={onStartConversation}
              className="inline-flex items-center justify-center gap-2 px-8 h-12 rounded-full text-sm sm:text-base font-semibold bg-white text-indigo-950 hover:bg-slate-50 shadow-lg hover:shadow-xl transition hover:-translate-y-0.5"
            >
              {t.cta}
              
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path d="M5 12h14" />
                <path d="M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>

        </div>

      </div>
    </section>
  );
};

export default CTASection;
