/**
 * The three-step form that collects what a guide should be generated from.
 *
 * Step 1 is the company and its data source, step 2 the stakeholder being interviewed, step 3 the
 * free-text context. Splitting it across steps is deliberate: the whole form on one screen reads
 * as a wall of optional fields, and only two of them are actually required.
 *
 * The form owns no state. Everything it collects lives in the hub as a single `setup` value, and
 * every keystroke goes back through `updateSetup` -- which is what lets this be a plain component
 * rather than a second copy of the hub's state.
 */

import {
  AlertTriangle, ArrowRight, Building2, CheckCircle2, ChevronRight, Compass,
  Settings2, Sparkles, Users,
} from "lucide-react";

import type { AssessmentItem } from "./guide";
import type { InterviewSetup } from "./setup";
import type { InterviewLabels, InterviewPersona } from "./copy";

type Props = {
  setup: InterviewSetup;
  updateSetup: (patch: Partial<InterviewSetup>) => void;
  /** 1, 2 or 3 -- which of the three panels is showing. */
  formStep: number;
  /** Assessments this guide can be built from; empty means "from scratch" is the only option. */
  sourceAssessments: AssessmentItem[];
  selectedAssessmentId: string;
  setSelectedAssessmentId: (id: string) => void;
  selectedAssessment: AssessmentItem | undefined;
  /** Validated forward navigation, and submission. The rules themselves live in `setup.ts`. */
  goToStep2: () => void;
  goToStep3: () => void;
  handleGenerate: () => void;
  error: string | null;
  labels: InterviewLabels;
  personas: InterviewPersona[];
  /** True when a project is active, which narrows the data sources on offer. */
  inProject: boolean;
  /** Step back, clearing any error the previous attempt left on screen. */
  goBackToStep: (step: number) => void;
  /** The hub's shared header, rendered above the form. */
  header: React.ReactNode;
};

export default function InterviewSetupView({
  setup, updateSetup, formStep,
  sourceAssessments, selectedAssessmentId, setSelectedAssessmentId, selectedAssessment,
  goToStep2, goToStep3, handleGenerate, error, labels, personas,
  inProject, goBackToStep, header,
}: Props) {
  const {
    companyName, sector, size, region, profile,
    customContext, customProfileName, customProfileDesc,
  } = setup;

  return (
    <div className="min-h-screen bg-[#F7F8FA] text-slate-800 font-sans pb-16">
      {header}

      <div className="max-w-5xl mx-auto px-6 mt-8">

        {/* Step Indicators */}
        <div className="flex items-center gap-2 mb-8">
          {[
            { n: 1, label: labels.stepSourceLabel },
            { n: 2, label: labels.stepPersonaLabel },
            { n: 3, label: labels.stepGenerateLabel },
          ].map((s, i) => {
            const isActive = formStep === s.n;
            const isCompleted = formStep > s.n;
            return (
              <div key={i} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 bg-white border rounded-full px-3.5 py-1.5 shadow-sm transition-all duration-200 ${
                  isActive 
                    ? "border-ey-gold ring-2 ring-ey-gold/20 bg-ey-gold/5" 
                    : isCompleted 
                      ? "border-emerald-500 bg-emerald-50/20" 
                      : "border-slate-200 opacity-60"
                }`}>
                  <span className={`h-5 w-5 rounded-full text-[10px] font-bold flex items-center justify-center transition-all duration-200 ${
                    isActive 
                      ? "bg-ey-gold text-white" 
                      : isCompleted 
                        ? "bg-emerald-500 text-white" 
                        : "bg-slate-200 text-slate-500"
                  }`}>{isCompleted ? "✓" : s.n}</span>
                  <span className={`text-xs font-semibold transition-all duration-200 ${
                    isActive 
                      ? "text-slate-900 font-bold" 
                      : isCompleted 
                        ? "text-emerald-800" 
                        : "text-slate-400"
                  }`}>{s.label}</span>
                </div>
                {i < 2 && <ChevronRight className="h-3.5 w-3.5 text-slate-300" />}
              </div>
            );
          })}
        </div>

        {/* Main Form Layout */}
        <div className="space-y-6">
          
          {/* Section 1: Data Source & Company Details */}
          <div className={`bg-white border rounded-2xl shadow-sm overflow-hidden transition-all duration-300 ${
            formStep === 1 
              ? "border-slate-300 shadow-md ring-1 ring-slate-200" 
              : "border-slate-200 opacity-90"
          }`}>
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <Building2 className="h-4 w-4 text-slate-400" />
                {labels.step1Title}
              </h3>
              {formStep > 1 && (
                <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-bold uppercase tracking-wide">
                  {labels.stepCompleted}
                </span>
              )}
            </div>
            <div className="p-6">
              {/* Selector Block */}
              <div className="mb-5">
                {/* Data source + its context. Saved interviews now live on the dashboard. */}
                <div className="space-y-2.5 md:max-w-md">
                  <div>
                    <label className="text-xs font-semibold text-slate-600 mb-1.5 block">{labels.sourceLabel}</label>
                    <select
                      value={selectedAssessmentId}
                      onChange={(e) => setSelectedAssessmentId(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-700 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400/20 focus:outline-none transition-all"
                    >
                      <option value="scratch">{labels.scratchOption}</option>
                      {sourceAssessments.map((a) => (
                        <option key={a.id} value={a.id.toString()}>
                          #{a.id} — {a.company_name} ({a.sector})
                        </option>
                      ))}
                    </select>
                    {inProject && sourceAssessments.length === 0 && (
                      <p className="mt-1.5 text-[11px] leading-snug text-slate-400">
                        {labels.noAssessmentInProject}
                      </p>
                    )}
                  </div>

                  {selectedAssessment && (
                    <div className="rounded-lg bg-emerald-50 border border-emerald-200/60 px-3 py-2.5 flex items-center gap-2.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      <div className="text-[11px]">
                        <p className="font-bold text-emerald-800">{labels.insightTitle}</p>
                        <p className="text-emerald-600">
                          {labels.insightStatus}: <span className="font-mono uppercase">{selectedAssessment.status}</span>
                          {selectedAssessment.overall_maturity_band && (
                            <> · {labels.insightMaturity}: <span className="font-bold">{selectedAssessment.overall_maturity_band}</span></>
                          )}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

              </div>

              {/* Company Fields Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: labels.companyLabel + " *", field: "companyName" as const, value: companyName, ph: "Tunisie Telecom" },
                  { label: labels.sectorLabel, field: "sector" as const, value: sector, ph: "Telecom, Banking..." },
                  { label: labels.sizeLabel, field: "size" as const, value: size, ph: "PME, Enterprise..." },
                  { label: labels.regionLabel, field: "region" as const, value: region, ph: "Africa, Europe..." },
                ].map((f, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <label className="text-[11px] font-semibold text-slate-500">{f.label}</label>
                    <input
                      type="text"
                      value={f.value}
                      onChange={(e) => updateSetup({ [f.field]: e.target.value })}
                      disabled={selectedAssessmentId !== "scratch"}
                      placeholder={f.ph}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 placeholder:text-slate-300 disabled:bg-slate-50 disabled:text-slate-400 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400/20 focus:outline-none transition-all"
                    />
                  </div>
                ))}
              </div>

              {formStep === 1 && (
                <div className="mt-6 border-t border-slate-100 pt-6 flex flex-col items-end gap-3">
                  {error && (
                    <div className="w-full rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      {error}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={goToStep2}
                    className="flex items-center gap-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 px-5 py-3 text-sm font-bold text-white shadow-sm transition active:scale-[0.99]"
                  >
                    {labels.continueToStep2}
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Section 2: Persona Selection */}
          {formStep >= 2 && (
            <div className={`bg-white border rounded-2xl shadow-sm overflow-hidden transition-all duration-300 animate-fadeIn ${
              formStep === 2 
                ? "border-slate-300 shadow-md ring-1 ring-slate-200" 
                : "border-slate-200 opacity-90"
            }`}>
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                  <Users className="h-4 w-4 text-slate-400" />
                  {labels.step2Title}
                </h3>
                {formStep > 2 && (
                  <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-bold uppercase tracking-wide">
                    {labels.stepCompleted}
                  </span>
                )}
              </div>
              <div className="p-6">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {personas.map((p) => {
                    const isActive = profile === p.code;
                    const accentMap: Record<string, { border: string; bg: string; badge: string; icon: string }> = {
                      yellow:  { border: "border-yellow-400", bg: "bg-yellow-50/60", badge: "bg-yellow-400 text-yellow-900", icon: "text-yellow-600" },
                      blue:    { border: "border-blue-400", bg: "bg-blue-50/60", badge: "bg-blue-500 text-white", icon: "text-blue-600" },
                      emerald: { border: "border-emerald-400", bg: "bg-emerald-50/60", badge: "bg-emerald-500 text-white", icon: "text-emerald-600" },
                      violet:  { border: "border-violet-400", bg: "bg-violet-50/60", badge: "bg-violet-500 text-white", icon: "text-violet-600" },
                      slate:   { border: "border-slate-400", bg: "bg-slate-50/60", badge: "bg-slate-500 text-white", icon: "text-slate-600" },
                    };
                    const colors = accentMap[p.accent] || accentMap.yellow;

                    return (
                      <button
                        key={p.code}
                        type="button"
                        onClick={() => updateSetup({ profile: p.code })}
                        className={`group text-left rounded-xl border-2 p-4 transition-all duration-200 relative ${
                          isActive
                            ? `${colors.border} ${colors.bg} shadow-sm`
                            : "border-slate-150 bg-white hover:border-slate-300 hover:shadow-sm"
                        }`}
                      >
                        {isActive && (
                          <div className="absolute top-2.5 right-2.5">
                            <CheckCircle2 className={`h-4 w-4 ${colors.icon}`} />
                          </div>
                        )}
                        <div className={`h-9 w-9 rounded-lg flex items-center justify-center mb-3 transition-colors ${
                          isActive ? colors.badge : "bg-slate-100 text-slate-400 group-hover:bg-slate-200"
                        }`}>
                          {p.icon}
                        </div>
                        <h4 className="text-[13px] font-bold text-slate-900 leading-tight">{p.title}</h4>
                        <p className="text-[11px] text-slate-400 leading-snug mt-1.5 font-medium">{p.desc}</p>
                      </button>
                    );
                  })}
                </div>

                {profile === "Other" && (
                  <div className="mt-5 border-t border-slate-100 pt-5 space-y-4 animate-fadeIn">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                      <Settings2 className="h-4 w-4 text-slate-400" />
                      {labels.customProfileTitle}
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-1.5 sm:col-span-1">
                        <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                          {labels.customRoleLabel}
                        </label>
                        <input
                          type="text"
                          value={customProfileName}
                          onChange={(e) => updateSetup({ customProfileName: e.target.value })}
                          placeholder={labels.customRolePlaceholder}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-700 placeholder:text-slate-300 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400/20 focus:outline-none transition-all"
                        />
                      </div>
                      <div className="space-y-1.5 sm:col-span-2">
                        <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                          {labels.customDescriptionLabel}
                        </label>
                        <textarea
                          value={customProfileDesc}
                          onChange={(e) => updateSetup({ customProfileDesc: e.target.value })}
                          placeholder={labels.customDescriptionPlaceholder}
                          rows={2}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-700 placeholder:text-slate-300 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400/20 focus:outline-none resize-none transition-all"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {formStep === 2 && (
                  <div className="mt-6 border-t border-slate-100 pt-6 flex flex-col gap-3">
                    {error && (
                      <div className="w-full rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        {error}
                      </div>
                    )}
                    <div className="flex justify-between items-center">
                      <button
                        type="button"
                        onClick={() => goBackToStep(1)}
                        className="text-xs font-bold uppercase tracking-wide text-slate-500 hover:text-slate-800 transition"
                      >
                        {labels.backToStep1}
                      </button>
                      <button
                        type="button"
                        onClick={goToStep3}
                        className="flex items-center gap-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 px-5 py-3 text-sm font-bold text-white shadow-sm transition active:scale-[0.99]"
                      >
                        {labels.continueToStep3}
                        <ArrowRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Section 3: Custom Remarks & Generate */}
          {formStep >= 3 && (
            <div className={`bg-white border rounded-2xl shadow-sm overflow-hidden transition-all duration-300 animate-fadeIn ${
              formStep === 3 
                ? "border-slate-300 shadow-md ring-1 ring-slate-200" 
                : "border-slate-200 opacity-90"
            }`}>
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                  <Compass className="h-4 w-4 text-slate-400" />
                  {labels.step3Title}
                </h3>
              </div>
              <div className="p-6 space-y-5">
                <textarea
                  value={customContext}
                  onChange={(e) => updateSetup({ customContext: e.target.value })}
                  placeholder={labels.contextPlaceholder}
                  rows={4}
                  className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 placeholder:text-slate-300 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400/20 focus:outline-none resize-none transition-all"
                />

                {error && (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 p-3.5 text-sm text-rose-700 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <div className="mt-6 border-t border-slate-100 pt-6 flex justify-between items-center">
                  <button
                    type="button"
                    onClick={() => goBackToStep(2)}
                    className="text-xs font-bold uppercase tracking-wide text-slate-500 hover:text-slate-800 transition"
                  >
                    {labels.backToStep2}
                  </button>
                  <button
                    onClick={handleGenerate}
                    className="flex items-center gap-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 px-6 py-4 text-sm font-bold text-white shadow-lg shadow-slate-900/10 active:scale-[0.995] transition-all"
                  >
                    <Sparkles className="h-4.5 w-4.5 text-yellow-400" />
                    {labels.generate}
                  </button>
                </div>

              </div>
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
