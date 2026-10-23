"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Building2, CheckCircle2, Circle, FileText, Loader2, Send, Sparkles, Trash2, X } from "lucide-react";
import { Avatar } from "../../components/ui/avatar-1";
import AssessmentGeneratingPage from "./generating-page";
import AssessmentReport from "./report/AssessmentReport";
import MultiChoiceOptions from "../../components/ui/multi-choice-input";
import type { FinalReport } from "../../types/final-report";

type ChatMessage = { id: string; text: string; isUser: boolean };
type AxisProgress = { axis: string; covered: number; total: number };
type AssessmentState = { id: number; status: string; axis: string | null; version: number; progress: AxisProgress[] };
type Option = { code: string; label: string };
type CompanyProfileForm = {
  companyName: string;
  sector: string;
  companySize: string;
  region: string;
};
type Props = {
  onBack?: () => void;
  language?: string;
  topSlot?: React.ReactNode;
  /** Whether to reopen the conversation that was in progress when the consultant last left.
   *
   *  True only when the browser loaded straight onto this module's route -- that is, the page was
   *  reloaded mid-assessment. Opening the module from the services hub is a request for the
   *  history list, not for whatever chat happened to be open last time. */
  resumeLastConversation?: boolean;
};

/** Which assessment is open, so a page reload returns to it instead of the history list.
 *  Only the id is stored -- the conversation itself is rebuilt from the server. */
const ACTIVE_ASSESSMENT_KEY = "cx_active_assessment";

/** Whether this page load has already had its chance to reopen the conversation.
 *
 *  Module scope, so it survives the component unmounting but resets on a real page load -- which
 *  is exactly the line we need. Reopening exists to undo an accidental reload, once. Without this
 *  latch the module also reopens when the consultant walks out and comes back later in the same
 *  session, and that is not a reload: they left that conversation on purpose. */
let restoreAlreadyOffered = false;

const rememberActiveAssessment = (id: number | null) => rememberId(ACTIVE_ASSESSMENT_KEY, id);
const rememberedAssessmentId = () => rememberedId(ACTIVE_ASSESSMENT_KEY);
type OnboardingStage = "await_company_name" | "await_sector_choice" | "await_size_choice" | "assessment_active" | "completed";

import { authFetchUrl } from "../../lib/api";
import { useClientLink } from "./use-client-link";
import { useDeleteAssessment } from "./use-delete-assessment";
import { useActiveProject } from "../../context/ActiveProjectContext";
import AssessmentHistoryTable, { type AssessmentItem } from "./history-table";
import StudioNav from "../../components/ui/studio-nav";
import { uuid } from "../../lib/uuid";
import { assessmentCopy } from "./copy";
import { rememberId, rememberedId } from "../../lib/remembered-id";
import {
  AXIS_ORDER, axisIndex, getAssessmentStartIntro, getAxisDisplayName, getAxisProgressSubtitle,
  getInitialGreeting,
} from "./copy";
import ModuleHeader from "../../components/ui/module-header";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const normalizeAxis = (value: string | null | undefined) => (value ?? "").trim().toUpperCase();

/** Split an assistant message into the lead-in, the question itself, and anything after it.
 *
 *  The assistant rarely asks a bare question -- it acknowledges the last answer, gives a line of
 *  context, then asks. Rendering that as one grey paragraph buries the only part the client has
 *  to act on, so the question is bolded and the rest is not.
 *
 *  Finding it: take the LAST "?" in the message, then walk backwards to the previous sentence
 *  ending. Last rather than first, because the context sentences sometimes contain a question
 *  themselves ("Wondering where to start?") and the real ask is the one that closes the message.
 *  A message with no "?" is returned whole and stays unstyled. */
const splitAssistantQuestion = (text: string) => {
  const trimmedEnd = text.trimEnd();
  const questionEnd = trimmedEnd.lastIndexOf("?");
  if (questionEnd < 0) {
    return { prefix: text, question: "", suffix: "" };
  }

  let questionStart = 0;
  for (let index = questionEnd - 1; index >= 0; index -= 1) {
    if ([".", "?", "!", "\n"].includes(trimmedEnd[index])) {
      questionStart = index + 1;
      break;
    }
  }

  while (questionStart < trimmedEnd.length && /\s/.test(trimmedEnd[questionStart])) {
    questionStart += 1;
  }

  return {
    prefix: text.slice(0, questionStart),
    question: text.slice(questionStart, questionEnd + 1),
    suffix: text.slice(questionEnd + 1),
  };
};

const AssistantMessageText = ({ text }: { text: string }) => {
  const { prefix, question, suffix } = splitAssistantQuestion(text);

  if (!question) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }

  return (
    <span className="whitespace-pre-wrap">
      {prefix}
      <strong className="font-bold text-slate-950">{question}</strong>
      {suffix}
    </span>
  );
};

export default function AssessmentChatStatic(
  { onBack, language = "fr", topSlot, resumeLastConversation = false }: Props,
) {
  const copy = assessmentCopy(language === "fr");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: uuid(),
      text: getInitialGreeting(language),
      isUser: false,
    },
  ]);
  const [isFocused, setIsFocused] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [assessment, setAssessment] = useState<AssessmentState | null>(null);
  const [stage, setStage] = useState<OnboardingStage>("await_company_name");
  const [companyName, setCompanyName] = useState("");
  const [companyProfile, setCompanyProfile] = useState<CompanyProfileForm>({
    companyName: "",
    sector: "",
    companySize: "",
    region: "",
  });
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isReferenceLoading, setIsReferenceLoading] = useState(false);
  const [selectedSector, setSelectedSector] = useState<Option | null>(null);
  const [sectorOptions, setSectorOptions] = useState<Option[]>([]);
  const [sizeOptions, setSizeOptions] = useState<Option[]>([]);
  const [regionOptions, setRegionOptions] = useState<Option[]>([]);
  const [finalReport, setFinalReport] = useState<FinalReport | null>(null);
  const [showRecommendations, setShowRecommendations] = useState(false);
  const { attach: attachToProject, completeStep } = useActiveProject();
  // The module opens on a history table; "New assessment" switches to the company form.
  const [view, setView] = useState<"history" | "new">("history");
  const [assessmentsList, setAssessmentsList] = useState<AssessmentItem[]>([]);
  // "New assessment" has two modes: fill it in now (consultant chat), or send a passwordless link
  // to the client so they fill it themselves. In "send" mode we collect the recipient + emit a link.
  const [newMode, setNewMode] = useState<"fill" | "send">("fill");
  // The "send to a client" panel: its five fields, the link it produces, and copying it.
  // Aliased to the names the markup below already uses.
  const {
    name: clientName,
    setName: setClientName,
    role: clientRole,
    setRole: setClientRole,
    email: clientEmail,
    setEmail: setClientEmail,
    link: generatedLink,
    setLink: setGeneratedLink,
    copied: linkCopied,
    copyLink,
    reset: resetClientLink,
  } = useClientLink();
  // In-app delete confirmation (replaces window.confirm).
  // The delete confirmation. Removing the row from the visible list stays here; the hook owns
  // the three flags that have to agree while the request is in flight.
  const {
    pending: pendingDelete,
    busy: deleteBusy,
    error: deleteError,
    ask: handleDeleteAssessment,
    cancel: cancelDeleteAssessment,
    confirm: confirmDeleteAssessment,
  } = useDeleteAssessment(
    (deletedId) => setAssessmentsList((prev) => prev.filter((x) => x.id !== deletedId)),
    language === "fr",
  );
  const [showGeneratingPage, setShowGeneratingPage] = useState(false);
  const [openingReport, setOpeningReport] = useState(false);
  const [isReportFetching, setIsReportFetching] = useState(false);
  const [isGeneratingMinDelayDone, setIsGeneratingMinDelayDone] = useState(false);
  const [submittedAnswersCount, setSubmittedAnswersCount] = useState(0);
  const [questionOptions, setQuestionOptions] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const activeQuestionRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);      // the chat scroll container
  const lastScrolledQuestion = useRef<number>(-1);     // index of the question we last scrolled to

  const progressStats = useMemo(() => {
    const rows = assessment?.progress ?? [];
    const currentAxis = normalizeAxis(assessment?.axis);
    const totalCovered = rows.reduce((sum, row) => sum + Math.max(0, row.covered ?? 0), 0);
    const totalQuestions = rows.reduce((sum, row) => sum + Math.max(0, row.total ?? 0), 0);
    const realPercent = totalQuestions > 0 ? Math.round((totalCovered / totalQuestions) * 100) : 0;
    const conversationalTarget = Math.max(totalQuestions + 6, 12);
    const turnPercent = Math.round((submittedAnswersCount / conversationalTarget) * 100);
    const percent =
      assessment?.status === "completed"
        ? 100
        : Math.min(95, Math.max(realPercent, Math.max(0, turnPercent)));
    const currentAxisIndex = axisIndex(currentAxis);
    const barClass =
      currentAxis === "MANAGE"
        ? "bg-blue-500"
        : currentAxis === "ANALYZE"
          ? "bg-amber-500"
          : currentAxis === "IMPROVE"
            ? "bg-emerald-500"
            : "bg-violet-500";
    return {
      totalCovered,
      totalQuestions,
      percent,
      realPercent,
      currentAxisIndex,
      barClass,
    };
  }, [assessment, submittedAnswersCount]);
  const axisDone = useMemo(() => {
    const currentAxis = normalizeAxis(assessment?.axis);
    const currentIndex = axisIndex(currentAxis);
    return new Map(
      AXIS_ORDER.map((axis, index) => {
        const done = assessment?.status === "completed" ? true : index < currentIndex;
        return [axis, done];
      })
    );
  }, [assessment]);

  const appendAssistant = (text: string) => {
    setMessages((prev) => [...prev, { id: uuid(), text, isUser: false }]);
  };
  const appendUser = (text: string) => {
    setMessages((prev) => [...prev, { id: uuid(), text, isUser: true }]);
  };

  const fetchAssessmentSnapshot = async (assessmentId: number): Promise<AssessmentState> => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments/${assessmentId}`);
    if (!response.ok) throw new Error("Failed to fetch assessment");
    const payload = await response.json();
    return {
      id: payload.id,
      status: payload.status,
      axis: payload.current_axis,
      version: payload.state_version,
      progress: payload.progress ?? [],
    };
  };

  /** The answered turns of a conversation, oldest first. */
  const fetchMessages = async (assessmentId: number): Promise<ChatMessage[]> => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments/${assessmentId}/messages`);
    if (!response.ok) return [];
    const data = await response.json();
    return (data.items ?? []).map((item: { id: number; role: string; content: string }) => ({
      id: String(item.id),
      text: item.content,
      isUser: item.role === "user",
    }));
  };

  /** Rebuild an in-progress conversation from the server and show it.
   *
   * Used by the create path, by resuming from the history list, and by the on-mount restore, so
   * all three land in the same state. The transcript comes from /messages, which holds only
   * ANSWERED turns; the question still waiting is in `pending_question` and is fetched
   * separately, so nothing is duplicated.
   */
  const restoreConversation = async (assessmentId: number) => {
    const snapshot = await fetchAssessmentSnapshot(assessmentId);
    setAssessment(snapshot);
    rememberActiveAssessment(assessmentId);

    const transcript = await fetchMessages(assessmentId);
    if (snapshot.status === "completed") {
      setMessages(transcript);
      setQuestionOptions([]);
      setStage("completed");
      return snapshot;
    }

    const next = await fetchNextQuestion(assessmentId);
    if (next.question) {
      transcript.push({ id: uuid(), text: next.question, isUser: false });
    }
    setMessages(transcript);
    setQuestionOptions(next.options ?? []);
    setStage("assessment_active");
    return snapshot;
  };

  const fetchNextQuestion = async (
    assessmentId: number
  ): Promise<{ status: string; question: string | null; options: string[] }> => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments/${assessmentId}/next-question`);
    if (!response.ok) throw new Error("Failed to fetch next question");
    const payload = await response.json();
    return {
      status: payload.status ?? "active",
      question: payload.question ?? payload.message ?? null,
      options: payload.options ?? [],
    };
  };

  const fetchReferenceOptions = async () => {
    const response = await authFetchUrl(`${API_BASE_URL}/reference/options`);
    if (!response.ok) throw new Error("Failed to fetch options");
    const payload = await response.json();
    
    const allowedSectorCodes = new Set([
      "retail",
      "ecommerce",
      "banking",
      "insurance",
      "telecom",
      "healthcare",
      "travel",
      "saas",
      "public"
    ]);
    const filteredSectors = (payload.sectors ?? []).filter((s: { code: string }) => allowedSectorCodes.has(s.code));
    
    setSectorOptions(filteredSectors);
    setSizeOptions(payload.company_sizes ?? []);
    setRegionOptions(payload.regions ?? []);
    return payload as { sectors: Option[]; company_sizes: Option[]; regions: Option[] };
  };

  const startAssessment = async (payload: {
    company_name: string;
    sector?: string;
    size?: string;
    region?: string;
  }) => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, language }),
    });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    const snapshot = await fetchAssessmentSnapshot(Number(data.assessment_id));
    setAssessment(snapshot);
    rememberActiveAssessment(snapshot.id);
    setStage(snapshot.status === "completed" ? "completed" : "assessment_active");
    const result = await fetchNextQuestion(snapshot.id);
    if (result.question) {
      setMessages((prev) => {
        const combined = `${getInitialGreeting(language)}\n\n${getAssessmentStartIntro(language)} ${result.question}`.trim();
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && !lastMessage.isUser) {
          return [...prev.slice(0, -1), { ...lastMessage, text: combined }];
        }
        return [...prev, { id: uuid(), text: combined, isUser: false }];
      });
      setQuestionOptions(result.options);
    }
  };

  const updateCompanyProfile = (field: keyof CompanyProfileForm, value: string) => {
    setCompanyProfile((current) => ({ ...current, [field]: value }));
    if (profileError) setProfileError(null);
  };

  const handleProfileSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newMode === "send") {
      await handleGenerateLink();
      return;
    }
    const profile = {
      companyName: companyProfile.companyName.trim(),
      sector: companyProfile.sector.trim(),
      companySize: companyProfile.companySize.trim(),
      region: companyProfile.region.trim(),
    };

    if (!profile.companyName || !profile.sector || !profile.companySize || !profile.region) {
      setProfileError("Please complete company name, sector, company size, and region before starting.");
      return;
    }

    setIsTyping(true);
    try {
      setCompanyName(profile.companyName);
      await startAssessment({
        company_name: profile.companyName,
        sector: profile.sector,
        size: profile.companySize,
        region: profile.region,
      });
    } catch {
      setProfileError("I could not start the assessment yet. Please check the selected profile and try again.");
    } finally {
      setIsTyping(false);
    }
  };

  // Create the assessment WITHOUT starting the consultant chat (used by "Send to client").
  const createAssessmentOnly = async (payload: {
    company_name: string;
    sector?: string;
    size?: string;
    region?: string;
  }): Promise<number> => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, language }),
    });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    return Number(data.assessment_id);
  };

  // "Send to client" submit: create the assessment, mint a passwordless link, show it to copy.
  // The consultant only provides the company name + who they're sending it to. Sector and company
  // size are the client's to know, so we leave them out and let the backend infer them.
  const handleGenerateLink = async () => {
    const companyName = companyProfile.companyName.trim();
    if (!companyName) {
      setProfileError(
        language === "fr" ? "Veuillez indiquer le nom de l'entreprise." : "Please enter the company name.",
      );
      return;
    }
    if (!clientName.trim()) {
      setProfileError(
        language === "fr" ? "Indiquez le nom de la personne destinataire." : "Enter the name of the person you're sending this to.",
      );
      return;
    }
    setIsTyping(true);
    setProfileError(null);
    try {
      const id = await createAssessmentOnly({
        company_name: companyName,
      });
      const res = await authFetchUrl(`${API_BASE_URL}/assessments/${id}/recipients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: clientName.trim(),
          client_role: clientRole.trim() || undefined,
          email: clientEmail.trim() || undefined,
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setGeneratedLink(data.link);
      refreshAssessments();
    } catch {
      setProfileError(
        language === "fr"
          ? "Impossible de générer le lien. Veuillez réessayer."
          : "Could not generate the link. Please try again.",
      );
    } finally {
      setIsTyping(false);
    }
  };


  // Reset the "new" form back to a clean state (after sending or when leaving).
  const resetNewForm = () => {
    setNewMode("fill");
    resetClientLink();
    setProfileError(null);
  };

  const fetchFinalReport = async (assessmentId: number): Promise<FinalReport | null> => {
    const response = await authFetchUrl(`${API_BASE_URL}/assessments/${assessmentId}/final-report`);
    if (!response.ok) return null;
    const payload = await response.json();
    setFinalReport(payload);
    // If launched from a project, link this assessment + complete the step (no-op otherwise).
    void attachToProject("assessment", String(assessmentId), "assessment", companyName || undefined);
    void completeStep("assessment");
    return payload;
  };

  const startReportGeneration = async (assessmentId: number) => {
    setIsTyping(false);
    setQuestionOptions([]);
    setIsReportFetching(true);
    setIsGeneratingMinDelayDone(false);
    setShowGeneratingPage(true);
    try {
      await fetchFinalReport(assessmentId);
    } finally {
      setIsReportFetching(false);
    }
  };

  const refreshAssessments = () => {
    authFetchUrl(`${API_BASE_URL}/assessments?limit=100`)
      .then((r) => r.json())
      .then((d) => {
        if (d && Array.isArray(d.items)) setAssessmentsList(d.items);
      })
      .catch(() => {});
  };

  // Delete flow (owner only — the server 404s otherwise). Uses an in-app modal, not window.confirm.

  // Open a past assessment: a completed one shows its report; an in-progress one resumes the chat.
  const loadAssessment = async (id: number, status: string) => {
    // For a completed report, show a loading screen and go straight to the report — never flash
    // the chat zone while the report is being fetched.
    if (status === "completed") {
      setOpeningReport(true);
      try {
        const snap = await fetchAssessmentSnapshot(id);
        setAssessment(snap);
        const item = assessmentsList.find((a) => a.id === id);
        if (item) setCompanyName(item.company_name);
        await fetchFinalReport(id);
        setShowRecommendations(true);
      } catch {
        setView("history");
      } finally {
        setOpeningReport(false);
      }
      return;
    }
    // In-progress: rebuild the conversation. This used to set `assessment` and stop, leaving
    // the chat empty and `stage` still on onboarding.
    setView("new");
    try {
      await restoreConversation(id);
      const item = assessmentsList.find((a) => a.id === id);
      if (item) setCompanyName(item.company_name);
    } catch {
      rememberActiveAssessment(null);
      setView("history");
    }
  };

  const parseChoice = (text: string, options: Option[]): Option | null => {
    const value = text.trim().toLowerCase();
    const byCode = options.find((opt) => opt.code.toLowerCase() === value);
    if (byCode) return byCode;
    const byLabel = options.find((opt) => opt.label.toLowerCase() === value);
    if (byLabel) return byLabel;
    const index = Number(value);
    if (!Number.isNaN(index) && index >= 1 && index <= options.length) return options[index - 1];
    return null;
  };

  const handleOnboardingMessage = async (userText: string) => {
    if (stage === "await_company_name") {
      setCompanyName(userText);
      setIsTyping(true);
      try {
        await startAssessment({ company_name: userText });
      } catch {
        const opts = await fetchReferenceOptions();
        setStage("await_sector_choice");
        const sectorList = opts.sectors.slice(0, 10).map((opt, idx) => `${idx + 1}. ${opt.label}`).join(" | ");
        appendAssistant(copy.chooseSector(sectorList));
      } finally {
        setIsTyping(false);
      }
      return;
    }

    if (stage === "await_sector_choice") {
      const option = parseChoice(userText, sectorOptions);
      if (!option) {
        appendAssistant(copy.sectorNotUnderstood);
        return;
      }
      setSelectedSector(option);
      setStage("await_size_choice");
      const sizeList = sizeOptions.slice(0, 10).map((opt, idx) => `${idx + 1}. ${opt.label}`).join(" | ");
      appendAssistant(copy.chooseSize(sizeList));
      return;
    }

    if (stage === "await_size_choice") {
      const option = parseChoice(userText, sizeOptions);
      if (!option) {
        appendAssistant(copy.sizeNotUnderstood);
        return;
      }
      setIsTyping(true);
      try {
        await startAssessment({
          company_name: companyName,
          sector: selectedSector?.code,
          size: option.code,
        });
      } catch {
        appendAssistant(copy.couldNotStart);
      } finally {
        setIsTyping(false);
      }
      return;
    }
  };

  const handleAssessmentMessage = async (userText: string) => {
    if (!assessment) return;
    setIsTyping(true);
    try {
      const response = await authFetchUrl(`${API_BASE_URL}/assessments/${assessment.id}/answers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": uuid(),
        },
        body: JSON.stringify({
          answer: userText,
          expected_axis: assessment.axis,
          expected_version: assessment.version,
        }),
      });

      if (response.status === 409) {
        const snapshot = await fetchAssessmentSnapshot(assessment.id);
        setAssessment(snapshot);
        appendAssistant(copy.outOfSync);
        return;
      }

      if (!response.ok) {
        appendAssistant(copy.couldNotProcessAnswer);
        return;
      }

      const snapshot = await fetchAssessmentSnapshot(assessment.id);
      setAssessment(snapshot);
      setSubmittedAnswersCount((prev) => prev + 1);
      if (snapshot.status === "completed") {
        setStage("completed");
        setQuestionOptions([]);
        return;
      }

      const result = await fetchNextQuestion(assessment.id);
      if (result.status === "completed") {
        const completedSnapshot = await fetchAssessmentSnapshot(assessment.id);
        setAssessment(completedSnapshot);
        setStage("completed");
        setQuestionOptions([]);
        return;
      }

      if (result.question) {
        appendAssistant(result.question);
        setQuestionOptions(result.options);
      }
    } finally {
      setIsTyping(false);
    }
  };

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!input.trim()) return;
    const text = input.trim();
    appendUser(text);
    setInput("");
    if (stage === "assessment_active") {
      await handleAssessmentMessage(text);
      return;
    }
    if (stage === "completed") return;
    await handleOnboardingMessage(text);
  };

  const clearChat = () => {
    setInput("");
    rememberActiveAssessment(null);
    setAssessment(null);
    setCompanyName("");
    setCompanyProfile({
      companyName: "",
      sector: "",
      companySize: "",
      region: "",
    });
    setProfileError(null);
    setSelectedSector(null);
    setSectorOptions([]);
    setSizeOptions([]);
    setFinalReport(null);
    setShowRecommendations(false);
    setShowGeneratingPage(false);
    setIsReportFetching(false);
    setIsGeneratingMinDelayDone(false);
    setSubmittedAnswersCount(0);
    setStage("await_company_name");
    setMessages([
      {
        id: uuid(),
        text: getInitialGreeting(language),
        isUser: false,
      },
    ]);
  };

  useEffect(() => {
    if (stage !== "await_company_name") return;
    if (sectorOptions.length > 0 && sizeOptions.length > 0) return;

    let cancelled = false;
    setIsReferenceLoading(true);
    fetchReferenceOptions()
      .catch(() => {
        if (!cancelled) {
          setProfileError("I could not load the sector and company size options. Please refresh and try again.");
        }
      })
      .finally(() => {
        if (!cancelled) setIsReferenceLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Depend on the list lengths too: a full reset (clearChat) empties them without changing
    // `stage`, and we must reload so the sector/size dropdowns are never left blank.
  }, [stage, sectorOptions.length, sizeOptions.length]);

  useEffect(() => {
    // The newest assistant message is the current question.
    const lastQuestionIdx = messages.map((m) => m.isUser).lastIndexOf(false);
    const container = scrollRef.current;
    if (
      stage === "assessment_active" &&
      lastQuestionIdx !== lastScrolledQuestion.current &&  // only when a NEW question appears
      activeQuestionRef.current &&
      container
    ) {
      lastScrolledQuestion.current = lastQuestionIdx;
      // Bring the new question to the top of the chat area (so only it is in view),
      // scrolling ONLY this container -- not the whole conversation/page.
      const top =
        activeQuestionRef.current.getBoundingClientRect().top -
        container.getBoundingClientRect().top +
        container.scrollTop -
        8;
      container.scrollTo({ top, behavior: "smooth" });
    } else if (stage !== "assessment_active") {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isTyping, stage]);

  // Load the assessment list for the history landing on mount.
  useEffect(() => {
    refreshAssessments();
  }, []);

  // Return to whatever assessment was open before the page reloaded. Without this the component
  // starts with `assessment` null and drops the consultant back on the history list mid-run.
  //
  // Only on a reload, though. Opening the module from the services hub must land on the history
  // list -- jumping straight back into an interrupted conversation gives the consultant no way to
  // reach their other assessments.
  useEffect(() => {
    // Two things have to hold: the browser loaded straight onto this module -- so this really is
    // a reload rather than a walk back in from the hub -- and no earlier mount in this same page
    // load has already used the offer up.
    if (!resumeLastConversation || restoreAlreadyOffered) return;
    restoreAlreadyOffered = true;

    const id = rememberedAssessmentId();
    if (id === null) return;
    let cancelled = false;
    (async () => {
      try {
        const snapshot = await restoreConversation(id);
        if (!cancelled && snapshot.status !== "completed") setView("new");
      } catch {
        // Deleted, finished, or no longer visible to this user: forget it and show the list.
        rememberActiveAssessment(null);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Runs once: restoring is a startup action, not something to repeat when callbacks change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The stored id means "this conversation is on screen right now", so keep that true: back on
  // the history list with nothing open, there is nothing to remember. Without this the id would
  // outlive the conversation, and a later reload could revive one the consultant had already
  // walked away from. A restore in flight re-stores it as soon as its snapshot lands.
  useEffect(() => {
    if (view === "history" && assessment === null) rememberActiveAssessment(null);
  }, [view, assessment]);

  useEffect(() => {
    if (!showGeneratingPage) return;
    if (!isGeneratingMinDelayDone) return;
    if (isReportFetching) return;
    if (!finalReport) return;
    setShowGeneratingPage(false);
    setShowRecommendations(true);
    setIsGeneratingMinDelayDone(false);
  }, [showGeneratingPage, isGeneratingMinDelayDone, isReportFetching, finalReport]);

  const handleGenerateReportClick = async () => {
    if (!assessment) return;
    await startReportGeneration(assessment.id);
  };

  if (showRecommendations && assessment) {
    if (!finalReport) {
      return (
        <div className="min-h-screen bg-slate-50 px-4 py-8">
          <div className="mx-auto w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-600">
              {language === "fr"
                ? "Le rapport final n'est pas encore disponible. Veuillez retourner au chat et réessayer."
                : "Final report is not available yet. Please return to chat and try again."}
            </p>
            <button
              type="button"
              onClick={() => setShowRecommendations(false)}
              className="mt-4 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              {language === "fr" ? "Retour au chat" : "Back to chat"}
            </button>
          </div>
        </div>
      );
    }
    return (
      <AssessmentReport
        report={finalReport}
        companyName={companyName}
        language={language}
        onBack={() => {
          // Return to the assessments list, not the underlying chat.
          setShowRecommendations(false);
          rememberActiveAssessment(null);
          setAssessment(null);
          setView("history");
        }}
      />
    );
  }

  // Opening a completed report: show a loading screen (never the chat) until it's ready.
  if (openingReport) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#ffffff,#f8fafc)]">
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="h-9 w-9 animate-spin text-violet-500" />
          <p className="text-sm font-semibold text-slate-600">
            {language === "fr" ? "Chargement du rapport…" : "Loading report…"}
          </p>
        </div>
      </div>
    );
  }

  if (showGeneratingPage) {
    return (
      <AssessmentGeneratingPage
        language={language}
        onDone={() => {
          setIsGeneratingMinDelayDone(true);
        }}
      />
    );
  }

  if (view === "history" && !assessment) {
    return (
      <div className="min-h-screen bg-[linear-gradient(180deg,#ffffff,#f8fafc)]">
        <ModuleHeader
          title={language === "fr" ? "Évaluation de maturité" : "Maturity Assessment"}
          subtitle={language === "fr" ? "Diagnostic CX guidé" : "Guided CX diagnostic"}
          onBack={onBack ?? (() => window.history.back())}
          isFrench={language === "fr"}
        />
        {topSlot}
        <div className="mx-auto w-full max-w-7xl px-4 py-8">
          <div className="mb-6 hidden items-center justify-between">
            <button
              onClick={onBack}
              className="btn-secondary"
            >
              ← {language === "fr" ? "Retour" : "Back"}
            </button>
            <div className="flex items-center gap-3">
              <div className="inline-flex items-center gap-2 rounded-full bg-violet-50 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-violet-700">
                <Sparkles className="h-3.5 w-3.5" />
                {language === "fr" ? "Évaluation EY" : "EY Assessment"}
              </div>
              <StudioNav isFrench={language === "fr"} />
            </div>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {language === "fr" ? "Évaluations de maturité" : "Maturity assessments"}
            </h1>
            <p className="mb-6 mt-1 text-sm text-slate-500">
              {language === "fr"
                ? "Vos conversations : reprenez-les, consultez les rapports, ou lancez-en une nouvelle."
                : "Your conversations — resume them, view reports, or start a new one."}
            </p>
            <AssessmentHistoryTable
              assessments={assessmentsList}
              onOpen={loadAssessment}
              onNew={() => {
                // Full reset so we always land on the company-profile form (with the
                // Fill-now / Send-to-client toggle), never fall through to a stale chat.
                clearChat();
                resetNewForm();
                setView("new");
              }}
              onDelete={handleDeleteAssessment}
              isFrench={language === "fr"}
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
                    {language === "fr" ? "Supprimer l'évaluation ?" : "Delete assessment?"}
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    {language === "fr"
                      ? `L'évaluation de « ${pendingDelete.company_name} » sera définitivement supprimée. Cette action est irréversible.`
                      : `The assessment for "${pendingDelete.company_name}" will be permanently deleted. This cannot be undone.`}
                  </p>
                </div>
              </div>
              {deleteError && (
                <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{deleteError}</div>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={cancelDeleteAssessment}
                  disabled={deleteBusy}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  {language === "fr" ? "Annuler" : "Cancel"}
                </button>
                <button
                  type="button"
                  onClick={() => void confirmDeleteAssessment()}
                  disabled={deleteBusy}
                  className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-rose-700 disabled:opacity-60"
                >
                  {deleteBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  {language === "fr" ? "Supprimer" : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (!assessment && stage === "await_company_name") {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(139,92,246,0.14),transparent_42%),linear-gradient(180deg,#ffffff,#f8fafc)] px-4 py-8">
        <div className="mx-auto mb-4 w-full max-w-6xl">
          <button
            onClick={() => {
              resetNewForm();
              setView("history");
            }}
            className="btn-secondary"
          >
            ← {language === "fr" ? "Retour aux évaluations" : "Back to assessments"}
          </button>
        </div>
        <div className="mx-auto grid min-h-[calc(100vh-8rem)] w-full max-w-6xl items-center gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="rounded-3xl border border-violet-100 bg-white/85 p-7 shadow-xl backdrop-blur"
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-violet-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-violet-700">
              <Sparkles className="h-4 w-4" />
              {language === "fr" ? "Nouvelle évaluation" : "New assessment"}
            </div>
            <h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
              {language === "fr" ? "Lancez une évaluation de maturité." : "Start a maturity assessment."}
            </h1>
            <p className="mt-5 text-base leading-7 text-slate-600">
              {language === "fr"
                ? "Définissez le contexte de l'entreprise, puis menez l'entretien vous-même ou envoyez un lien privé à votre client."
                : "Set the company context, then run the guided interview yourself or send a private link to your client."}
            </p>
            <div className="mt-7 grid gap-3 text-sm text-slate-700">
              <div className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <Building2 className="mt-0.5 h-5 w-5 text-violet-600" />
                <span>
                  {language === "fr"
                    ? "« Remplir maintenant » : vous menez l'entretien guidé. « Envoyer au client » : il le complète via un lien privé, et les résultats arrivent sur votre tableau de bord."
                    : "“Fill in now” runs the guided interview yourself. “Send to client” lets them complete it via a private link, with results landing on your dashboard."}
                </span>
              </div>
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.06 }}
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl sm:p-8"
          >
            <div className="mb-6">
              <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">
                {language === "fr" ? "Profil de l'entreprise" : "Company profile"}
              </p>
              <h2 className="mt-2 text-2xl font-bold text-slate-950">
                {language === "fr" ? "Définir le contexte" : "Set the assessment context"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {newMode === "send"
                  ? language === "fr"
                    ? "Renseignez le contexte de l'entreprise, puis générez un lien à envoyer au client."
                    : "Fill in the company context, then generate a link to send to the client."
                  : language === "fr"
                    ? "Veuillez remplir les champs ci-dessous. L'évaluation commencera immédiatement après validation."
                    : "Please complete the fields below. The assessment will start immediately after submission."}
              </p>
            </div>

            {/* Fill-now vs send-to-client toggle */}
            <div className="mb-6 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => {
                  setNewMode("fill");
                  setGeneratedLink(null);
                  setProfileError(null);
                }}
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                  newMode === "fill" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {language === "fr" ? "Remplir maintenant" : "Fill in now"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setNewMode("send");
                  setGeneratedLink(null);
                  setProfileError(null);
                }}
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                  newMode === "send" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {language === "fr" ? "Envoyer au client" : "Send to client"}
              </button>
            </div>

            <form className="space-y-5" onSubmit={handleProfileSubmit}>
              <div className="space-y-2">
                <label htmlFor="companyName" className="text-sm font-semibold text-slate-800">
                  {language === "fr" ? "Nom de l'entreprise" : "Company name"}
                </label>
                <input
                  id="companyName"
                  value={companyProfile.companyName}
                  onChange={(event) => updateCompanyProfile("companyName", event.target.value)}
                  placeholder={language === "fr" ? "Exemple : Four Seasons" : "Example: Four Seasons"}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                />
              </div>

              {/* Sector / size / region: only when the consultant fills it in themselves.
                  When sending to a client, these are the client's to know, so we omit them. */}
              {newMode === "fill" && (
              <>
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="sector" className="text-sm font-semibold text-slate-800">
                    {language === "fr" ? "Secteur d'activité" : "Sector"}
                  </label>
                  <select
                    id="sector"
                    value={companyProfile.sector}
                    onChange={(event) => updateCompanyProfile("sector", event.target.value)}
                    disabled={isReferenceLoading}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 disabled:bg-slate-50"
                  >
                    <option value="">
                      {isReferenceLoading
                        ? (language === "fr" ? "Chargement des secteurs..." : "Loading sectors...")
                        : (language === "fr" ? "Sélectionner un secteur" : "Select sector")}
                    </option>
                    {sectorOptions.map((option) => (
                      <option key={option.code} value={option.code}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label htmlFor="companySize" className="text-sm font-semibold text-slate-800">
                    {language === "fr" ? "Taille de l'entreprise" : "Company size"}
                  </label>
                  <select
                    id="companySize"
                    value={companyProfile.companySize}
                    onChange={(event) => updateCompanyProfile("companySize", event.target.value)}
                    disabled={isReferenceLoading}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 disabled:bg-slate-50"
                  >
                    <option value="">
                      {isReferenceLoading
                        ? (language === "fr" ? "Chargement des tailles..." : "Loading sizes...")
                        : (language === "fr" ? "Sélectionner la taille" : "Select size")}
                    </option>
                    {sizeOptions.map((option) => (
                      <option key={option.code} value={option.code}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="region" className="text-sm font-semibold text-slate-800">
                  {language === "fr" ? "Région" : "Region"}
                </label>
                <select
                  id="region"
                  value={companyProfile.region}
                  onChange={(event) => updateCompanyProfile("region", event.target.value)}
                  disabled={isReferenceLoading}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                >
                  <option value="">
                    {isReferenceLoading
                      ? (language === "fr" ? "Chargement des régions..." : "Loading regions...")
                      : (language === "fr" ? "Sélectionner la région" : "Select region")}
                  </option>
                  {regionOptions.map((region) => (
                    <option key={region.code} value={region.code}>
                      {region.label}
                    </option>
                  ))}
                </select>
              </div>
              </>
              )}

              {/* When sending, sector & size are inferred from the company name — no consultant input. */}
              {newMode === "send" && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
                  {language === "fr"
                    ? "Le secteur et la taille sont détectés automatiquement à partir du nom de l'entreprise ; vous n'avez pas à les renseigner ici."
                    : "Sector and company size are detected automatically from the company name, so you don't need to set them here."}
                </div>
              )}

              {/* Recipient details — only when sending the assessment to a client */}
              {newMode === "send" && (
                <div className="space-y-5 rounded-2xl border border-violet-100 bg-violet-50/40 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-violet-700">
                    {language === "fr" ? "Destinataire du lien" : "Link recipient"}
                  </p>
                  <div className="grid gap-5 md:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="clientName" className="text-sm font-semibold text-slate-800">
                        {language === "fr" ? "Nom de la personne" : "Person's name"}
                      </label>
                      <input
                        id="clientName"
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                        placeholder={language === "fr" ? "Ex : Amine Ben Salah" : "e.g. Amine Ben Salah"}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="clientRole" className="text-sm font-semibold text-slate-800">
                        {language === "fr" ? "Poste (facultatif)" : "Role (optional)"}
                      </label>
                      <input
                        id="clientRole"
                        value={clientRole}
                        onChange={(e) => setClientRole(e.target.value)}
                        placeholder={language === "fr" ? "Ex : Directeur Expérience Client" : "e.g. Head of Customer Experience"}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="clientEmail" className="text-sm font-semibold text-slate-800">
                      {language === "fr" ? "Email (facultatif — pour l'envoyer directement)" : "Email (optional — to send it directly)"}
                    </label>
                    <input
                      id="clientEmail"
                      type="email"
                      value={clientEmail}
                      onChange={(e) => setClientEmail(e.target.value)}
                      placeholder={language === "fr" ? "personne@entreprise.com" : "person@company.com"}
                      className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                    />
                  </div>
                </div>
              )}

              {/* Generated link result */}
              {newMode === "send" && generatedLink && (
                <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                  <div className="flex items-center gap-2 text-sm font-bold text-emerald-800">
                    <CheckCircle2 className="h-4 w-4" />
                    {language === "fr" ? "Lien prêt à envoyer" : "Link ready to share"}
                  </div>
                  <p className="text-xs text-emerald-700">
                    {clientEmail.trim()
                      ? language === "fr"
                        ? "Le lien a aussi été envoyé par email (si la messagerie est configurée). Vous pouvez le copier ci-dessous."
                        : "The link was also emailed (if email is configured). You can copy it below."
                      : language === "fr"
                        ? "Copiez ce lien et envoyez-le à votre client. Aucun compte n'est requis pour le remplir."
                        : "Copy this link and send it to your client. No account is needed to fill it in."}
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      readOnly
                      value={generatedLink}
                      onFocus={(e) => e.currentTarget.select()}
                      className="flex-1 truncate rounded-xl border border-emerald-200 bg-white px-3 py-2.5 text-xs text-slate-700 outline-none"
                    />
                    <button
                      type="button"
                      onClick={copyLink}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2.5 text-xs font-bold text-white transition hover:bg-emerald-700"
                    >
                      {linkCopied
                        ? (language === "fr" ? "Copié !" : "Copied!")
                        : (language === "fr" ? "Copier" : "Copy")}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      resetNewForm();
                      setView("history");
                    }}
                    className="text-xs font-semibold text-emerald-700 underline-offset-2 hover:underline"
                  >
                    {language === "fr" ? "← Retour aux évaluations" : "← Back to assessments"}
                  </button>
                </div>
              )}

              {profileError ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
                  {profileError}
                </div>
              ) : null}

              {!(newMode === "send" && generatedLink) && (
                <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
                  {onBack ? (
                    <button
                      type="button"
                      onClick={onBack}
                      className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      {language === "fr" ? "Retour" : "Back"}
                    </button>
                  ) : <span />}
                  <button
                    type="submit"
                    disabled={isTyping || (newMode === "fill" && isReferenceLoading)}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-6 py-3 text-sm font-bold text-white shadow-lg transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {newMode === "send"
                      ? isTyping
                        ? (language === "fr" ? "Génération du lien..." : "Generating link...")
                        : (language === "fr" ? "Générer le lien" : "Generate link")
                      : isTyping
                        ? (language === "fr" ? "Démarrage de l'évaluation..." : "Starting assessment...")
                        : (language === "fr" ? "Démarrer l'évaluation" : "Start assessment")}
                    {isTyping ? <Loader2 className="h-4 w-4 animate-spin" /> : newMode === "send" ? <Send className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                  </button>
                </div>
              )}
            </form>
          </motion.section>
        </div>
      </div>
    );
  }

  const lastAssistantMsgIndex = messages.map((m) => m.isUser).lastIndexOf(false);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(139,92,246,0.12),transparent_45%),linear-gradient(180deg,#ffffff,#f8fafc)] px-3 py-3 sm:px-4 sm:py-4">
      <div className="mx-auto w-full max-w-[1400px]">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex h-[calc(100vh-1.5rem)] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl sm:h-[calc(100vh-2rem)]"
        >
          <div className="hidden w-72 border-r border-slate-100 bg-slate-50/70 p-5 lg:block">
            <div className="mb-6 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-500" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  {language === "fr" ? "Parcours d'évaluation" : "Assessment Journey"}
                </h2>
                <p className="text-xs text-slate-500">
                  {language === "fr" ? "Entretien guidé" : "Guided interview"}
                </p>
              </div>
            </div>
            {assessment ? (
              <div className="space-y-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {language === "fr" ? "Progression" : "Progress"}
                </p>
                <div className="h-2 w-full rounded-full bg-slate-200">
                  <div className={`h-2 rounded-full transition-all duration-500 ${progressStats.barClass}`} style={{ width: `${progressStats.percent}%` }} />
                </div>
                <div className="space-y-3">
                  {AXIS_ORDER.map((axis) => {
                    const completed = Boolean(axisDone.get(axis));
                    const current = normalizeAxis(assessment.axis) === axis;
                    const markerClass = completed ? "text-emerald-500" : current ? "text-violet-500" : "text-slate-300";
                    const textClass = completed ? "text-emerald-700" : current ? "text-violet-700" : "text-slate-500";
                    return (
                      <div key={axis} className="flex items-start gap-3">
                        <div className="mt-0.5 shrink-0">
                          {completed ? (
                            <CheckCircle2 className={`h-4 w-4 ${markerClass}`} />
                          ) : (
                            <Circle className={`h-4 w-4 ${markerClass}`} />
                          )}
                        </div>
                        <div className="flex flex-col">
                          <span className={`text-xs font-bold uppercase tracking-wider ${textClass}`}>{getAxisDisplayName(axis, language)}</span>
                          <span className="text-[11px] text-slate-500 font-normal mt-0.5 leading-normal">
                            {getAxisProgressSubtitle(axis, language)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-slate-500">
                  {language === "fr"
                    ? "Restez concentré sur des exemples concrets. Nous nous occupons de l'analyse."
                    : "Stay focused on practical examples. We handle the analysis."}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                {language === "fr"
                  ? "Nous allons dresser le profil de votre entreprise puis lancer un entretien de maturité intelligent."
                  : "We will profile your company context then run a smart maturity interview."}
              </p>
            )}
          </div>

          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4 sm:px-5">
              <div className="flex items-center gap-2">
              {onBack ? (
                <button
                  type="button"
                  onClick={onBack}
                  className="rounded-md p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                  aria-label="Back to landing"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
              ) : null}
              <Sparkles className="h-5 w-5 text-violet-500" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  {language === "fr" ? "Assistant EY" : "EY Assistant"}
                </h2>
                <p className="text-xs text-slate-500">
                  {assessment
                    ? (language === "fr" ? `Évaluation #${assessment.id} - ${assessment.status}` : `Assessment #${assessment.id} - ${assessment.status}`)
                    : (language === "fr" ? "Profilage en cours" : "Profiling in chat")}
                </p>
              </div>
              </div>
              <button
                onClick={clearChat}
                className="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Clear chat"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {assessment ? (
              <div className="border-b border-slate-100 px-4 py-3 sm:px-5 lg:hidden">
                <div className="mb-2 h-2 w-full rounded-full bg-slate-100">
                  <div className={`h-2 rounded-full transition-all duration-500 ${progressStats.barClass}`} style={{ width: `${progressStats.percent}%` }} />
                </div>
                <div className="flex items-center gap-2">
                  {AXIS_ORDER.map((axis) => {
                    const completed = Boolean(axisDone.get(axis));
                    const current = normalizeAxis(assessment.axis) === axis;
                    const cls = completed ? "text-emerald-500" : current ? "text-violet-500" : "text-slate-300";
                    return completed ? (
                      <CheckCircle2 key={axis} className={`h-4 w-4 ${cls}`} />
                    ) : (
                      <Circle key={axis} className={`h-4 w-4 ${cls}`} />
                    );
                  })}
                </div>
              </div>
            ) : null}

            {stage !== "completed" ? (
              <>
                <div ref={scrollRef} className="flex-1 overflow-y-auto bg-white px-4 py-4 sm:px-5">
                  <div className="space-y-4 pb-[50vh]">
                    {messages.map((msg, idx) => {
                      const isLatestAssistant = !msg.isUser && idx === lastAssistantMsgIndex;
                      return (
                      <div 
                        key={msg.id} 
                        ref={isLatestAssistant ? activeQuestionRef : null}
                        className={`flex ${msg.isUser ? "justify-end" : "justify-start"} scroll-mt-6`}
                      >
                        {!msg.isUser ? (
                          <div className="mr-2 mt-1 shrink-0">
                            <Avatar chatbot size={30} alt="EY Assistant avatar" />
                          </div>
                        ) : null}

                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          className={`max-w-[95%] rounded-2xl px-5 py-4 text-[17px] leading-relaxed sm:max-w-[90%] shadow-sm ${
                            msg.isUser
                              ? "rounded-tr-none bg-slate-900 text-white font-normal"
                              : "rounded-tl-none border border-slate-200 bg-slate-50 text-slate-800 font-normal"
                          }`}
                        >
                          {msg.isUser ? msg.text : <AssistantMessageText text={msg.text} />}
                        </motion.div>
                      </div>
                      );
                    })}

                    {isTyping ? (
                      <div className="flex justify-start">
                        <div className="mr-2 mt-1 shrink-0">
                          <Avatar chatbot size={30} alt="EY Assistant avatar" />
                        </div>
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="max-w-[88%] rounded-2xl rounded-tl-none border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 sm:max-w-[78%]"
                        >
                          <div className="flex items-center gap-2 text-slate-600">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>{language === "fr" ? "L'assistant réfléchit..." : "Assistant is thinking..."}</span>
                          </div>
                        </motion.div>
                      </div>
                    ) : null}
                    <div ref={endRef} />
                  </div>
                </div>

                <div className="border-t border-slate-100 bg-white p-4 sm:p-5">
                  <form
                    onSubmit={handleSubmit}
                    className={`relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-200 ${
                      isFocused
                        ? "border-violet-400 bg-white shadow-md shadow-violet-100 ring-4 ring-violet-50"
                        : "border-slate-200 bg-white shadow-sm hover:border-slate-300"
                    }`}
                  >
                    {stage === "assessment_active" && !isTyping && questionOptions.length > 0 ? (
                      <div className="border-b border-slate-100 bg-slate-50/50">
                        <MultiChoiceOptions
                          options={questionOptions}
                          disabled={isTyping}
                          onSelect={async (text) => {
                            setQuestionOptions([]);
                            appendUser(text);
                            await handleAssessmentMessage(text);
                          }}
                        />
                      </div>
                    ) : null}

                    <div className="relative flex items-center bg-white min-h-[64px] transition-colors duration-150 hover:bg-violet-50/30">
                      {stage === "assessment_active" && !isTyping && questionOptions.length > 0 ? (
                        <div className="pl-6 pr-4">
                          <span
                            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[13px] font-bold transition-all duration-150 ${
                              isFocused
                                ? "bg-violet-500 text-white shadow-md shadow-violet-200"
                                : "bg-violet-50 text-violet-500"
                            }`}
                          >
                            {questionOptions.length + 1}
                          </span>
                        </div>
                      ) : null}
                      <input
                        value={input}
                        onChange={(event) => setInput(event.target.value)}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={
                          stage === "await_company_name"
                            ? (language === "fr" ? "Saisissez le nom de votre entreprise..." : "Type your company name...")
                            : stage === "await_sector_choice"
                              ? (language === "fr" ? "Saisissez le numéro ou le nom du secteur..." : "Type sector number or name...")
                              : stage === "await_size_choice"
                                ? (language === "fr" ? "Saisissez le numéro ou le nom de la taille..." : "Type size number or name...")
                                : (language === "fr" ? "Saisissez votre réponse ou choisissez une option..." : "Type your own answer or pick an option above...")
                        }
                        className={`w-full bg-transparent py-4 pr-14 text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none ${
                          stage === "assessment_active" && !isTyping && questionOptions.length > 0 ? "pl-0" : "pl-5"
                        }`}
                      />
                      <button
                        type="submit"
                        disabled={!input.trim() || isTyping}
                        className={`absolute right-2 rounded-xl p-2 transition-all duration-200 ${
                          input.trim() && !isTyping
                            ? "bg-violet-600 text-white shadow-sm hover:bg-violet-700 hover:shadow"
                            : "cursor-not-allowed bg-slate-100 text-slate-400"
                        }`}
                        aria-label="Send"
                      >
                        <Send className="h-4 w-4" />
                      </button>
                    </div>
                  </form>
                  <div className="mt-2.5 px-1">
                    <p className="text-[13px] font-medium text-slate-400">
                      {language === "fr"
                        ? "Appuyez sur Entrée pour envoyer ou choisissez une option ci-dessus."
                        : "Press Enter to send or pick an option above."}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-1 items-center justify-center p-6">
                <div className="w-full max-w-2xl rounded-3xl border border-violet-200/70 bg-gradient-to-br from-violet-50 to-indigo-50 p-7 text-center shadow-sm">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-violet-600 shadow-sm">
                    <FileText className="h-7 w-7" />
                  </div>
                  <p className="text-base font-semibold text-slate-900">
                    {language === "fr"
                      ? "Merci — nous avons maintenant assez d'éléments pour concevoir votre rapport de maturité de l'expérience client."
                      : "Thank you — we now have enough evidence to build your customer experience maturity report."}
                  </p>
                  <p className="mt-2 text-sm text-slate-600">
                    {language === "fr"
                      ? "Votre rapport comprendra vos points forts, vos axes d'amélioration, la maturité par axe et des recommandations ciblées."
                      : "Your report will include strengths, pain points, maturity by axis, and targeted recommendations."}
                  </p>
                </div>
              </div>
            )}
            {stage === "completed" ? (
              <div className="border-t border-violet-100 bg-gradient-to-r from-violet-50 to-indigo-50 px-4 py-5 sm:px-5">
                <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                  <button
                    type="button"
                    onClick={onBack}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    {language === "fr" ? "Retour au chat" : "Back to chat"}
                  </button>
                  <button
                    type="button"
                    onClick={handleGenerateReportClick}
                    disabled={isReportFetching}
                    className="group inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isReportFetching
                      ? (language === "fr" ? "Préparation du rapport..." : "Preparing report...")
                      : (language === "fr" ? "Obtenir le rapport" : "Get report")}
                    {!isReportFetching ? <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" /> : null}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </motion.div>
      </div>
    </div>
  );
}


