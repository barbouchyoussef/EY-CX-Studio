import { useState, type FormEvent } from "react";
import { apiChangePassword, apiUpdateProfile } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { passwordValid } from "../../lib/password";
import PasswordRequirements from "./password-requirements";

const INPUT =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink placeholder-slate-300 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15";
const SHELL =
  "relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] px-4 text-ink";
const BTN =
  "inline-flex w-full items-center justify-center rounded-full bg-ink px-8 py-3 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover disabled:translate-y-0 disabled:opacity-50";

/** Account settings while signed in: display name, and password.
 *  Changing the password rotates every other session but keeps this one alive. */
export default function ChangePasswordPage({ onBack }: { onBack: () => void }) {
  const { user, applyUser } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [nameBusy, setNameBusy] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!passwordValid(next)) return setError("Please meet the password requirements below.");
    if (next !== confirm) return setError("New passwords do not match.");
    setBusy(true);
    try {
      await apiChangePassword(current, next);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  };

  const saveName = async (e: FormEvent) => {
    e.preventDefault();
    setNameError(null);
    setNameSaved(false);
    const trimmed = name.trim();
    if (trimmed.length < 2) return setNameError("Please enter at least 2 characters.");
    if (trimmed === user?.full_name) return;
    setNameBusy(true);
    try {
      applyUser(await apiUpdateProfile(trimmed));
      setNameSaved(true);
    } catch (err) {
      setNameError(err instanceof Error ? err.message : "Could not update your name");
    } finally {
      setNameBusy(false);
    }
  };

  return (
    <div className={SHELL}>
      <div className="relative w-full max-w-md py-10">
        <h1 className="mb-6 text-center text-2xl font-medium tracking-[-0.02em]">Account settings</h1>

        {/* ── Display name ─────────────────────────────────────────── */}
        <div className="mb-5 rounded-2xl border border-slate-100 bg-white/80 p-7 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur-md sm:p-8">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Your name</h2>
          <p className="mb-4 text-xs text-slate-500">
            Shown to colleagues on the analyses you own and share.
          </p>
          <form onSubmit={saveName}>
            <input
              type="text"
              autoComplete="name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameSaved(false);
              }}
              className={`${INPUT} mb-3`}
            />
            {user?.email && (
              <p className="mb-3 text-xs text-slate-400">
                Signed in as {user.email} — contact an administrator to change your email.
              </p>
            )}
            {nameError && (
              <p className="mb-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-600">{nameError}</p>
            )}
            {nameSaved && (
              <p className="mb-3 text-xs font-medium text-emerald-600">Your name has been updated.</p>
            )}
            <button
              type="submit"
              disabled={nameBusy || name.trim() === (user?.full_name ?? "") || name.trim().length < 2}
              className={BTN}
            >
              {nameBusy ? "Saving…" : "Save name"}
            </button>
          </form>
        </div>

        {/* ── Password ─────────────────────────────────────────────── */}
        <div className="rounded-2xl border border-slate-100 bg-white/80 p-7 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur-md sm:p-8">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Change password</h2>
          {done ? (
            <>
              <p className="text-sm font-medium text-emerald-600">Your password has been updated.</p>
              <button onClick={onBack} className={`${BTN} mt-6`}>
                Done
              </button>
            </>
          ) : (
            <form onSubmit={submit}>
              {(
                [
                  ["Current password", current, setCurrent, "current-password"],
                  ["New password", next, setNext, "new-password"],
                  ["Confirm new password", confirm, setConfirm, "new-password"],
                ] as const
              ).map(([label, val, set, ac]) => (
                <div key={label}>
                  <label className="mb-1.5 block text-xs font-semibold text-slate-600">{label}</label>
                  <input
                    type="password"
                    autoComplete={ac}
                    required
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    className={`${INPUT} ${label === "New password" ? "mb-2" : "mb-4"}`}
                  />
                  {label === "New password" && <PasswordRequirements pw={val} />}
                </div>
              ))}
              {error && (
                <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-600">{error}</p>
              )}
              <button type="submit" disabled={busy} className={BTN}>
                {busy ? "Saving…" : "Update password"}
              </button>
              <button
                type="button"
                onClick={onBack}
                className="mt-4 block w-full text-center text-xs font-medium text-slate-500 transition hover:text-ey-gold"
              >
                Cancel
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
