import { useEffect, useRef, useState, useCallback } from "react";
import {
  ArrowLeft, Printer, AlertTriangle, Sparkles, BookOpen,
  CheckCircle2, RefreshCw,
  Trash2, Pencil, Plus, Save, X, Circle, FileSpreadsheet, StickyNote,
  ChevronDown, ChevronUp, Loader2
} from "lucide-react";
import ModuleChat, { ChatMarkdown, type ModuleChatMessage } from "../../components/ui/module-chat";
import ShareButton from "../../components/ui/share-button";
import AddToProjectButton from "../../components/ui/add-to-project-button";
import InterviewProjectReportView from "./project-report";
import { useProjectInterviewReport } from "./use-project-report";
import StudioNav from "../../components/ui/studio-nav";
import InterviewHistoryTable, { type InterviewItem } from "./history-table";
import InterviewGeneratingView from "./generating-view";
import InterviewOpeningView from "./opening-view";
import { interviewSections } from "./sections";
import { interviewLabels, interviewPersonas } from "./copy";
import InterviewSetupView from "./setup-view";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useProjectArtifactRefs } from "../../lib/use-project-artifacts";

import { authFetchUrl } from "../../lib/api";
import { EMPTY_SETUP, companyProblem, profileProblem, setupProblem, type InterviewSetup } from "./setup";
import {
  questionsFieldFor,
  withQuestionIds,
  type AssessmentItem,
  type InterviewGuide,
  type InterviewGuideQuestionItem,
  type SectionKey,
} from "./guide";
import { exportInterviewGuideToExcel } from "./excel";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/** Where the in-progress guide is mirrored, so closing the tab does not lose unsaved edits. */
const LOCAL_STORAGE_KEY = "ey_interview_guide_autosave";

/** How long editing has to pause before the guide is written to the database. */
const AUTOSAVE_DEBOUNCE_MS = 1500;

/** The company fields, cleared. Filled in together from an assessment, so cleared together too. */
const BLANK_COMPANY_FIELDS = { companyName: "", sector: "", size: "", region: "" } as const;

type Props = {
  onBack: () => void;
  topSlot?: React.ReactNode;
};


export default function ClientInterviewHub(
  { onBack, topSlot }: Props,
) {
  const [step, setStep] = useState<
    "history" | "form" | "generating" | "opening" | "result" | "projectReport"
  >("history");
  const [formStep, setFormStep] = useState(1);
  // In-app delete confirmation for a saved interview.
  const [pendingDelete, setPendingDelete] = useState<{ id: number; company_name: string } | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [assessments, setAssessments] = useState<AssessmentItem[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string>("scratch");

  // Everything the consultant fills in before generating, held as one value.
  //
  // It was nine separate pieces of state, which meant the setup form needed eighteen props and
  // the validation rules had to be written against the component rather than against a value.
  // The fields are destructured below purely for readability at the use sites -- `setup` is the
  // source of truth and the thing that gets passed down.
  const [setup, setSetup] = useState<InterviewSetup>(EMPTY_SETUP);
  const updateSetup = (patch: Partial<InterviewSetup>) =>
    setSetup((prev) => ({ ...prev, ...patch }));
  const {
    companyName, sector, size, region, language, profile,
    customContext, customProfileName, customProfileDesc,
  } = setup;

  // Guide generation states
  const [guide, setGuide] = useState<InterviewGuide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { project: activeProject, attach: attachToProject, completeStep } = useActiveProject();
  // Owned here rather than in the table so the buttons that generate it and the page that shows
  // it are the same instance: generating from the list makes the page available immediately,
  // with no second fetch. Null outside a project keeps it inert -- a consolidated report only
  // means something for a set of interviews of the same client.
  const projectReport = useProjectInterviewReport(activeProject?.id ?? null);
  // When inside a project, the Data Source only offers the assessments that live in this project.
  const { refs: projectAssessmentRefs } = useProjectArtifactRefs("assessment");

  // When this guide belongs to a saved result and a project is active, link it + complete the
  // step. attach/completeStep no-op without an active project, and the attach is idempotent.
  useEffect(() => {
    if (step === "result" && guide?.id) {
      void attachToProject("interview_guide", String(guide.id), "interview", guide.company_name);
      void completeStep("interview");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guide?.id, step]);

  // Interview assistant chat (per saved guide). The CURRENT guide is sent on every turn so the
  // assistant always reasons over the consultant's live edits, not a stale copy.
  const [chatMessages, setChatMessages] = useState<ModuleChatMessage[]>([]);
  const appendChatMessage = (m: ModuleChatMessage) => setChatMessages((prev) => [...prev, m]);
  // Always hold the freshest guide so the chat sends the latest edits/answers (no stale closure).
  const guideRef = useRef<InterviewGuide | null>(guide);
  guideRef.current = guide;

  // Insights: cross-reference the Orion self-assessment against the interview answers.
  // Insights render inline under the interview and persist on the guide, so there is no
  // open/closed state any more -- only whether they were already generated.
  const [insightsSavedAt, setInsightsSavedAt] = useState<string | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsText, setInsightsText] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // Restore the persisted conversation when a SAVED guide is opened (unsaved guides start fresh).
  useEffect(() => {
    const gid = guide?.id;
    if (!gid) {
      setChatMessages([]);
      return;
    }
    let cancelled = false;
    authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/${gid}/chat`)
      .then((r) => (r.ok ? r.json() : { messages: [] }))
      .then((d: { messages?: { id?: string; role: string; text: string; sources?: string[]; ts?: number }[] }) => {
        if (cancelled) return;
        const msgs = Array.isArray(d.messages) ? d.messages : [];
        setChatMessages(
          msgs.map((m) => ({
            id: m.id ?? `${Math.random()}`,
            role: m.role === "assistant" ? "assistant" : "user",
            text: m.text ?? "",
            sources: m.sources,
            ts: m.ts ?? Date.now(),
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setChatMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [guide?.id]);
  // Edit states for live questions
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editQuestionText, setEditQuestionText] = useState("");
  const [editRationaleText, setEditRationaleText] = useState("");
  const [editFollowUpText, setEditFollowUpText] = useState("");

  // Answer notes — expanded state tracking
  const [expandedNoteIds, setExpandedNoteIds] = useState<Set<string>>(new Set());
  const [savedGuides, setSavedGuides] = useState<InterviewItem[]>([]);

  const fetchSavedGuides = useCallback(() => {
    authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/list`)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data)) {
          setSavedGuides(data);
        }
      })
      .catch((err) => console.error("Failed to load saved guides:", err));
  }, []);

  const saveGuideToDb = useCallback(async (g: InterviewGuide) => {
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: g.id || null,
          assessment_id: g.assessment_id || null,
          company_name: g.company_name,
          profile: g.profile || profile,
          language: g.language,
          payload: g
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.id) {
          if (g.id !== data.id) {
            setGuide((prev) => {
              if (prev && prev.company_name === g.company_name) {
                return { ...prev, id: data.id };
              }
              return prev;
            });
          }
          fetchSavedGuides();
          return data.id as number;
        }
        fetchSavedGuides();
      }
    } catch (err) {
      console.error("Failed to save guide to DB:", err);
    }
    return g.id ?? null;
  }, [profile, fetchSavedGuides]);

  const saveGuideToStorage = useCallback((g: InterviewGuide) => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(g));
    } catch { /* quota exceeded — ignore */ }
  }, []);

  // Persist on every guide change (localStorage + debounced DB)
  useEffect(() => {
    if (guide && step === "result") {
      saveGuideToStorage(guide);
      
      const timer = setTimeout(() => {
        saveGuideToDb(guide);
      }, AUTOSAVE_DEBOUNCE_MS);
      return () => clearTimeout(timer);
    }
  }, [guide, step, saveGuideToStorage, saveGuideToDb]);

  // Restore the last guide from localStorage on mount, so a closed tab does not lose work that
  // had not reached the database yet.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as InterviewGuide;
        if (parsed && parsed.company_name) {
          setGuide(withQuestionIds(parsed));
          updateSetup({ companyName: parsed.company_name, language: parsed.language || "fr" });
        }
      }
    } catch { /* corrupt data — ignore */ }
  }, []);

  // Load past assessments list and saved guides list on mount
  useEffect(() => {
    authFetchUrl(`${API_BASE_URL}/assessments?limit=100`)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.items)) {
          setAssessments(data.items);
        }
      })
      .catch((err) => console.error("Failed to load assessments:", err));

    fetchSavedGuides();
  }, [fetchSavedGuides]);

  // In a project, only offer that project's assessments as a source; otherwise all of yours.
  const sourceAssessments = activeProject
    ? assessments.filter((a) => projectAssessmentRefs.has(a.id.toString()))
    : assessments;

  const handleLoadGuideFromDb = async (guideId: number) => {
    setStep("opening");
    setError(null);
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/${guideId}`);
      if (!res.ok) throw new Error("Failed to fetch guide");
      const data = (await res.json()) as InterviewGuide;
      
      setGuide(withQuestionIds(data));
      // The profile has to come back into the form too. The autosave sends `g.profile || profile`,
      // so leaving the form on its default meant reopening a Marketing or IT Lead interview and
      // saving it wrote "CEO" over the stored role.
      updateSetup({
        companyName: data.company_name,
        language: data.language || "fr",
        ...(data.profile ? { profile: data.profile } : {}),
      });
      // Show the saved briefing straight away if one exists -- it is stored on the guide, so
      // it never needs regenerating just because the page was reopened.
      const saved = (data as { insights?: { markdown?: string; generated_at?: string } }).insights;
      setInsightsText(saved?.markdown ?? null);
      setInsightsSavedAt(saved?.generated_at ?? null);
      setStep("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading saved guide.");
      setStep("form");
      setFormStep(1);
    }
  };

  // "New interview" → a fresh Step 1 (from scratch).
  const startNewInterview = () => {
    setSelectedAssessmentId("scratch");
    updateSetup(BLANK_COMPANY_FIELDS);
    setGuide(null);
    setError(null);
    setInsightsText(null);
    setInsightsSavedAt(null);
    setFormStep(1);
    setStep("form");
  };

  // Delete a saved interview (owner only — the server 404s otherwise), via an in-app modal.
  const handleDeleteInterview = (item: InterviewItem) => {
    setDeleteError(null);
    setPendingDelete({ id: item.id, company_name: item.company_name });
  };

  const confirmDeleteInterview = async () => {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/${pendingDelete.id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSavedGuides((prev) => prev.filter((g) => g.id !== pendingDelete.id));
        setPendingDelete(null);
      } else {
        setDeleteError(
          labels.deleteNotOwner,
        );
      }
    } finally {
      setDeleteBusy(false);
    }
  };

  // Pre-fill fields when assessment changes
  useEffect(() => {
    setFormStep(1);
    if (selectedAssessmentId === "scratch") {
      updateSetup(BLANK_COMPANY_FIELDS);
      return;
    }
    const matched = assessments.find((a) => a.id.toString() === selectedAssessmentId);
    if (matched) {
      updateSetup({
        companyName: matched.company_name,
        sector: matched.sector,
        size: matched.size,
        region: matched.region ?? "",
      });
    }
  }, [selectedAssessmentId, assessments]);

  // Dynamic loader text sequences
  const isFrench = language.toLowerCase().startsWith("fr");

  const runInsights = async () => {
    const g = guideRef.current;
    if (!g) return;
    setInsightsLoading(true);
    setInsightsError(null);
    setInsightsText(null);
    try {
      // Flush the latest answers to the DB so the cross-reference reads the freshest guide.
      const savedId = await saveGuideToDb(g);
      if (savedId && guideRef.current && !guideRef.current.id) {
        guideRef.current = { ...guideRef.current, id: savedId };
      }
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/insights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guide_id: guideRef.current?.id ?? null, guide: guideRef.current }),
      });
      const data = res.ok ? await res.json() : null;
      if (!data) {
        setInsightsError(labels.insightsFailed);
      } else if (data.status === "no_history" || data.status === "no_assessment") {
        setInsightsError(
          labels.noOrionHistory,
        );
      } else {
        setInsightsText(data.insights || "");
        setInsightsSavedAt(new Date().toISOString());
      }
    } catch {
      setInsightsError(labels.networkError);
    } finally {
      setInsightsLoading(false);
    }
  };

  // Each step checks only its own rules before letting the consultant move on.
  const goToStep2 = () => {
    const problem = companyProblem(setup, isFrench);
    setError(problem?.message ?? null);
    if (!problem) setFormStep(2);
  };

  const goToStep3 = () => {
    const problem = profileProblem(setup, isFrench);
    setError(problem?.message ?? null);
    if (!problem) setFormStep(3);
  };

  const handleGenerate = async () => {
    // Submitting re-checks everything, because a consultant can go back and empty a field after
    // passing the step that guards it. A failed rule names its own step, so they land where the
    // problem is instead of on a message about a screen they cannot see.
    const problem = setupProblem(setup, isFrench);
    if (problem) {
      setError(problem.message);
      setFormStep(problem.step);
      return;
    }

    // InterviewGeneratingView owns its own stage index and mounts fresh, so it always starts
    // from the first line without being reset here.
    setStep("generating");
    setError(null);

    const payload = {
      assessment_id: selectedAssessmentId === "scratch" ? null : parseInt(selectedAssessmentId, 10),
      company_name: companyName,
      sector: sector || null,
      size: size || null,
      region: region || null,
      language: language,
      profile: profile === "Other" ? customProfileName.trim() : profile,
      custom_context: customContext || null,
      custom_profile_description: profile === "Other" ? customProfileDesc.trim() : null,
    };

    try {
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/interview-guide/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let errorMsg = labels.generateFailed;
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            errorMsg = errData.detail;
          }
        } catch { /* ignore */ }
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setGuide(withQuestionIds(data));

      setStep("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error occurred during generation.");
      setStep("form");
    }
  };

  const selectedAssessment = assessments.find((a) => a.id.toString() === selectedAssessmentId);

  // Live actions for questions edit flow
  const updateSectionQuestions = (
    sectionKey: SectionKey,
    updater: (prev: InterviewGuideQuestionItem[]) => InterviewGuideQuestionItem[]
  ) => {
    if (!guide) return;
    const arrayName = questionsFieldFor(sectionKey);
    setGuide({
      ...guide,
      [arrayName]: updater(guide[arrayName]),
    });
  };

  const handleToggleAnswered = (sectionKey: SectionKey, id: string) => {
    updateSectionQuestions(sectionKey, (prev) =>
      prev.map((q) => (q.id === id ? { ...q, isAnswered: !q.isAnswered } : q))
    );
  };

  const handleUpdateAnswerNote = (sectionKey: SectionKey, id: string, note: string) => {
    updateSectionQuestions(sectionKey, (prev) =>
      prev.map((q) => (q.id === id ? { ...q, answerNote: note } : q))
    );
  };

  const toggleNoteExpanded = (id: string) => {
    setExpandedNoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // Excel is a deliverable here, not a data dump -- the styling lives in its own module.
  const handleExportExcel = async () => {
    if (!guide) return;
    try {
      await exportInterviewGuideToExcel(guide, { isFrench, profile });
    } catch (err) {
      console.error("Excel generation failed:", err);
      setError(labels.excelExportFailed);
    }
  };

  const handleDeleteQuestion = (sectionKey: SectionKey, id: string) => {
    updateSectionQuestions(sectionKey, (prev) => prev.filter((q) => q.id !== id));
    if (editingId === id) {
      setEditingId(null);
    }
  };

  const handleStartEdit = (q: InterviewGuideQuestionItem) => {
    setEditingId(q.id);
    setEditQuestionText(q.question);
    setEditRationaleText(q.rationale);
    setEditFollowUpText(q.follow_up);
  };

  const handleSaveEdit = (sectionKey: SectionKey, id: string) => {
    updateSectionQuestions(sectionKey, (prev) =>
      prev.map((q) =>
        q.id === id
          ? {
              ...q,
              question: editQuestionText,
              rationale: editRationaleText,
              follow_up: editFollowUpText,
            }
          : q
      )
    );
    setEditingId(null);
  };

  const handleCancelEdit = (sectionKey: SectionKey, id: string) => {
    // If it's a newly added empty question, cancel deletes it
    const arrayName = questionsFieldFor(sectionKey);
    const item = guide?.[arrayName]?.find((q) => q.id === id);
    if (item && !item.question.trim() && !item.rationale.trim() && !item.follow_up.trim()) {
      handleDeleteQuestion(sectionKey, id);
    }
    setEditingId(null);
  };

  const handleAddQuestion = (sectionKey: SectionKey) => {
    const newId = `new-${Date.now()}-${Math.random()}`;
    const newQuestion: InterviewGuideQuestionItem = {
      id: newId,
      question: "",
      rationale: "",
      follow_up: "",
      isAnswered: false,
    };

    updateSectionQuestions(sectionKey, (prev) => [...prev, newQuestion]);
    setEditingId(newId);
    setEditQuestionText("");
    setEditRationaleText("");
    setEditFollowUpText("");
  };

  const labels = interviewLabels(isFrench);
  const personas = interviewPersonas(isFrench);

  // Shared header component. The project band (topSlot) renders directly beneath it, so the
  // product identity stays first and the band reads as context for this page.
  const renderHeader = (rightContent?: React.ReactNode) => (
    <>
    <header className="bg-white border-b border-slate-200/80 px-6 py-4 flex items-center justify-between sticky top-0 z-30 backdrop-blur-sm bg-white/95 no-print">
      <div className="flex items-center gap-3">
        <button
          onClick={
            step === "result"
              ? () => { setStep("form"); setFormStep(1); }
              : step === "form" || step === "projectReport"
                ? () => setStep("history")
                : onBack
          }
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-500 hover:text-slate-800 hover:border-slate-300 transition-all"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {step === "result"
            ? labels.modifySettings
            : step === "form" || step === "projectReport"
              ? labels.backToInterviews
              : labels.back}
        </button>
        <div className="h-6 w-px bg-slate-200" />
        <div className="flex items-center gap-2.5">
          <img src={`${import.meta.env.BASE_URL}ey_logo.svg`} alt="EY" className="h-7 w-auto block" />
          <div>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight flex items-center gap-1.5 leading-none">
              {labels.title}
              <span className="h-1.5 w-1.5 rounded-full bg-yellow-400 inline-block animate-pulse" />
            </h1>
            <p className="text-[9px] text-slate-400 font-medium tracking-widest uppercase mt-0.5 leading-none">{labels.subtitle}</p>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {step === "result" && guide?.id && (
          <AddToProjectButton
            kind="interview_guide"
            refId={String(guide.id)}
            stepKey="interview"
            title={guide.company_name}
            suggestedName={guide.company_name}
            compact
          />
        )}
        {step === "result" && guide?.id && (
          <ShareButton kind="interview_guide" refId={String(guide.id)} compact />
        )}
        {rightContent}
        <div className="flex gap-0.5 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
          <button
            type="button"
            onClick={() => updateSetup({ language: "fr" })}
            className={`rounded-md px-3 py-1.5 text-[10px] font-bold transition-all ${
              language === "fr" ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-700"
            }`}
          >FR</button>
          <button
            type="button"
            onClick={() => updateSetup({ language: "en" })}
            className={`rounded-md px-3 py-1.5 text-[10px] font-bold transition-all ${
              language === "en" ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-700"
            }`}
          >EN</button>
        </div>
        <span className="h-6 w-px bg-slate-200" />
        <StudioNav isFrench={isFrench} />
      </div>
    </header>
    {topSlot}
    </>
  );

  // ============================= HISTORY VIEW =============================
  if (step === "history") {
    return (
      <div className="min-h-screen bg-[#F7F8FA] text-slate-800 font-sans pb-16">
        {renderHeader()}
        <div className="mx-auto mt-8 max-w-7xl px-6">
          <div className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {labels.guidesHeading}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {labels.guidesLead}
            </p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <InterviewHistoryTable
              interviews={savedGuides}
              onOpen={handleLoadGuideFromDb}
              onNew={startNewInterview}
              onDelete={handleDeleteInterview}
              isFrench={isFrench}
              projectReport={projectReport}
              onViewReport={() => setStep("projectReport")}
            />
          </div>
        </div>

        {/* In-app delete confirmation */}
        {pendingDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-50 text-rose-600">
                  <Trash2 className="h-5 w-5" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    {labels.deleteTitle}
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    {isFrench
                      ? `Le guide d'entretien de « ${pendingDelete.company_name} » sera définitivement supprimé. Cette action est irréversible.`
                      : `The interview guide for "${pendingDelete.company_name}" will be permanently deleted. This cannot be undone.`}
                  </p>
                </div>
              </div>
              {deleteError && (
                <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{deleteError}</div>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPendingDelete(null);
                    setDeleteError(null);
                  }}
                  disabled={deleteBusy}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  {labels.cancel}
                </button>
                <button
                  type="button"
                  onClick={() => void confirmDeleteInterview()}
                  disabled={deleteBusy}
                  className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-rose-700 disabled:opacity-60"
                >
                  {deleteBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  {labels.delete}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ========================= PROJECT REPORT VIEW =========================
  // Its own page, like every other result in the app. Rendered from the hub rather than the
  // table so it gets the same header, back button and project band as the rest of the module.
  if (step === "projectReport") {
    return (
      <div className="min-h-screen bg-[#F7F8FA] text-slate-800 font-sans pb-16">
        {renderHeader(
          <button
            onClick={() => void projectReport.generate()}
            disabled={projectReport.generating}
            className="btn-secondary-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={`h-3 w-3 ${projectReport.generating ? "animate-spin" : ""}`} />
            {projectReport.generating ? labels.reportGenerating : labels.regenerateReport}
          </button>,
        )}
        <div className="mx-auto mt-8 max-w-5xl px-6">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                {labels.projectReportHeading}
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                {labels.projectReportLead}
                {projectReport.generatedAt && (
                  <>
                    {" · "}
                    {labels.reportGeneratedAt}{" "}
                    {new Date(projectReport.generatedAt).toLocaleDateString(labels.dateLocale, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </>
                )}
              </p>
            </div>
            {projectReport.stale && (
              <p className="rounded-full bg-amber-50 px-3 py-1 text-[11px] font-semibold text-amber-700">
                {labels.reportStale}
              </p>
            )}
          </div>
          {projectReport.error && (
            <p className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {projectReport.error}
            </p>
          )}
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            {projectReport.report ? (
              <InterviewProjectReportView report={projectReport.report} />
            ) : (
              // Reachable only by switching project while this page is open. Redirecting from
              // render would fight React, and would also flash during the reload that follows.
              <p className="py-8 text-center text-sm text-slate-400">
                {projectReport.loading ? "…" : labels.projectReportEmpty}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ============================= FORM VIEW =============================
  if (step === "form") {
    return (
      <InterviewSetupView
        setup={setup}
        updateSetup={updateSetup}
        formStep={formStep}
        sourceAssessments={sourceAssessments}
        selectedAssessmentId={selectedAssessmentId}
        setSelectedAssessmentId={setSelectedAssessmentId}
        selectedAssessment={selectedAssessment}
        goToStep2={goToStep2}
        goToStep3={goToStep3}
        handleGenerate={handleGenerate}
        error={error}
        labels={labels}
        personas={personas}
        inProject={Boolean(activeProject)}
        goBackToStep={(target) => { setError(null); setFormStep(target); }}
        header={renderHeader()}
      />
    );
  }

  if (step === "generating") return <InterviewGeneratingView isFrench={isFrench} />;
  if (step === "opening") return <InterviewOpeningView isFrench={isFrench} />;

  // Presentation (titles, colours, durations) is a table; the questions come from the guide.
  const sectionConfigs = interviewSections(isFrench).map((section) => ({
    ...section,
    questions: guide?.[questionsFieldFor(section.key)] || [],
  }));

  // ============================= RESULT VIEW =============================
  return (
    <div className="min-h-screen bg-[#F7F8FA] text-slate-800 font-sans pb-16 print:bg-white print:text-slate-900 print:p-0">
      <style dangerouslySetInnerHTML={{ __html: `
        @media print {
          .no-print, button, .flex-1.h-px, .pt-2.no-print, [title="Modifier"], [title="Supprimer"], .no-print-counter {
            display: none !important;
          }
          body, html, #root, main {
            background: white !important;
            color: black !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          main, .max-w-4xl {
            max-width: 100% !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
          }
          .print-card {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            margin-bottom: 25px !important;
            border: 1px solid #cbd5e1 !important;
            background: white !important;
            box-shadow: none !important;
            border-radius: 12px !important;
          }
          .print-question-item {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            border-bottom: 1px solid #e2e8f0 !important;
          }
          * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .print-grid-stack {
            display: block !important;
          }
          .print-grid-stack > div {
            margin-bottom: 15px !important;
            width: 100% !important;
            display: block !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
          }
        }
      `}} />
      
      {renderHeader(
        guide ? (
          <div className="flex items-center gap-2">
            <button
              onClick={handleExportExcel}
              className="no-print flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 px-3.5 py-2 text-xs font-bold text-emerald-700 shadow-sm transition-all"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              {labels.exportExcel}
            </button>
            <button
              onClick={() => window.print()}
              className="no-print flex items-center gap-1.5 rounded-lg bg-yellow-400 hover:bg-yellow-500 px-3.5 py-2 text-xs font-bold text-slate-900 shadow-sm transition-all"
            >
              <Printer className="h-3.5 w-3.5" />
              {labels.print}
            </button>
          </div>
        ) : undefined
      )}

      <main className="max-w-4xl mx-auto px-6 mt-8 print:p-0 print:mt-0">
        {guide && (
          <div className="space-y-6">

            {/* Report Header Card */}
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm print:border-none print:shadow-none">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-2xl font-black text-slate-950 tracking-tight">{guide.company_name}</h2>
                  <p className="text-xs text-slate-400 font-medium mt-1 flex items-center gap-2">
                    <span className="font-mono uppercase tracking-wider">
                      {labels.guideHeading}
                    </span>
                    <span className="h-1 w-1 rounded-full bg-slate-300" />
                    <span className="font-semibold text-slate-600">{personas.find(p => p.code === profile)?.title || profile}</span>
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <span className="no-print inline-flex items-center gap-1.5 bg-slate-100 text-slate-500 text-[10px] font-mono px-2.5 py-1.5 rounded-md border border-slate-200 font-semibold uppercase tracking-wider">
                    <Sparkles className="h-3 w-3 text-yellow-500" />
                    AI Generated
                  </span>
                  <p className="text-[10px] text-slate-400 font-mono mt-1.5">
                    {new Date().toLocaleDateString(labels.dateLocale, { day: "numeric", month: "long", year: "numeric" })}
                  </p>
                </div>
              </div>
            </div>

            {/* Synthesis + Gaps layout */}
            <div className="grid gap-5 md:grid-cols-5 print-grid-stack">
              {/* Executive Summary */}
              {guide.executive_summary && (
                <div className="md:col-span-3 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm print:border print:shadow-none">
                  <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-yellow-500 print:text-slate-600" />
                    {labels.summary}
                  </h3>
                  <p className="text-[13px] text-slate-600 leading-[1.8]">
                    {guide.executive_summary}
                  </p>
                </div>
              )}

              {/* Gaps */}
              {guide.unanswered_areas && guide.unanswered_areas.length > 0 && (
                <div className="md:col-span-2 bg-white border border-amber-200/60 rounded-2xl p-6 shadow-sm print:border print:shadow-none">
                  <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500 print:text-slate-600" />
                    {labels.gaps}
                  </h3>
                  <ul className="space-y-2.5">
                    {guide.unanswered_areas.map((gap, index) => (
                      <li key={index} className="flex items-start gap-2 text-[12px] text-slate-600 leading-relaxed">
                        <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                        {gap}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Questions Title Bar */}
            <div className="flex items-center justify-between pt-2 no-print">
              <div className="flex items-center gap-3 flex-1 mr-4">
                <h3 className="text-sm font-bold text-slate-900">{labels.questions}</h3>
                <div className="flex-1 h-px bg-slate-200" />
              </div>
              <span className="text-[10px] font-mono text-slate-400 bg-white border px-2.5 py-1 rounded-md shadow-sm shrink-0">
                {sectionConfigs.reduce((acc, s) => acc + s.questions.length, 0)} {labels.totalQuestions}
              </span>
            </div>

            {/* Question Sections */}
            {sectionConfigs.map((section) => {
              const qs = section.questions;
              return (
                <section key={section.key} className="print-card bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                  
                  {/* Section Header */}
                  <div className={`px-6 py-4 border-b ${section.borderColor} ${section.bgColor} flex items-center justify-between`}>
                    <div className="flex items-center gap-2.5">
                      <div className={`h-8 w-8 rounded-lg flex items-center justify-center shadow-sm ${section.iconBg}`}>
                        {section.icon}
                      </div>
                      <div>
                        <h4 className="text-[13px] font-bold text-slate-800 leading-none">{section.title}</h4>
                        <p className="text-[10px] text-slate-400 font-medium mt-1 leading-none">
                          {labels.sectionDuration} {section.duration}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 no-print">
                      <button
                        onClick={() => handleAddQuestion(section.key)}
                        className="flex items-center gap-1 text-[11px] font-bold text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm hover:bg-slate-50 hover:text-slate-800 transition-all"
                      >
                        <Plus className="h-3.5 w-3.5 text-slate-400" />
                        {labels.add}
                      </button>
                    </div>
                  </div>

                  {/* Questions Grid/List */}
                  <div className="divide-y divide-slate-150/80 bg-slate-50/15">
                    {qs.length === 0 ? (
                      <div className="p-8 text-center text-xs text-slate-400 italic">
                        {labels.emptySection}
                      </div>
                    ) : (
                      qs.map((q, idx) => {
                        const isEditing = editingId === q.id;
                        const isAnswered = q.isAnswered;

                        return (
                          <div 
                            key={q.id} 
                            className={`px-6 py-6 transition-all relative print-question-item ${
                              isAnswered ? "bg-emerald-50/25 border-l-4 border-l-emerald-500" : "bg-white"
                            }`}
                          >
                            {/* Interactive Top Row Controls - Hidden on Print */}
                            <div className="no-print flex items-center justify-between mb-4 border-b border-slate-100 pb-3">
                              
                              {/* Answered Toggle Checkbox */}
                              <button
                                onClick={() => handleToggleAnswered(section.key, q.id)}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-semibold transition-all ${
                                  isAnswered
                                    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                                    : "bg-slate-50 border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                                }`}
                              >
                                {isAnswered ? (
                                  <>
                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                                    <span>{labels.answered}</span>
                                  </>
                                ) : (
                                  <>
                                    <Circle className="h-3.5 w-3.5 text-slate-400" />
                                    <span>{labels.toAsk}</span>
                                  </>
                                )}
                              </button>

                              {/* Edit & Delete Action Buttons */}
                              {!isEditing && (
                                <div className="flex items-center gap-1.5">
                                  <button
                                    onClick={() => handleStartEdit(q)}
                                    className="p-2 rounded-lg border border-slate-200 bg-white text-slate-400 hover:text-slate-700 hover:border-slate-350 shadow-sm transition-all"
                                    title={labels.edit}
                                  >
                                    <Pencil className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteQuestion(section.key, q.id)}
                                    className="p-2 rounded-lg border border-rose-200 bg-white text-rose-400 hover:text-rose-650 hover:bg-rose-50/50 shadow-sm transition-all"
                                    title={labels.delete}
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* QUESTION BLOCK */}
                            {isEditing ? (
                              /* Inline Editing Mode */
                              <div className="space-y-4 bg-slate-50/50 border border-slate-200 rounded-xl p-4 no-print">
                                <div className="flex flex-col gap-1">
                                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{labels.mainQuestionLabel}</label>
                                  <textarea
                                    value={editQuestionText}
                                    onChange={(e) => setEditQuestionText(e.target.value)}
                                    rows={2}
                                    placeholder={labels.mainQuestionPlaceholder}
                                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-yellow-400 focus:outline-none bg-white"
                                  />
                                </div>

                                <div className="grid gap-3 sm:grid-cols-2">
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{labels.whyLabel}</label>
                                    <textarea
                                      value={editRationaleText}
                                      onChange={(e) => setEditRationaleText(e.target.value)}
                                      rows={3}
                                      placeholder={labels.whyPlaceholder}
                                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-yellow-400 focus:outline-none bg-white"
                                    />
                                  </div>
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{labels.followUpsLabel}</label>
                                    <textarea
                                      value={editFollowUpText}
                                      onChange={(e) => setEditFollowUpText(e.target.value)}
                                      rows={3}
                                      placeholder={labels.followUpsPlaceholder}
                                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-yellow-400 focus:outline-none bg-white"
                                    />
                                  </div>
                                </div>

                                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                                  <button
                                    onClick={() => handleCancelEdit(section.key, q.id)}
                                    className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100 transition-all"
                                  >
                                    <X className="h-3.5 w-3.5" />
                                    {labels.cancel}
                                  </button>
                                  <button
                                    onClick={() => handleSaveEdit(section.key, q.id)}
                                    className="flex items-center gap-1 rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 transition-all"
                                  >
                                    <Save className="h-3.5 w-3.5 text-yellow-400" />
                                    {labels.save}
                                  </button>
                                </div>
                              </div>
                            ) : (
                              /* Standard Render Mode */
                              <div className="space-y-4">
                                <div className="flex items-start gap-3">
                                  {/* Print only counter */}
                                  <div className="print:flex hidden h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-900 text-[9px] font-mono font-bold text-white">
                                    Q{idx + 1}
                                  </div>
                                  <p className="text-[14px] font-bold text-slate-900 leading-relaxed print:text-black">
                                    {q.question || <span className="text-slate-300 italic">{labels.emptyQuestion}</span>}
                                  </p>
                                </div>

                                {/* Expanded Side-by-side Rationale & Follow-up Cards */}
                                <div className="grid gap-4 sm:grid-cols-2 print-grid-stack">
                                  <div className="bg-slate-50 border border-slate-200/50 rounded-xl p-4 text-[12px] leading-relaxed text-slate-500 shadow-sm/5 whitespace-pre-line">
                                    <strong className="text-slate-700 block mb-1.5 font-extrabold uppercase tracking-wider font-mono text-[9.5px]">
                                      {labels.whyHeading}
                                    </strong>
                                    {q.rationale || <span className="text-slate-300 italic">{labels.noObjective}</span>}
                                  </div>
                                  
                                  <div className="bg-amber-50/80 border border-amber-200/80 rounded-xl p-4 text-[12px] leading-relaxed font-bold text-amber-950 shadow-sm/5 whitespace-pre-line">
                                    <strong className="text-amber-900 block mb-1.5 font-extrabold uppercase tracking-wider font-mono text-[9.5px]">
                                      {labels.followUpsHeading}
                                    </strong>
                                    {q.follow_up || <span className="text-slate-400 italic font-normal">{labels.noProbes}</span>}
                                  </div>
                                </div>

                                {/* ── Answer / Notes Area ── */}
                                <div className="no-print">
                                  <button
                                    onClick={() => toggleNoteExpanded(q.id)}
                                    className={`flex items-center gap-2 w-full px-4 py-2.5 rounded-xl border text-xs font-semibold transition-all ${
                                      q.answerNote
                                        ? "bg-blue-50/60 border-blue-200/60 text-blue-700 hover:bg-blue-100/60"
                                        : "bg-slate-50/50 border-slate-200/50 text-slate-400 hover:text-slate-600 hover:bg-slate-100/50"
                                    }`}
                                  >
                                    <StickyNote className="h-3.5 w-3.5" />
                                    <span>{labels.noteLabel}</span>
                                    {q.answerNote && (
                                      <span className="ml-1 px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-600 text-[9px] font-bold">
                                        {q.answerNote.length > 0 ? "✓" : ""}
                                      </span>
                                    )}
                                    <span className="ml-auto">
                                      {expandedNoteIds.has(q.id) ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                                    </span>
                                  </button>
                                  {(expandedNoteIds.has(q.id) || (q.answerNote && q.answerNote.length > 0)) && (
                                    <div className="mt-2 animate-in slide-in-from-top-2 duration-200">
                                      <textarea
                                        value={q.answerNote || ""}
                                        onChange={(e) => handleUpdateAnswerNote(section.key, q.id, e.target.value)}
                                        rows={4}
                                        placeholder={labels.answerPlaceholder}
                                        className="w-full rounded-xl border border-blue-200/60 bg-white px-4 py-3 text-[12.5px] text-slate-700 leading-relaxed placeholder:text-slate-300 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 focus:outline-none transition-all resize-y shadow-inner"
                                      />
                                    </div>
                                  )}
                                </div>

                                {/* Print-only answer area */}
                                {q.answerNote && (
                                  <div className="hidden print:block border border-slate-200 rounded-lg p-3 text-[11px] text-slate-700 leading-relaxed bg-blue-50/20">
                                    <strong className="text-slate-800 block mb-1 font-extrabold uppercase tracking-wider font-mono text-[9px]">
                                      {labels.notesHeading}
                                    </strong>
                                    <span className="whitespace-pre-wrap">{q.answerNote}</span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </section>
              );
            })}

            {/* Analysis of the interview, cross-referenced against the Orion self-assessment.
                Stored on the guide, so it stays here on reload instead of living in a dialog. */}
            {guide?.assessment_id != null && (
              <section className="mt-10 border-t border-slate-200 pt-8">
                {insightsText ? (
                  <>
                    <div className="no-print mb-4 flex flex-wrap items-center gap-3">
                      <span className="flex items-center gap-2 text-[13px] font-bold text-slate-800">
                        <Sparkles className="h-4 w-4 text-ey-gold" />
                        {labels.analysisTitle}
                      </span>
                      {insightsSavedAt && (
                        <span className="text-[11px] text-slate-400">
                          {labels.generatedOn}
                          {new Date(insightsSavedAt).toLocaleDateString(undefined,
                            { day: "numeric", month: "short", year: "numeric" })}
                        </span>
                      )}
                      <button
                        onClick={runInsights}
                        disabled={insightsLoading}
                        className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-semibold text-slate-500 transition hover:border-slate-300 hover:text-slate-700 disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3 w-3 ${insightsLoading ? "animate-spin" : ""}`} />
                        {insightsLoading
                          ? labels.analysing
                          : labels.regenerate}
                      </button>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
                      <ChatMarkdown text={insightsText} />
                    </div>
                  </>
                ) : (
                  <div className="no-print flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 px-6 py-8">
                    <button
                      onClick={runInsights}
                      disabled={insightsLoading}
                      className="inline-flex items-center gap-2 rounded-xl bg-ey-navy px-5 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-ey-navy-hover disabled:opacity-50"
                    >
                      <Sparkles className="h-4 w-4 text-ey-gold" />
                      {insightsLoading
                        ? labels.analysisRunning
                        : labels.analyseInterview}
                    </button>
                    <p className="mt-2 max-w-md text-center text-[11px] text-slate-400">
                      {labels.analysisExplainer}
                    </p>
                    {insightsError && (
                      <p className="mt-3 text-center text-[12px] text-rose-600">{insightsError}</p>
                    )}
                  </div>
                )}
              </section>
            )}

          </div>
        )}
      </main>

      {/* Floating interview assistant — sends the CURRENT (live-edited) guide on every turn. */}
      {step === "result" && guide && (
        <div className="no-print">
          <ModuleChat
            endpoint={`${API_BASE_URL}/assessments/interview-guide/chat`}
            messages={chatMessages}
            onAppendMessage={appendChatMessage}
            title={labels.assistantTitle}
            subtitle={guide.company_name}
            emptyTitle={labels.assistantSubtitle}
            emptyHint={
              labels.assistantHint
            }
            placeholder={labels.assistantPlaceholder}
            // Flush the current guide (with the latest answers/edits) to the DB BEFORE asking, so
            // the backend reads the freshest saved copy rather than trusting the chat payload.
            beforeSend={async () => {
              const g = guideRef.current;
              if (!g) return;
              const savedId = await saveGuideToDb(g);
              if (savedId && guideRef.current && !guideRef.current.id) {
                guideRef.current = { ...guideRef.current, id: savedId };
              }
            }}
            buildBody={(query, history) => ({
              query,
              history,
              guide_id: guideRef.current?.id ?? null,
              guide: guideRef.current, // fallback for an unsaved guide
            })}
          />
        </div>
      )}
    </div>
  );
}
