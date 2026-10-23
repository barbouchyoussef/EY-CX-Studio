import { useState, useRef, useEffect } from "react";
import ModuleHeader from "../../components/ui/module-header";
import {
  ArrowLeft,
  Upload,
  FileText,
  FileSpreadsheet,
  Presentation,
  Image as ImageIcon,
  File,
  Plus,
  FolderOpen,
  Loader2,
  FileCheck,
  Download,
  BarChart3,
  Layers,
  Clock,
  HelpCircle,
  Pencil,
  Trash2,
  RotateCcw,
} from "lucide-react";
import FadeUp from "../../components/FadeUp";
import DeskSessionTable, { type DeskSessionItem } from "./session-table";

import { authFetchUrl } from "../../lib/api";
import { ReportOverviewView, type ReportOverview } from "./overview";
import { exportReportPdf } from "./pdf-export";
import ModuleChat, { type ModuleChatMessage } from "../../components/ui/module-chat";
import ShareButton from "../../components/ui/share-button";
import StudioNav from "../../components/ui/studio-nav";
import AddToProjectButton from "../../components/ui/add-to-project-button";
import { useActiveProject } from "../../context/ActiveProjectContext";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type UploadedFile = {
  id: string;
  doc_id?: string;
  name: string;
  size: number;
  type: string;
  status: "pending" | "processing" | "success" | "failed";
  pageCount?: number;
  error?: string;
  // Kept in memory only (not persisted) so a failed upload can be retried without re-picking.
  file?: File;
};

const formatBytes = (n: number): string => {
  if (!n || n < 1024) return `${n || 0} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: string[];
  ts: number;
};

type Session = {
  id: string;
  session_id: string;
  name: string;
  createdAt: number;
  files: UploadedFile[];
  messages: ChatMessage[];
  reportMarkdown?: string;
  // The structured half. Absent on sessions generated before it existed, which is why the
  // renderer below still falls back to the markdown.
  reportOverview?: ReportOverview | null;
  userContext?: string;
  isGeneratingReport?: boolean;
  reportError?: string;
  docCount?: number; // from the lightweight list, for the dashboard before detail is loaded
  hasReport?: boolean;
  owned?: boolean;
};

type DeskResearchProps = { onBack: () => void };

const ACCEPTED_EXTENSIONS = [".pdf", ".xlsx", ".xls", ".pptx", ".ppt", ".docx", ".doc", ".png", ".jpg", ".jpeg"];

const fileIcon = (name: string) => {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return <FileText className="h-4 w-4 text-red-500" />;
  if (["xlsx", "xls"].includes(ext)) return <FileSpreadsheet className="h-4 w-4 text-emerald-600" />;
  if (["pptx", "ppt"].includes(ext)) return <Presentation className="h-4 w-4 text-orange-500" />;
  if (["png", "jpg", "jpeg"].includes(ext)) return <ImageIcon className="h-4 w-4 text-sky-500" />;
  return <File className="h-4 w-4 text-slate-400" />;
};


/* ------------------------------------------------------------------ */
/*  Markdown Renderer                                                  */
/* ------------------------------------------------------------------ */

/** Render inline markdown (**bold**, *italic*, `code`) inside a line of text. Without this
    the report shows raw asterisks, which is the "it's written in markdown" complaint. */
/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function DeskResearch(
  { onBack, topSlot }: DeskResearchProps & { topSlot?: React.ReactNode },
) {
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const { attach: attachToProject, completeStep } = useActiveProject();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"workspace" | "report">("workspace");
  // The module opens on a dashboard of sessions; opening / creating one enters the workspace.
  const [showDashboard, setShowDashboard] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<DeskSessionItem | null>(null);

  const [dragging, setDragging] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  // Session whose delete is armed (two-click confirm, since it erases all its files).
  const [armedDelete, setArmedDelete] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;

  // Derived progress — one file at a time updates its own row, so these stay live.
  const files = activeSession?.files ?? [];
  const processingCount = files.filter((f) => f.status === "processing").length;
  const readyCount = files.filter((f) => f.status === "success").length;
  const failedCount = files.filter((f) => f.status === "failed").length;
  const isProcessing = processingCount > 0;

  /** Patch one file row inside a session by its local id. */
  const patchFile = (localSessionId: string, fileId: string, patch: Partial<UploadedFile>) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === localSessionId
          ? { ...s, files: s.files.map((f) => (f.id === fileId ? { ...f, ...patch } : f)) }
          : s,
      ),
    );
  };

  /* ---- Mapping backend session/document shapes to the local UI shapes ---- */
  const sessionName = (raw: { title?: string | null; created_at?: string }): string =>
    raw.title?.trim() ||
    `Desk Research · ${raw.created_at ? new Date(raw.created_at).toLocaleDateString() : "session"}`;

  const mapDoc = (d: {
    doc_id: string;
    filename: string;
    format: string;
    status: string;
    page_count?: number | null;
  }): UploadedFile => ({
    id: d.doc_id,
    doc_id: d.doc_id,
    name: d.filename,
    size: 0, // original byte size is not persisted; the row hides size when 0
    type: d.format,
    status: d.status === "success" ? "success" : d.status === "partial" ? "success" : "failed",
    pageCount: d.page_count ?? undefined,
  });

  /* ---- Load the full detail of one session (documents + saved report) ---- */
  const loadSessionDetail = async (localId: string, sessionId: string) => {
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${sessionId}`);
      if (!res.ok) return;
      const data = await res.json();
      setSessions((prev) =>
        prev.map((s) =>
          s.id === localId
            ? {
                ...s,
                name: sessionName(data),
                files: (data.documents || []).map(mapDoc),
                reportMarkdown: data.report_markdown ?? s.reportMarkdown,
                reportOverview: data.report_overview ?? s.reportOverview,
                userContext: data.user_context ?? s.userContext,
                // Restore persisted chat history (falls back to whatever is already local).
                messages: Array.isArray(data.messages) && data.messages.length
                  ? data.messages.map(
                      (m: { id?: string; role: string; text: string; sources?: string[]; ts?: number }): ModuleChatMessage => ({
                        id: m.id ?? `${Math.random()}`,
                        role: m.role === "assistant" ? "assistant" : "user",
                        text: m.text ?? "",
                        sources: m.sources,
                        ts: m.ts ?? Date.now(),
                      }),
                    )
                  : s.messages,
              }
            : s,
        ),
      );
    } catch (err) {
      console.error("Failed to load session detail:", err);
    }
  };

  /* ---- Create New Session via API ---- */
  const createSession = async () => {
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/desk-research/sessions`, { method: "POST" });
      if (!res.ok) return;
      const data = await res.json();
      const newSess: Session = {
        id: data.session_id,
        session_id: data.session_id,
        name: sessionName(data),
        createdAt: data.created_at ? Date.parse(data.created_at) : Date.now(),
        files: [],
        messages: [],
      };
      setSessions((prev) => [newSess, ...prev]);
      setActiveSessionId(newSess.id);
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  // Dashboard → workspace: open the chosen session and pull its detail.
  const openSessionFromDashboard = (s: DeskSessionItem) => {
    setActiveSessionId(s.id);
    setActiveTab(s.has_report ? "report" : "workspace");
    void loadSessionDetail(s.id, s.session_id);
    setShowDashboard(false);
  };

  const newSessionFromDashboard = async () => {
    await createSession();
    setShowDashboard(false);
  };

  // Delete a session from the dashboard (owner only — the server 404s otherwise).
  const removeSession = async (s: DeskSessionItem) => {
    setSessions((prev) => prev.filter((x) => x.session_id !== s.session_id));
    setPendingDelete(null);
    try {
      await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${s.session_id}`, { method: "DELETE" });
    } catch (err) {
      console.error("Delete session failed:", err);
    }
  };

  /* ---- Rename a session (persisted server-side) ---- */
  const commitRename = async (localId: string, sessionId: string) => {
    const title = renameValue.trim();
    setRenamingId(null);
    const current = sessions.find((s) => s.id === localId);
    if (!title || !current || title === current.name) return;
    // Optimistic: show the new name immediately, then persist.
    setSessions((prev) => prev.map((s) => (s.id === localId ? { ...s, name: title } : s)));
    try {
      await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
    } catch (err) {
      console.error("Rename failed:", err);
    }
  };

  /* ---- Delete a session and all its files (server-side too) ---- */
  const deleteSession = async (localId: string, sessionId: string) => {
    const remaining = sessions.filter((s) => s.id !== localId);
    setSessions(remaining);
    setArmedDelete(null);
    if (activeSessionId === localId) {
      const next = remaining[0];
      if (next) {
        setActiveSessionId(next.id);
        void loadSessionDetail(next.id, next.session_id);
      } else {
        setActiveSessionId(null);
        void createSession();
      }
    }
    try {
      await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${sessionId}`, { method: "DELETE" });
    } catch (err) {
      console.error("Delete session failed:", err);
    }
  };

  /* ---- Open a session from the sidebar: select it and pull its latest state ---- */
  const openSession = (localId: string) => {
    setActiveSessionId(localId);
    const s = sessions.find((x) => x.id === localId);
    if (s) void loadSessionDetail(localId, s.session_id);
  };

  /* ---- Bootstrap: restore existing sessions from the server, or start a fresh one ---- */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetchUrl(`${API_BASE_URL}/desk-research/sessions`);
        const list: Array<{
          session_id: string;
          created_at: string;
          title?: string | null;
          document_count?: number;
          has_report?: boolean;
          owned?: boolean;
        }> = res.ok ? await res.json() : [];
        if (cancelled) return;
        // Land on the dashboard: load the list, don't auto-open or auto-create a session.
        const mapped: Session[] = list.map((r) => ({
          id: r.session_id,
          session_id: r.session_id,
          name: sessionName(r),
          createdAt: Date.parse(r.created_at) || Date.now(),
          files: [],
          messages: [],
          docCount: r.document_count ?? 0,
          hasReport: Boolean(r.has_report),
          owned: r.owned !== false,
        }));
        setSessions(mapped);
      } catch (err) {
        console.error("Failed to load sessions:", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* ---- Upload one file (reused by initial upload and retry) ----
     The request stays open while the server runs docling + OCR, so a heavy scanned PDF can
     take minutes; a dropped/timed-out connection lands here as a failure the user can retry. */
  const uploadFileRow = async (localSessionId: string, sessionId: string, file: File, rowId: string) => {
    patchFile(localSessionId, rowId, { status: "processing", error: undefined });
    const fd = new FormData();
    fd.append("files", file);
    try {
      const res = await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${sessionId}/upload`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        patchFile(localSessionId, rowId, { status: "failed", error: `Server error ${res.status} — retry` });
        return;
      }
      const data = await res.json();
      const summary = (data.results || [])[0];
      const backendError = (data.errors || [])[0];
      if (summary) {
        patchFile(localSessionId, rowId, {
          doc_id: summary.doc_id,
          type: summary.format,
          status: summary.status === "success" ? "success" : "failed",
          pageCount: summary.page_count,
          error: summary.status === "success" ? undefined : backendError || "Could not extract this document",
        });
      } else {
        patchFile(localSessionId, rowId, { status: "failed", error: backendError || "Unsupported or empty file" });
      }
    } catch {
      patchFile(localSessionId, rowId, {
        status: "failed",
        error: "Upload interrupted (timeout or server restart) — retry",
      });
    }
  };

  /* ---- Add files: show each immediately, then process one at a time ----
     Sequential rather than parallel: two heavy scanned PDFs at once spike server memory and
     are the main cause of dropped uploads. One at a time is slower but reliable. */
  const addFiles = async (fileList: FileList) => {
    if (!activeSession) return;
    const localSessionId = activeSession.id;
    const sessionId = activeSession.session_id;
    const incoming = Array.from(fileList);
    if (incoming.length === 0) return;

    const rows = incoming.map((f) => ({
      id: `tmp-${Math.random().toString(36).slice(2)}`,
      name: f.name,
      size: f.size,
      type: f.name.split(".").pop()?.toLowerCase() ?? "",
      status: "processing" as const,
      file: f,
    }));
    setSessions((prev) =>
      prev.map((s) => (s.id === localSessionId ? { ...s, files: [...s.files, ...rows] } : s)),
    );

    for (const r of rows) {
      await uploadFileRow(localSessionId, sessionId, r.file, r.id);
    }
  };

  /* ---- Retry a failed file (its File is still held in memory) ---- */
  const retryFile = (localId: string, fileId: string) => {
    const sess = sessions.find((s) => s.id === localId);
    const row = sess?.files.find((f) => f.id === fileId);
    if (!sess || !row?.file) return;
    void uploadFileRow(localId, sess.session_id, row.file, fileId);
  };

  /* ---- Remove a file from the session (and server-side if it was processed) ---- */
  const removeFile = async (localId: string, fileId: string) => {
    const sess = sessions.find((s) => s.id === localId);
    const row = sess?.files.find((f) => f.id === fileId);
    setSessions((prev) =>
      prev.map((s) => (s.id === localId ? { ...s, files: s.files.filter((f) => f.id !== fileId) } : s)),
    );
    if (sess && row?.doc_id) {
      try {
        await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${sess.session_id}/documents/${row.doc_id}`, {
          method: "DELETE",
        });
      } catch (err) {
        console.error("Remove document failed:", err);
      }
    }
  };

  /* ---- Generate Executive Synthesis Report via Mistral ---- */
  const generateReport = async () => {
    if (!activeSession || activeSession.files.length === 0) return;

    const localSessionId = activeSession.id;
    setSessions((prev) =>
      prev.map((s) => (s.id === localSessionId ? { ...s, isGeneratingReport: true, reportError: undefined } : s))
    );

    try {
      const res = await authFetchUrl(`${API_BASE_URL}/desk-research/sessions/${activeSession.session_id}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          language: "English",
          user_context: activeSession.userContext,
        }),
      });
      const data = res.ok ? await res.json() : null;

      if (data && data.status === "success" && data.report_markdown) {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === localSessionId
              ? { ...s, reportMarkdown: data.report_markdown, reportOverview: data.report_overview ?? null, isGeneratingReport: false, reportError: undefined }
              : s,
          ),
        );
        // If launched from a project, link this session + complete the step (no-op otherwise).
        void attachToProject("desk_session", activeSession.session_id, "desk_research", activeSession.name);
        void completeStep("desk_research");
        setActiveTab("report");
      } else {
        const message = data?.message || `Report generation failed (${res.status}).`;
        setSessions((prev) =>
          prev.map((s) => (s.id === localSessionId ? { ...s, isGeneratingReport: false, reportError: message } : s)),
        );
      }
    } catch (err) {
      console.error("Report generation failed:", err);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === localSessionId
            ? { ...s, isGeneratingReport: false, reportError: "Network error while generating the report." }
            : s,
        ),
      );
    }
  };

  /* ---- Chatbot Session Q&A via API ---- */
  /** Append one chat message to the active session's history (persisted per session). */
  const appendChatMessage = (message: ModuleChatMessage) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, messages: [...s.messages, message] } : s)),
    );
  };

  // ── Dashboard of research sessions (the module's landing surface) ──
  if (showDashboard) {
    const deskItems: DeskSessionItem[] = sessions.map((s) => ({
      id: s.id,
      session_id: s.session_id,
      name: s.name,
      createdAt: s.createdAt,
      doc_count: s.docCount ?? s.files.length,
      has_report: s.hasReport ?? Boolean(s.reportMarkdown),
      owned: s.owned,
    }));
    return (
      <div className="min-h-screen bg-[#f6f7fb] text-ink">
        <ModuleHeader title="Desk Research" subtitle="Document analysis" onBack={onBack} />
        {topSlot}
        <div className="mx-auto w-full max-w-7xl px-4 py-8">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Research sessions</h1>
            <p className="mb-6 mt-1 text-sm text-slate-500">
              Your saved sessions — open a session, share it, delete it, or start a new one.
            </p>
            <DeskSessionTable
              sessions={deskItems}
              onOpen={openSessionFromDashboard}
              onNew={newSessionFromDashboard}
              onDelete={(s) => setPendingDelete(s)}
              isFrench={false}
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
                  <h3 className="text-base font-bold text-slate-900">Delete session?</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    “{pendingDelete.name}” and all its documents will be permanently deleted. This cannot be undone.
                  </p>
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setPendingDelete(null)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void removeSession(pendingDelete)}
                  className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-rose-700"
                >
                  <Trash2 className="h-4 w-4" /> Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-[#f6f7fb] text-ink">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <img src={logoSrc} alt="EY" className="h-7 w-auto" />
            <span className="h-4 w-px bg-slate-200" />
            <span className="text-sm font-semibold text-ey-navy">Desk Research & AI Synthesis</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex rounded-full border border-slate-200 bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => setActiveTab("workspace")}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                  activeTab === "workspace" ? "bg-white text-ey-navy shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <Layers className="h-3.5 w-3.5" /> Workspace
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("report")}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                  activeTab === "report" ? "bg-white text-ey-navy shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" /> Executive Report
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowDashboard(true)}
              className="btn-secondary"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </button>

            <span className="h-5 w-px bg-slate-200" />
            <StudioNav />
          </div>
        </div>
      </header>
      {topSlot}

      {/* Main Container */}
      <div className="mx-auto flex max-w-7xl gap-6 px-6 py-8">
        {/* Sidebar: Sessions */}
        <aside className="hidden w-60 shrink-0 md:block">
          <FadeUp>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Research Sessions</h2>
                <button
                  type="button"
                  onClick={createSession}
                  className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                  title="New session"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>

              <ul className="space-y-1">
                {sessions.map((s) => {
                  const active = s.id === activeSessionId;
                  const editing = renamingId === s.id;
                  return (
                    <li key={s.id}>
                      {editing ? (
                        <div className="flex items-center gap-1 rounded-lg bg-ey-navy/5 px-2 py-1.5">
                          <FolderOpen className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                          <input
                            autoFocus
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitRename(s.id, s.session_id);
                              if (e.key === "Escape") setRenamingId(null);
                            }}
                            onBlur={() => commitRename(s.id, s.session_id)}
                            className="min-w-0 flex-1 rounded border border-slate-200 bg-white px-2 py-1 text-[13px] outline-none focus:border-ey-gold"
                          />
                        </div>
                      ) : (
                        <div
                          className={`group flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] transition ${
                            active
                              ? "bg-ey-navy/5 font-semibold text-ey-navy"
                              : "text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => openSession(s.id)}
                            className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          >
                            <FolderOpen className="h-3.5 w-3.5 shrink-0" />
                            <span className="truncate">{s.name}</span>
                          </button>
                          {/* Rename + delete. Delete arms an explicit confirm rather than a
                              fragile double-click, so it can't be disarmed by a focus change. */}
                          {armedDelete === s.id ? (
                            <div className="flex shrink-0 items-center gap-1">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteSession(s.id, s.session_id);
                                }}
                                className="rounded bg-rose-600 px-2 py-0.5 text-[10px] font-bold text-white transition hover:bg-rose-700"
                              >
                                Delete
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setArmedDelete(null);
                                }}
                                className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 transition hover:text-slate-800"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div
                              className={`flex shrink-0 items-center gap-0.5 transition ${
                                active ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                              }`}
                            >
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRenamingId(s.id);
                                  setRenameValue(s.name);
                                }}
                                title="Rename session"
                                aria-label="Rename session"
                                className="rounded p-1 text-slate-400 transition hover:bg-slate-200/60 hover:text-slate-700"
                              >
                                <Pencil className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setArmedDelete(s.id);
                                }}
                                title="Delete session"
                                aria-label="Delete session"
                                className="rounded p-1 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          </FadeUp>
        </aside>

        {/* Content Area */}
        <div className="flex flex-1 flex-col gap-6 lg:flex-row">
          {activeTab === "workspace" ? (
            /* WORKSPACE TAB: Upload & Document Manager */
            <section className="min-w-0 flex-1 space-y-6">
              <FadeUp>
                {/* Live status banner — reflects the real state, not a static note. */}
                {isProcessing ? (
                  <div className="flex items-start gap-3 rounded-xl border border-ey-gold/30 bg-ey-gold/[0.06] px-4 py-3">
                    <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-ey-gold" />
                    <div className="text-xs leading-relaxed text-slate-700">
                      <span className="font-semibold text-slate-800">
                        Processing {processingCount} document{processingCount === 1 ? "" : "s"}…
                      </span>{" "}
                      Extraction, OCR and table parsing can take a few minutes per file — the first
                      file is slowest while the models load. You can keep adding files; each turns
                      green as it finishes. Please leave this tab open.
                    </div>
                  </div>
                ) : readyCount > 0 ? (
                  <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                    <FileCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <p className="text-xs leading-relaxed text-emerald-800">
                      <span className="font-semibold">
                        {readyCount} document{readyCount === 1 ? "" : "s"} ready.
                      </span>{" "}
                      {failedCount > 0 && `${failedCount} could not be processed. `}
                      Add more, or generate the executive report below.
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
                    <Clock className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <p className="leading-relaxed">
                      Upload the documents for this research session. Extraction and OCR run on the
                      server and can take a few minutes per file.
                    </p>
                  </div>
                )}

                {/* Drop zone — always available so files can be added while others process. */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); }}
                  onClick={() => fileInputRef.current?.click()}
                  className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
                    dragging ? "border-ey-gold bg-ey-gold/5" : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50"
                  }`}
                >
                  <Upload className={`h-8 w-8 ${dragging ? "text-ey-gold" : "text-slate-400"}`} />
                  <p className="mt-3 text-sm font-medium text-slate-700">
                    Drag &amp; drop files or click to browse
                  </p>
                  <p className="mt-1 text-xs text-slate-400">PDF, XLSX, PPTX, DOCX, PNG, JPG (Trilingual: EN, AR, FR) · up to 50 MB each</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept={ACCEPTED_EXTENSIONS.join(",")}
                    className="hidden"
                    onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }}
                  />
                </div>

                {/* File list */}
                {activeSession && activeSession.files.length > 0 && (
                  <div className="mt-6 rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <div className="border-b border-slate-100 px-5 py-3.5">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Uploaded Session Documents ({activeSession.files.length})
                      </h3>
                    </div>
                    <ul className="divide-y divide-slate-100">
                      {activeSession.files.map((f) => (
                        <li key={f.id} className="flex items-center gap-3 px-5 py-3">
                          {fileIcon(f.name)}
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-slate-800">{f.name}</p>
                            <p className="text-[11px] text-slate-400">
                              {[
                                f.size > 0 ? formatBytes(f.size) : null,
                                f.pageCount ? `${f.pageCount} page(s)/sheet(s)` : null,
                                f.status === "failed" && f.error ? f.error : null,
                              ]
                                .filter(Boolean)
                                .join(" · ") || " "}
                            </p>
                          </div>
                          {f.status === "processing" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-ey-gold/10 px-2.5 py-1 text-[11px] font-medium text-[#8a6d2f]">
                              <Loader2 className="h-3 w-3 animate-spin" /> Processing…
                            </span>
                          )}
                          {f.status === "success" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                              <FileCheck className="h-3 w-3" /> Ready
                            </span>
                          )}
                          {f.status === "failed" && (
                            <div className="flex shrink-0 items-center gap-1.5">
                              <span
                                className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-700"
                                title={f.error}
                              >
                                Failed
                              </span>
                              {f.file && (
                                <button
                                  type="button"
                                  onClick={() => retryFile(activeSession.id, f.id)}
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
                                  title="Retry upload"
                                >
                                  <RotateCcw className="h-3 w-3" /> Retry
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => removeFile(activeSession.id, f.id)}
                                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                                title="Remove"
                                aria-label="Remove file"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Report Generation Panel — available once at least one document is ready. */}
                {activeSession && readyCount > 0 && (
                  <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex items-start gap-3 mb-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ey-navy text-white">
                        <BarChart3 className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-ey-navy">Executive Report Synthesis</h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Synthesize {readyCount} ready document{readyCount === 1 ? "" : "s"} into a structured executive strategy report.
                        </p>
                      </div>
                    </div>

                    {/* Optional User Context Textarea */}
                    <div className="mb-4">
                      <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                        <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                        Optional Instructions / Specific Analysis Goal:
                      </label>
                      <textarea
                        rows={3}
                        value={activeSession.userContext || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSessions((prev) =>
                            prev.map((s) => (s.id === activeSession.id ? { ...s, userContext: val } : s))
                          );
                        }}
                        placeholder="Explain what these documents are or what specific analysis you want extracted (e.g., 'Focus on Q4 revenue trends, partner share margins, and subscriber churn risks')."
                        className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-3 text-xs text-slate-800 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/20"
                      />
                    </div>

                    {/* Generate Report Button + honest time expectation */}
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
                        <Clock className="h-3 w-3" />
                        {activeSession.isGeneratingReport
                          ? "Reading every document and synthesizing — this can take a few minutes for large sets."
                          : "Generation reads all documents in full; large sets can take a few minutes."}
                      </p>
                      <button
                        type="button"
                        onClick={generateReport}
                        disabled={activeSession.isGeneratingReport || isProcessing}
                        title={isProcessing ? "Wait for documents to finish processing" : undefined}
                        className="inline-flex items-center gap-2 rounded-xl bg-ey-navy px-6 py-3 text-xs font-semibold text-white shadow-sm transition hover:bg-ey-navy-hover disabled:opacity-50"
                      >
                        {activeSession.isGeneratingReport ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" /> Generating Executive Report…
                          </>
                        ) : (
                          <>
                            <BarChart3 className="h-4 w-4" /> Generate Insights &amp; Executive Report
                          </>
                        )}
                      </button>
                    </div>

                    {activeSession.reportError && (
                      <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-[11px] font-medium text-rose-700">
                        {activeSession.reportError}
                      </p>
                    )}
                  </div>
                )}
              </FadeUp>
            </section>
          ) : (
            /* REPORT TAB: Rendered Executive Report — full width, readable measure */
            <section className="min-w-0 flex-1">
              <FadeUp>
                <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white px-8 py-8 shadow-sm md:px-10">
                  {activeSession?.reportMarkdown ? (
                    <div>
                      <div className="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
                        <div className="flex items-center gap-2 text-xs font-semibold text-ey-navy">
                          <BarChart3 className="h-4 w-4 text-ey-gold" /> Executive Report
                        </div>
                        <div className="flex items-center gap-2">
                          {activeSession.session_id && (
                            <AddToProjectButton
                              kind="desk_session"
                              refId={activeSession.session_id}
                              stepKey="desk_research"
                              title={activeSession.name}
                              suggestedName={activeSession.name}
                              compact
                            />
                          )}
                          {activeSession.session_id && (
                            <ShareButton kind="desk_session" refId={activeSession.session_id} compact />
                          )}
                          <button
                            type="button"
                            onClick={() =>
                              exportReportPdf(activeSession.reportMarkdown || "", activeSession.name || "Desk Research")
                            }
                            className="inline-flex items-center gap-1.5 rounded-lg bg-ey-navy px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#2a3050]"
                          >
                            <FileText className="h-3.5 w-3.5" /> Export PDF
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const blob = new Blob([activeSession.reportMarkdown || ""], { type: "text/markdown" });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `Executive_Report_${activeSession.session_id}.md`;
                              a.click();
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            <Download className="h-3.5 w-3.5" /> Markdown
                          </button>
                        </div>
                      </div>
                      <ReportOverviewView
                        overview={activeSession.reportOverview}
                        markdown={activeSession.reportMarkdown}
                      />
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <BarChart3 className="h-10 w-10 text-slate-300" />
                      <p className="mt-4 text-sm font-semibold text-slate-700">No Executive Report Generated Yet</p>
                      <p className="mt-1 text-xs text-slate-400">Upload documents in Workspace tab and click "Generate Insights & Executive Report".</p>
                    </div>
                  )}
                </div>
              </FadeUp>
            </section>
          )}

        </div>
      </div>

      {/* Floating session chatbot — opens/closes via the launcher, takes no layout space. */}
      <ModuleChat
        endpoint={`${API_BASE_URL}/desk-research/sessions/${activeSession?.session_id}/chat`}
        messages={activeSession?.messages ?? []}
        onAppendMessage={appendChatMessage}
        title="Research Assistant"
        subtitle={activeSession?.name}
        emptyTitle="Ask about this session"
        emptyHint="I can search your documents, summarize findings, or just chat."
        placeholder="Ask anything about your documents..."
        disabled={!activeSession?.session_id || readyCount === 0}
        disabledHint={
          !activeSession?.session_id
            ? "Create a session to start chatting."
            : "Upload and process a document first."
        }
      />
    </div>
  );
}
