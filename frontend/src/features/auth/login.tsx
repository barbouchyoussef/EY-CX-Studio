import { useState, type FormEvent } from "react";
import { useAuth } from "../../context/AuthContext";

const INPUT =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink placeholder-slate-300 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15";

/** Email + password sign-in, styled to the platform's light EY theme. */
export default function LoginPage({
  onSuccess,
  onForgot,
}: {
  onSuccess: () => void;
  onForgot?: () => void;
}) {
  const { login } = useAuth();
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] px-4 text-ink">
      {/* soft brand glow */}
      <div className="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.14),transparent_70%)]" />

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src={logoSrc} alt="EY Studio+" className="mb-6 h-11 w-auto" />
          <h1 className="text-2xl font-medium tracking-[-0.02em] text-ink">Sign in</h1>
          <p className="mt-1.5 text-sm text-slate-500">Sign in to the CX intelligence suite</p>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-slate-100 bg-white/80 p-7 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur-md sm:p-8"
        >
          <label className="mb-1.5 block text-xs font-semibold text-slate-600">Email</label>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className={`${INPUT} mb-4`}
          />

          <label className="mb-1.5 block text-xs font-semibold text-slate-600">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            className={`${INPUT} mb-4`}
          />

          {error && (
            <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-ink px-8 py-3 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover disabled:translate-y-0 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>

          {onForgot && (
            <button
              type="button"
              onClick={onForgot}
              className="mt-4 block w-full text-center text-xs font-medium text-slate-500 transition hover:text-ey-gold"
            >
              Forgot your password?
            </button>
          )}
        </form>

        <p className="mt-6 text-center text-[11px] text-slate-400">
          Access is invite-only. Ask an administrator for an invitation.
        </p>
      </div>
    </div>
  );
}
