import { useState, type FormEvent } from "react";
import { apiForgotPassword } from "../../lib/api";

const INPUT =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink placeholder-slate-300 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15";
const SHELL =
  "relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] px-4 text-ink";
const BTN =
  "inline-flex w-full items-center justify-center rounded-full bg-ink px-8 py-3 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover disabled:translate-y-0 disabled:opacity-50";

/** Request a password-reset link. The response is intentionally the same whether or not the
 *  email is registered, so this screen never confirms account existence. */
export default function ForgotPasswordPage({ onBack }: { onBack: () => void }) {
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await apiForgotPassword(email.trim());
      setSent(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={SHELL}>
      <div className="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.14),transparent_70%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src={logoSrc} alt="EY Studio+" className="mb-6 h-11 w-auto" />
          <h1 className="text-2xl font-medium tracking-[-0.02em]">Reset your password</h1>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-white/80 p-7 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur-md sm:p-8">
          {sent ? (
            <>
              <p className="text-sm text-slate-600">
                If that email is registered, a reset link has been sent. Check your inbox and follow
                the link (it expires shortly).
              </p>
              <button onClick={onBack} className={`${BTN} mt-6`}>
                Back to sign in
              </button>
            </>
          ) : (
            <form onSubmit={submit}>
              <p className="mb-4 text-xs text-slate-500">
                Enter your email and we’ll send you a link to set a new password.
              </p>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className={`${INPUT} mb-4`}
              />
              <button type="submit" disabled={busy} className={BTN}>
                {busy ? "Sending…" : "Send reset link"}
              </button>
              <button
                type="button"
                onClick={onBack}
                className="mt-4 block w-full text-center text-xs font-medium text-slate-500 transition hover:text-ey-gold"
              >
                Back to sign in
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
