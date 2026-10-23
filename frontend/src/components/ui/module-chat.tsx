import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Bot, FileText, Loader2, MessageCircle, Send, Sparkles, X } from "lucide-react";
import { authFetchUrl } from "../../lib/api";

/* ------------------------------------------------------------------ */
/*  Lightweight markdown renderer for assistant messages              */
/*  Handles: ## / ### headings, - / * / 1. lists, **bold**, *italic*,  */
/*  `code`, and highlighted [filename, p#] citation badges.            */
/* ------------------------------------------------------------------ */

const CITATION_RE =
  /\[(?:Source:\s*)?[^\]\n]*?\.(?:pdf|docx?|pptx?|xlsx?|png|jpe?g|tiff?|bmp|webp)[^\]\n]*?\]/gi;
const EMPHASIS_RE = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g;

function renderEmphasis(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  EMPHASIS_RE.lastIndex = 0;
  while ((m = EMPHASIS_RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${keyBase}-b${key}`} className="font-semibold text-ey-navy">{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={`${keyBase}-c${key}`} className="rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[0.9em]">{tok.slice(1, -1)}</code>);
    else out.push(<em key={`${keyBase}-i${key}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
    key++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;
  while ((m = CITATION_RE.exec(text)) !== null) {
    if (m.index > last) out.push(...renderEmphasis(text.slice(last, m.index), `${keyBase}-e${key}`));
    const label = m[0].replace(/^\[(?:Source:\s*)?/i, "").replace(/\]$/, "").trim();
    out.push(
      <span
        key={`${keyBase}-cite${key}`}
        className="mx-0.5 inline-flex items-center gap-1 rounded-md bg-ey-gold/15 px-1.5 py-0.5 align-baseline text-[10px] font-semibold text-[#8a6a1e]"
      >
        <FileText className="h-2.5 w-2.5" />
        {label}
      </span>,
    );
    last = m.index + m[0].length;
    key++;
  }
  if (last < text.length) out.push(...renderEmphasis(text.slice(last), `${keyBase}-e${key}`));
  return out;
}

export function ChatMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushList = (key: string) => {
    if (!list) return;
    const { ordered, items } = list;
    const Tag = ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={key} className={`my-1.5 ml-4 space-y-1 ${ordered ? "list-decimal" : "list-disc"} marker:text-ey-gold`}>
        {items.map((it, i) => (
          <li key={i}>{renderInline(it, `${key}-${i}`)}</li>
        ))}
      </Tag>,
    );
    list = null;
  };

  lines.forEach((raw, idx) => {
    const line = raw.trim();
    const ol = line.match(/^(\d+)\.\s+(.*)$/);
    const ul = line.match(/^[-*]\s+(.*)$/);
    if (ul) {
      if (!list || list.ordered) flushList(`l${idx}`);
      list = list ?? { ordered: false, items: [] };
      list.items.push(ul[1]);
      return;
    }
    if (ol) {
      if (!list || !list.ordered) flushList(`l${idx}`);
      list = list ?? { ordered: true, items: [] };
      list.items.push(ol[2]);
      return;
    }
    flushList(`l${idx}`);
    if (!line) return;
    if (line.startsWith("### ") || line.startsWith("#### ")) {
      blocks.push(<h4 key={idx} className="mt-2 mb-1 text-[12px] font-bold text-ey-navy">{renderInline(line.replace(/^#+\s/, ""), `h${idx}`)}</h4>);
    } else if (line.startsWith("## ")) {
      blocks.push(<h3 key={idx} className="mt-2 mb-1 text-[13px] font-bold text-ey-navy">{renderInline(line.slice(3), `h${idx}`)}</h3>);
    } else if (line === "---" || line === "***") {
      blocks.push(<hr key={idx} className="my-2 border-slate-200" />);
    } else {
      blocks.push(<p key={idx} className="my-1 leading-relaxed">{renderInline(line, `p${idx}`)}</p>);
    }
  });
  flushList("l-end");
  return <div className="text-xs text-slate-800">{blocks}</div>;
}

/* ------------------------------------------------------------------ */
/*  Reusable floating module chatbot                                   */
/*                                                                    */
/*  One chat UI for every module, rendered as a floating button that   */
/*  opens a chat panel (it takes no layout space when closed). Only the */
/*  DATA SOURCE changes: pass a different `endpoint` and keep your own  */
/*  `messages` array. Backend contract: POST endpoint with             */
/*  { query, history } -> { answer, sources }. Retrieval + agentic      */
/*  answering live server-side in the shared RAG engine.               */
/* ------------------------------------------------------------------ */

export type ModuleChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: string[];
  ts: number;
};

export type ModuleChatProps = {
  /** Full URL to POST the query to. Returns { answer, sources }. */
  endpoint: string;
  /** Message history (owned by the parent so it can persist per session/project). */
  messages: ModuleChatMessage[];
  /** Append a single message to the parent's store. */
  onAppendMessage: (message: ModuleChatMessage) => void;
  title?: string;
  subtitle?: string;
  emptyTitle?: string;
  emptyHint?: string;
  placeholder?: string;
  /** When true, input is disabled (e.g. no documents ready yet). */
  disabled?: boolean;
  disabledHint?: string;
  /** How many recent turns to send as conversation history. */
  historyTurns?: number;
  /** Build the request body from the query + history. Defaults to `{ query, history }`. */
  buildBody?: (query: string, history: { role: string; text: string }[]) => Record<string, unknown>;
  /** Awaited before each send — e.g. flush a save so the server reads the freshest state. */
  beforeSend?: () => Promise<void> | void;
};

const newId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export default function ModuleChat({
  endpoint,
  messages,
  onAppendMessage,
  title = "Assistant",
  subtitle,
  emptyTitle = "Ask a question",
  emptyHint = "Answers cite their source.",
  placeholder = "Type your question...",
  disabled = false,
  disabledHint,
  historyTurns = 6,
  buildBody = (query, history) => ({ query, history }),
  beforeSend,
}: ModuleChatProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading, open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const send = async () => {
    const query = input.trim();
    if (!query || loading || disabled) return;

    // Snapshot history BEFORE appending the new user message.
    const history = messages.slice(-historyTurns).map((m) => ({ role: m.role, text: m.text }));

    setInput("");
    setLoading(true);
    onAppendMessage({ id: newId(), role: "user", text: query, ts: Date.now() });

    try {
      // Flush any pending save so the server reads the freshest state (e.g. the live guide).
      if (beforeSend) {
        try {
          await beforeSend();
        } catch {
          /* a failed pre-save must not block the question */
        }
      }
      const res = await authFetchUrl(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBody(query, history)),
      });
      if (res.ok) {
        const data = await res.json();
        onAppendMessage({
          id: newId(),
          role: "assistant",
          text: data.answer ?? "No answer was returned.",
          sources: data.sources,
          ts: Date.now(),
        });
      } else {
        onAppendMessage({
          id: newId(),
          role: "assistant",
          text: "Sorry — the assistant could not answer that just now. Please try again.",
          ts: Date.now(),
        });
      }
    } catch {
      onAppendMessage({
        id: newId(),
        role: "assistant",
        text: "Network error while reaching the assistant.",
        ts: Date.now(),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating launcher — visible only when the panel is closed. */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`Open ${title}`}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-ey-navy text-white shadow-xl shadow-ey-navy/25 ring-1 ring-white/10 transition hover:scale-105 hover:bg-ey-navy-hover"
        >
          <MessageCircle className="h-6 w-6" />
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-ey-gold">
            <Sparkles className="h-2.5 w-2.5 text-white" />
          </span>
        </button>
      )}

      {/* Floating panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 flex max-h-[min(680px,calc(100vh-3rem))] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 bg-ey-navy px-4 py-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">
                <Bot className="h-4 w-4 text-ey-gold" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">{title}</h3>
                {subtitle && <p className="text-[11px] text-white/60">{subtitle}</p>}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-white/70 transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4" style={{ minHeight: 320 }}>
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-12 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ey-navy/5">
                  <Bot className="h-6 w-6 text-ey-navy" />
                </div>
                <p className="mt-4 text-sm font-medium text-slate-700">{emptyTitle}</p>
                <p className="mt-1 text-xs text-slate-400">{emptyHint}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((m) => (
                  <div key={m.id} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    {m.role === "assistant" && (
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ey-navy/5">
                        <Bot className="h-3.5 w-3.5 text-ey-navy" />
                      </div>
                    )}
                    <div
                      className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                        m.role === "user"
                          ? "bg-ey-navy font-medium text-white"
                          : "border border-slate-100 bg-slate-50 text-slate-800"
                      }`}
                    >
                      {m.role === "user" ? (
                        <p className="whitespace-pre-wrap">{m.text}</p>
                      ) : (
                        <ChatMarkdown text={m.text} />
                      )}
                      {m.sources && m.sources.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-slate-200/60 pt-2.5">
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Sources</span>
                          {m.sources.map((s, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1 rounded-md bg-ey-navy/[0.06] px-1.5 py-0.5 text-[10px] font-semibold text-ey-navy"
                            >
                              <FileText className="h-2.5 w-2.5 text-ey-gold" />
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-ey-gold" />
                    Thinking...
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 px-4 py-3">
            {disabled && disabledHint && (
              <p className="mb-2 text-center text-[11px] text-slate-400">{disabledHint}</p>
            )}
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                disabled={disabled}
                placeholder={placeholder}
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/20 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={send}
                disabled={!input.trim() || loading || disabled}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ey-navy text-white transition hover:bg-ey-navy-hover disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
