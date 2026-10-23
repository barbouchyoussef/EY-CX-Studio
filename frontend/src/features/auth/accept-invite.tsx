import { useState, type FormEvent } from "react";
import { useAuth } from "../../context/AuthContext";
import { passwordValid } from "../../lib/password";
import PasswordRequirements from "./password-requirements";

const INPUT =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink placeholder-slate-300 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15";
const SHELL =
  "relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] px-4 text-ink";

/** Invite acceptance: the token comes from the ?token= query param of the emailed link. */
export default function AcceptInvitePage({ onSuccess }: { onSuccess: () => void }) {
  const { acceptInvite } = useAuth();
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const token =
    typeof window === "undefined"
      ? ""
      : new URLSearchParams(window.location.search).get("token") ?? "";

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!passwordValid(password)) {
      setError("Please meet the password requirements below.");
      return;
    }
    setBusy(true);
    try {
      await acceptInvite(token, fullName.trim(), password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not accept invitation");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <div className={SHELL}>
        <div className="max-w-md rounded-2xl border border-slate-100 bg-white/80 p-8 text-center text-sm text-slate-600 shadow-[0_12px_40px_rgba(15,23,42,0.06)]">
          This invitation link is missing its token. Ask for a fresh invitation.
        </div>
      </div>
    );
  }

  return (
    <div className={SHELL}>
      <div className="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.14),transparent_70%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src={logoSrc} alt="EY Studio+" className="mb-6 h-11 w-auto" />
          <h1 className="text-2xl font-medium tracking-[-0.02em]">Accept your invitation</h1>
          <p className="mt-1.5 text-sm text-slate-500">Set your name and a password to finish.</p>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-slate-100 bg-white/80 p-7 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur-md sm:p-8"
        >
          <label className="mb-1.5 block text-xs font-semibold text-slate-600">Full name</label>
          <input
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={`${INPUT} mb-4`}
          />

          <label className="mb-1.5 block text-xs font-semibold text-slate-600">Password</label>
          <input
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={`${INPUT} mb-2`}
          />
          <PasswordRequirements pw={password} />

          {error && (
            <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="inline-flex w-full items-center justify-center rounded-full bg-ink px-8 py-3 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover disabled:translate-y-0 disabled:opacity-50"
          >
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
