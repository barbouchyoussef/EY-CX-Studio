import { useState } from "react";
import { assessmentCopy } from "../copy";
import Hero from "./hero";
import Features from "./features";
import HowItWorks from "./how-it-works";
import CoreFeaturesShowcase from "./showcase";
import CTASection from "./cta";
import Footer from "../../../components/Footer";
import ClientAssessmentChat from "./chat";

/**
 * The public, passwordless client page reached at `/a/<token>`.
 *
 * Its sections — hero, method, features, CTA — live beside it in this folder. They were once
 * shared with a public marketing site that no longer exists; consultants get InternalHome, which
 * imports none of them. There is no navbar here at all: no links, no login, no route out.
 * "Start assessment" drops the client straight into the respondent chat for their one assessment.
 */
export default function ClientAssessmentPage({ token }: { token: string }) {
  const [started, setStarted] = useState(false);
  const [language, setLanguage] = useState<string>("en");
  const isFr = language === "fr";
  const copy = assessmentCopy(isFr);
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;

  // Minimal, link-free header — just branding + a language toggle. No routes out of this page.
  const header = (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-slate-100 bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <img src={logoSrc} alt="EY" className="h-8 w-auto" />
          <span className="text-slate-300">|</span>
          <span className="text-sm font-semibold tracking-wide text-slate-700">
            {copy.assessmentName}
          </span>
        </div>
        <button
          onClick={() => setLanguage(copy.languageCode)}
          className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
        >
          {copy.languageToggle}
        </button>
      </div>
    </header>
  );

  if (started) {
    return (
      <div className="min-h-screen bg-[linear-gradient(180deg,#ffffff_0%,#f7f9fb_100%)]">
        {header}
        <main className="pt-16">
          <ClientAssessmentChat token={token} language={language} />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {header}
      <main className="pt-16">
        <Hero onStartConversation={() => setStarted(true)} language={language} />
        <HowItWorks language={language} />
        <Features language={language} />
        <CoreFeaturesShowcase language={language} />
        <CTASection onStartConversation={() => setStarted(true)} language={language} />
        <Footer language={language} />
      </main>
    </div>
  );
}
