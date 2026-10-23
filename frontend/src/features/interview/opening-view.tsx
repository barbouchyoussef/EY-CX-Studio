/**
 * The brief wait while a saved guide is fetched.
 *
 * Deliberately not the generation screen. That one narrates the model's work -- "analysing the
 * assessment history", "formulating questions" -- which is a plain untruth when all that is
 * happening is a row being read back, and it sets the consultant up to wait far longer than they
 * need to. Opening a guide is one request, so it gets one spinner and no story.
 */

import { Loader2 } from "lucide-react";

export default function InterviewOpeningView({ isFrench }: { isFrench: boolean }) {
  return (
    <div className="min-h-screen bg-[#F7F8FA] text-slate-800 font-sans flex items-center justify-center p-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <p className="text-sm font-medium text-slate-500">
          {isFrench ? "Ouverture de l'entretien…" : "Opening interview…"}
        </p>
      </div>
    </div>
  );
}
