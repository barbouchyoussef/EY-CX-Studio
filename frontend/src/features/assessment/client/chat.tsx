import { useEffect, useRef, useState, useMemo, type FormEvent } from "react";
import { assessmentCopy } from "../copy";
import { motion } from "framer-motion";
import { Sparkles, CheckCircle2, Circle, Loader2, Send, AlertTriangle, Building2 } from "lucide-react";
import { Avatar } from "../../../components/ui/avatar-1";
import MultiChoiceOptions from "../../../components/ui/multi-choice-input";
import AssessmentReport from "../report/AssessmentReport";
import type { FinalReport } from "../../../types/final-report";
import {
  getRespondentContext,
  getRespondentNextQuestion,
  submitRespondentAnswer,
  getRespondentFinalReport,
  getReferenceOptions,
  setRespondentProfile,
  type NextQuestion,
  type AxisProgress,
  type RefOption,
} from "../../../lib/respondentApi";

type Msg = { id: number; role: "assistant" | "user"; text: string };
type Phase = "loading" | "profile" | "asking" | "submitting" | "finishing" | "report" | "done" | "invalid";

let _id = 0;
const nid = () => ++_id;

/* ---- shared assessment presentation helpers (mirrors the consultant chat) ---- */

const AXIS_ORDER = ["MANAGE", "ANALYZE", "IMPROVE"];
const normalizeAxis = (v: string | null | undefined) => (v ?? "").trim().toUpperCase();

const getInitialGreeting = (lang: string) =>
  lang === "fr"
    ? "Bonjour, je suis l'assistant EY. Si vous êtes ici, cela signifie que votre organisation est prête à porter un regard honnête sur l'expérience qu'elle propose. C'est là que j'interviens."
    : "Hello, I’m the EY assistant. If you’re here, it means your organization is ready to take an honest look at the experience it delivers. That’s where I come in.";

const getStartIntro = (lang: string) =>
  lang === "fr" ? "Commençons l'évaluation." : "Let's begin the assessment.";

const getAxisDisplayName = (axis: string, lang: string) => {
  if (axis === "MANAGE") return lang === "fr" ? "GÉRER" : "MANAGE";
  if (axis === "ANALYZE") return lang === "fr" ? "ANALYSER" : "ANALYZE";
  if (axis === "IMPROVE") return lang === "fr" ? "AMÉLIORER" : "IMPROVE";
  return axis;
};

const getAxisSubtitle = (axis: string, lang: string) => {
  if (axis === "MANAGE")
    return lang === "fr" ? "Comment votre organisation s'approprie l'expérience" : "How your organization owns the experience";
  if (axis === "ANALYZE")
    return lang === "fr" ? "Comment vous transformez les signaux clients en décisions" : "How you turn customer signals into decisions";
  if (axis === "IMPROVE")
    return lang === "fr" ? "Comment vous agissez, vous adaptez et avancez" : "How you act, adapt, and move forward";
  return "";
};

const splitQuestion = (text: string) => {
  const t = text.trimEnd();
  const qEnd = t.lastIndexOf("?");
  if (qEnd < 0) return { prefix: text, question: "", suffix: "" };
  let qStart = 0;
  for (let i = qEnd - 1; i >= 0; i -= 1) {
    if ([".", "?", "!", "\n"].includes(t[i])) {
      qStart = i + 1;
      break;
    }
  }
  while (qStart < t.length && /\s/.test(t[qStart])) qStart += 1;
  return { prefix: text.slice(0, qStart), question: text.slice(qStart, qEnd + 1), suffix: text.slice(qEnd + 1) };
};

const AssistantText = ({ text }: { text: string }) => {
  const { prefix, question, suffix } = splitQuestion(text);
  if (!question) return <span className="whitespace-pre-wrap">{text}</span>;
  return (
    <span className="whitespace-pre-wrap">
      {prefix}
      <strong className="font-bold text-slate-950">{question}</strong>
      {suffix}
    </span>
  );
};

/**
 * The client's assessment conversation — the same look as the consultant's chat (axes-progress
 * sidebar, boxed multi-choice options, avatar bubbles, greeting intro), but driven entirely by the
 * passwordless link token through the /respondent endpoints.
 */
export default function ClientAssessmentChat({ token, language = "en" }: { token: string; language?: string }) {
  const isFr = language === "fr";
  const copy = assessmentCopy(isFr);
  const [phase, setPhase] = useState<Phase>("loading");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [options, setOptions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  // Live progress, refreshed from /context so the sidebar tracks the same axes as the consultant.
  const [progress, setProgress] = useState<AxisProgress[]>([]);
  const [currentAxis, setCurrentAxis] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("active");
  const [submitted, setSubmitted] = useState(0);
  const [report, setReport] = useState<FinalReport | null>(null);
  const [companyName, setCompanyName] = useState<string>("");
  // Client-filled company profile (the "hello" step) before the questions begin.
  const [refSectors, setRefSectors] = useState<RefOption[]>([]);
  const [refSizes, setRefSizes] = useState<RefOption[]>([]);
  const [selSector, setSelSector] = useState("");
  const [selSize, setSelSize] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);      // the chat scroll container
  const activeQuestionRef = useRef<HTMLDivElement>(null); // the newest assistant message
  const lastScrolledQuestion = useRef<number>(-1);     // index of the question we last scrolled to

  const say = (role: Msg["role"], text: string) => setMessages((m) => [...m, { id: nid(), role, text }]);

  useEffect(() => {
    // The newest assistant message is the current question.
    const lastQuestionIdx = messages.map((m) => m.role === "user").lastIndexOf(false);
    const container = scrollRef.current;
    if (
      phase === "asking" &&
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
    } else if (phase !== "asking") {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    // `busy` is deliberately not a dependency: it is declared below this effect, and the
    // lastScrolledQuestion guard already prevents a repeat scroll while the assistant types.
  }, [messages, phase]);

  const stats = useMemo(() => {
    const rows = progress ?? [];
    const cov = rows.reduce((s, r) => s + Math.max(0, r.covered ?? 0), 0);
    const tot = rows.reduce((s, r) => s + Math.max(0, r.total ?? 0), 0);
    const realPct = tot > 0 ? Math.round((cov / tot) * 100) : 0;
    const target = Math.max(tot + 6, 12);
    const turnPct = Math.round((submitted / target) * 100);
    const percent = status === "completed" ? 100 : Math.min(95, Math.max(realPct, Math.max(0, turnPct)));
    const cur = normalizeAxis(currentAxis);
    const barClass =
      cur === "MANAGE" ? "bg-blue-500" : cur === "ANALYZE" ? "bg-amber-500" : cur === "IMPROVE" ? "bg-emerald-500" : "bg-violet-500";
    const curIdx = Math.max(0, AXIS_ORDER.indexOf(cur || AXIS_ORDER[0]));
    return { percent, barClass, curIdx };
  }, [progress, currentAxis, status, submitted]);

  const isDone = (axis: string) => status === "completed" || AXIS_ORDER.indexOf(axis) < stats.curIdx;

  const refreshProgress = async () => {
    try {
      const ctx = await getRespondentContext(token);
      if (ctx.assessment) {
        setProgress(ctx.assessment.progress ?? []);
        setCurrentAxis(ctx.assessment.current_axis ?? null);
        if (ctx.assessment.status) setStatus(ctx.assessment.status);
      }
    } catch {
      /* progress is best-effort; the conversation still works without it */
    }
  };

  // Validate the link, seed the sidebar, then either collect the company profile (fresh assessment)
  // or resume straight into the questions (client already started answering).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ctx = await getRespondentContext(token);
        if (cancelled) return;
        let answered = 0;
        if (ctx.assessment) {
          setProgress(ctx.assessment.progress ?? []);
          setCurrentAxis(ctx.assessment.current_axis ?? null);
          if (ctx.assessment.status) setStatus(ctx.assessment.status);
          if (ctx.assessment.company?.name) setCompanyName(ctx.assessment.company.name);
          answered = (ctx.assessment.progress ?? []).reduce((s, r) => s + Math.max(0, r.covered ?? 0), 0);
        }
        // Fresh assessment → let the client fill their own sector + size first.
        if (answered === 0 && ctx.assessment?.status !== "completed") {
          const opts = await getReferenceOptions();
          if (cancelled) return;
          setRefSectors(opts.sectors);
          setRefSizes(opts.sizes);
          setPhase("profile");
          return;
        }
        await beginQuestions();
      } catch {
        if (!cancelled) setPhase("invalid");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Ask the first (or next) question, opening with the greeting intro.
  const beginQuestions = async () => {
    const q = await getRespondentNextQuestion(token);
    if (q.status === "completed") {
      await finish();
      return;
    }
    const first = `${getInitialGreeting(language)}\n\n${getStartIntro(language)} ${q.question || q.message || ""}`.trim();
    say("assistant", first);
    setOptions(q.options ?? []);
    setPhase("asking");
  };

  const submitProfile = async () => {
    if (!selSector || !selSize) {
      setProfileError(copy.chooseSectorAndSize);
      return;
    }
    setProfileBusy(true);
    setProfileError(null);
    try {
      await setRespondentProfile(token, selSector, selSize, companyName.trim() || undefined);
      await beginQuestions();
    } catch {
      setProfileError(copy.somethingWentWrong);
      setPhase("profile");
    } finally {
      setProfileBusy(false);
    }
  };

  const showQuestion = (q: NextQuestion) => {
    say("assistant", q.question || q.message || (copy.nextQuestion));
    setOptions(q.options ?? []);
    setPhase("asking");
  };

  const finish = async () => {
    setPhase("finishing"); // "generating your report" state while the backend builds it
    setOptions([]);
    setStatus("completed");
    try {
      const rep = await getRespondentFinalReport(token); // generates + marks completed server-side
      if (rep) {
        setReport(rep);
        setPhase("report");
        return;
      }
    } catch {
      /* answers are saved; fall back to a thank-you if the report can't be built */
    }
    setPhase("done");
  };

  const send = async (raw: string) => {
    const answer = raw.trim();
    if (!answer || phase !== "asking") return;
    say("user", answer);
    setInput("");
    setOptions([]);
    setSubmitted((n) => n + 1);
    setPhase("submitting");
    try {
      await submitRespondentAnswer(token, answer);
      await refreshProgress();
      const q = await getRespondentNextQuestion(token);
      if (q.status === "completed") await finish();
      else showQuestion(q);
    } catch {
      say("assistant", copy.sorrySomethingWentWrong);
      setPhase("asking");
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };

  // ── Invalid link ─────────────────────────────────────────────────────────
  if (phase === "invalid") {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center px-4 text-center">
        <AlertTriangle className="h-10 w-10 text-amber-500" />
        <h2 className="mt-4 text-lg font-bold text-slate-900">
          {copy.linkExpiredTitle}
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          {copy.linkExpiredLead}
        </p>
      </div>
    );
  }

  // ── Company profile ("hello" step) — the client fills their own name, sector + size ──
  if (phase === "profile") {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:py-14">
        <div className="grid items-start gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          {/* Left: the assistant introduces itself (this is the client's page, so it belongs here) */}
          <section className="rounded-3xl border border-violet-100 bg-white/85 p-7 shadow-xl backdrop-blur sm:p-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-violet-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-violet-700">
              <Sparkles className="h-4 w-4" />
              {copy.assistantName}
            </div>
            <h1 className="mt-5 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
              {copy.clientGreeting}
            </h1>
            <p className="mt-5 whitespace-pre-line text-base leading-7 text-slate-600">
              {copy.clientGreetingBody}
            </p>
            <div className="mt-7 flex gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-700">
              <Building2 className="mt-0.5 h-5 w-5 shrink-0 text-violet-600" />
              <span>
                {copy.profileWhy}
              </span>
            </div>
          </section>

          {/* Right: the editable profile form */}
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl sm:p-8">
            <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">{copy.profileTitle}</p>
            <h2 className="mt-2 text-2xl font-bold text-slate-950">{copy.profileHeading}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {copy.profileLead}
            </p>

            <div className="mt-6 space-y-5">
              <div className="space-y-2">
                <label htmlFor="clientCompany" className="text-sm font-semibold text-slate-800">{copy.companyNameLabel}</label>
                <input
                  id="clientCompany"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder={copy.companyNamePlaceholder}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-800">{copy.sectorLabel}</label>
                <select
                  value={selSector}
                  onChange={(e) => setSelSector(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                >
                  <option value="">{copy.sectorPlaceholder}</option>
                  {refSectors.map((o) => (
                    <option key={o.code} value={o.code}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-800">{copy.sizeLabel}</label>
                <select
                  value={selSize}
                  onChange={(e) => setSelSize(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
                >
                  <option value="">{copy.sizePlaceholder}</option>
                  {refSizes.map((o) => (
                    <option key={o.code} value={o.code}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {profileError && (
              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{profileError}</div>
            )}

            <button
              type="button"
              onClick={() => void submitProfile()}
              disabled={profileBusy}
              className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-3.5 text-sm font-bold text-white transition hover:bg-violet-700 disabled:opacity-60"
            >
              {profileBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {copy.startAssessment}
            </button>
          </section>
        </div>
      </div>
    );
  }

  // ── Full report (same one the consultant sees), minus consultant-only chrome ──
  // Rendered as a fixed overlay so it covers the client page header (no navbar in the report).
  if (phase === "report" && report) {
    return (
      <div className="fixed inset-0 z-50 overflow-y-auto bg-white">
        <AssessmentReport
          report={report}
          companyName={companyName}
          language={language}
          clientView
          onBack={() => {}}
        />
      </div>
    );
  }

  // ── Generating the report ─────────────────────────────────────────────────
  if (phase === "finishing") {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center px-4 text-center">
        <Loader2 className="h-9 w-9 animate-spin text-violet-500" />
        <h2 className="mt-5 text-lg font-bold text-slate-900">
          {copy.generatingReport}
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          {copy.generatingLead}
        </p>
      </div>
    );
  }

  const busy = phase === "submitting" || phase === "loading";

  return (
    <div className="px-3 py-3 sm:px-4 sm:py-4">
      <div className="mx-auto w-full max-w-[1200px]">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex h-[calc(100vh-6rem)] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl"
        >
          {/* ── Axes progress sidebar ── */}
          <div className="hidden w-72 border-r border-slate-100 bg-slate-50/70 p-5 lg:block">
            <div className="mb-6 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-500" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  {copy.journeyTitle}
                </h2>
                <p className="text-xs text-slate-500">{copy.guidedInterview}</p>
              </div>
            </div>
            <div className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                {copy.progressLabel}
              </p>
              <div className="h-2 w-full rounded-full bg-slate-200">
                <div className={`h-2 rounded-full transition-all duration-500 ${stats.barClass}`} style={{ width: `${stats.percent}%` }} />
              </div>
              <div className="space-y-3">
                {AXIS_ORDER.map((axis) => {
                  const completed = isDone(axis);
                  const current = normalizeAxis(currentAxis) === axis && !completed;
                  const marker = completed ? "text-emerald-500" : current ? "text-violet-500" : "text-slate-300";
                  const textCls = completed ? "text-emerald-700" : current ? "text-violet-700" : "text-slate-500";
                  return (
                    <div key={axis} className="flex items-start gap-3">
                      <div className="mt-0.5 shrink-0">
                        {completed ? <CheckCircle2 className={`h-4 w-4 ${marker}`} /> : <Circle className={`h-4 w-4 ${marker}`} />}
                      </div>
                      <div className="flex flex-col">
                        <span className={`text-xs font-bold uppercase tracking-wider ${textCls}`}>{getAxisDisplayName(axis, language)}</span>
                        <span className="mt-0.5 text-[11px] font-normal leading-normal text-slate-500">{getAxisSubtitle(axis, language)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-slate-500">
                {copy.clientGuidance}
              </p>
            </div>
          </div>

          {/* ── Chat area ── */}
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-4 sm:px-5">
              <Sparkles className="h-5 w-5 text-violet-500" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">{copy.assistantName}</h2>
                <p className="text-xs text-slate-500">{copy.assessmentName}</p>
              </div>
            </div>

            {phase === "done" ? (
              <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50">
                  <CheckCircle2 className="h-9 w-9 text-emerald-500" />
                </div>
                <h2 className="mt-5 text-2xl font-bold text-slate-900">{copy.thankYouTitle}</h2>
                <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
                  {copy.thankYouLead}
                </p>
              </div>
            ) : (
              <>
                <div ref={scrollRef} className="flex-1 overflow-y-auto bg-white px-4 py-4 sm:px-5">
                  <div className="space-y-4 pb-[50vh]">
                    {messages.map((m, idx) => {
                      // The last assistant message is the question we scroll to the top.
                      const isLatestAssistant =
                        m.role === "assistant" &&
                        idx === messages.map((x) => x.role === "user").lastIndexOf(false);
                      return (
                      <div
                        key={m.id}
                        ref={isLatestAssistant ? activeQuestionRef : null}
                        className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                      >
                        {m.role === "assistant" ? (
                          <div className="mr-2 mt-1 shrink-0">
                            <Avatar chatbot size={30} alt="EY Assistant avatar" />
                          </div>
                        ) : null}
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          className={`max-w-[95%] rounded-2xl px-5 py-4 text-[17px] leading-relaxed shadow-sm sm:max-w-[90%] ${
                            m.role === "user"
                              ? "rounded-tr-none bg-slate-900 font-normal text-white"
                              : "rounded-tl-none border border-slate-200 bg-slate-50 font-normal text-slate-800"
                          }`}
                        >
                          {m.role === "user" ? m.text : <AssistantText text={m.text} />}
                        </motion.div>
                      </div>
                      );
                    })}
                    {busy && (
                      <div className="flex justify-start">
                        <div className="mr-2 mt-1 shrink-0">
                          <Avatar chatbot size={30} alt="EY Assistant avatar" />
                        </div>
                        <div className="max-w-[88%] rounded-2xl rounded-tl-none border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
                          <div className="flex items-center gap-2 text-slate-600">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>{copy.assistantThinking}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={endRef} />
                  </div>
                </div>

                {/* Input + boxed options */}
                <div className="border-t border-slate-100 bg-white p-4 sm:p-5">
                  <form
                    onSubmit={onSubmit}
                    className={`relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-200 ${
                      isFocused
                        ? "border-violet-400 bg-white shadow-md shadow-violet-100 ring-4 ring-violet-50"
                        : "border-slate-200 bg-white shadow-sm hover:border-slate-300"
                    }`}
                  >
                    {phase === "asking" && options.length > 0 ? (
                      <div className="border-b border-slate-100 bg-slate-50/50">
                        <MultiChoiceOptions options={options} disabled={busy} onSelect={(text) => void send(text)} />
                      </div>
                    ) : null}
                    <div className="relative flex items-center bg-white transition-colors duration-150 hover:bg-violet-50/30">
                      <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        disabled={phase !== "asking"}
                        placeholder={
                          options.length > 0
                            ? copy.answerWithOptionsPlaceholder
                            : copy.answerPlaceholder
                        }
                        className="min-h-[60px] flex-1 bg-transparent px-5 text-[16px] text-slate-800 outline-none disabled:opacity-60"
                      />
                      <button
                        type="submit"
                        disabled={phase !== "asking" || !input.trim()}
                        className="mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-white transition hover:bg-violet-700 disabled:opacity-40"
                      >
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      </button>
                    </div>
                  </form>
                </div>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
