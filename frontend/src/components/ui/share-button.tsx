import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { Share2, X, Check } from "lucide-react";
import {
  listSharesFor,
  shareAnalysis,
  unshareAnalysis,
  type AnalysisKind,
  type ShareRecipient,
} from "../../lib/projectsApi";

type Props = {
  kind: AnalysisKind;
  refId: string;
  /** Optional compact style for placing in a header row. */
  compact?: boolean;
};

/** Share an individual analysis with an existing platform user. Reusable across modules:
 *  pass the analysis kind + its ref (report filename / guide id / session id / assessment id). */
export default function ShareButton({ kind, refId, compact }: Props) {
  const [open, setOpen] = useState(false);
  const [recipients, setRecipients] = useState<ShareRecipient[]>([]);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // The panel is portaled to <body> (so a table's overflow can't clip it), positioned from the
  // trigger's rect. Recompute before paint whenever it opens.
  useLayoutEffect(() => {
    if (!open || !ref.current) return;
    const place = () => {
      const r = ref.current!.getBoundingClientRect();
      setPos({ top: r.bottom + 8, right: window.innerWidth - r.right });
    };
    place();
    // A fixed panel drifts on scroll/resize — just close it, cheaper than tracking.
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || panelRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const load = async () => {
    try {
      setRecipients(await listSharesFor(kind, refId));
    } catch {
      /* keep the dialog usable even if the list fails */
    }
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    setError(null);
    if (next) load();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError(null);
    setBusy(true);
    try {
      await shareAnalysis(kind, refId, email.trim());
      setEmail("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not share");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (shareId: number) => {
    await unshareAnalysis(shareId);
    setRecipients((prev) => prev.filter((r) => r.share_id !== shareId));
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={toggle}
        className={
          compact
            ? "inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
            : "inline-flex items-center gap-1.5 rounded-lg bg-ey-navy px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-ey-navy-hover"
        }
      >
        <Share2 className="h-3.5 w-3.5" />
        Share
        {recipients.length > 0 && (
          <span className="rounded-full bg-ey-gold/20 px-1.5 text-[10px] font-bold text-ey-gold-deep">
            {recipients.length}
          </span>
        )}
      </button>

      {open && pos && createPortal(
        <div
          ref={panelRef}
          style={{ position: "fixed", top: pos.top, right: pos.right }}
          className="z-[60] w-72 rounded-xl border border-slate-100 bg-white p-3 shadow-[0_12px_40px_rgba(15,23,42,0.14)]"
        >
          <p className="mb-2 text-xs font-semibold text-slate-700">Share with a colleague</p>

          <form onSubmit={submit} className="flex items-center gap-1.5">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@company.com"
              className="flex-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15"
            />
            <button
              type="submit"
              disabled={busy || !email.trim()}
              className="flex h-7 w-7 items-center justify-center rounded-lg bg-ey-navy text-white transition hover:bg-ey-navy-hover disabled:opacity-40"
              title="Share"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
          </form>
          {error && <p className="mt-1.5 text-[11px] font-medium text-red-600">{error}</p>}

          {recipients.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Shared with</p>
              {recipients.map((r) => (
                <div key={r.share_id} className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-slate-700">{r.full_name}</div>
                    <div className="truncate text-[10px] text-slate-400">{r.email}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => revoke(r.share_id)}
                    title="Revoke"
                    className="text-slate-300 transition hover:text-red-500"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <p className="mt-2 text-[10px] text-slate-400">
            They must already have an account. It appears in their history immediately.
          </p>
        </div>,
        document.body
      )}
    </div>
  );
}
