/**
 * The full-screen wait while a guide is being generated.
 *
 * Generation takes long enough that a bare spinner reads as a hang, so the screen narrates what
 * the model is actually doing and steps through the stages on a timer. The steps are indicative,
 * not a real progress signal -- the backend does not report progress -- which is why they cycle
 * rather than fill up. Saying so here stops the next reader wiring them to something.
 */

import { useEffect, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

/** How long each line stays on screen. Long enough to read, short enough to feel alive. */
const STAGE_INTERVAL_MS = 2000;

const STAGES_FR = [
  "Analyse de l'historique des conversations avec le bot Orion...",
  "Identification des dimensions CX non abordées dans l'auto-évaluation...",
  "Formulation de questions spécifiques adaptées au profil de l'interlocuteur...",
  "Vérification des doublons et structuration finale du guide d'entretien...",
];

const STAGES_EN = [
  "Analyzing past conversation history with Orion bot...",
  "Identifying information gaps and uncovered CX capabilities...",
  "Formulating specific questions matched to the stakeholder persona...",
  "Checking for duplicate questions and building final interview flow...",
];

export default function InterviewGeneratingView({ isFrench }: { isFrench: boolean }) {
  const stages = isFrench ? STAGES_FR : STAGES_EN;
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(
      () => setStageIndex((prev) => (prev + 1) % stages.length),
      STAGE_INTERVAL_MS,
    );
    return () => clearInterval(interval);
  }, [stages.length]);

  return (
    <div className="min-h-screen bg-slate-955 text-white font-sans flex items-center justify-center p-6">
      <div className="max-w-sm w-full flex flex-col items-center gap-10 text-center">
        {/* Spinner */}
        <div className="relative h-24 w-24 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-[3px] border-slate-800" />
          <div className="absolute inset-0 rounded-full border-[3px] border-t-yellow-400 border-r-transparent border-b-transparent border-l-transparent animate-spin" />
          <div className="absolute inset-3 rounded-full border-2 border-slate-800" />
          <div className="absolute inset-3 rounded-full border-2 border-t-transparent border-r-white/40 border-b-transparent border-l-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
          <Sparkles className="h-6 w-6 text-yellow-400" />
        </div>

        <div className="space-y-3">
          <h2 className="text-xs font-black tracking-[0.25em] uppercase text-yellow-400 flex items-center justify-center gap-2">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            {isFrench ? "Génération en cours" : "Generating"}
          </h2>
          <p className="text-sm text-slate-400 font-medium leading-relaxed min-h-[44px] px-4 transition-all">
            {stages[stageIndex]}
          </p>
        </div>

        <div className="flex gap-1.5">
          {stages.map((_, i) => (
            <div key={i} className={`h-1.5 rounded-full transition-all duration-500 ${i === stageIndex ? "w-6 bg-yellow-400" : "w-1.5 bg-slate-700"}`} />
          ))}
        </div>
      </div>
    </div>
  );
}
