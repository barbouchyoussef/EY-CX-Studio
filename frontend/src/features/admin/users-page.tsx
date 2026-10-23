import { useEffect, useState } from "react";
import { Home } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import {
  adminListUsers,
  adminUpdateUser,
  apiInvite,
  type AuthUser,
  type InviteResult,
} from "../../lib/api";

const INPUT =
  "rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-ink placeholder-slate-300 outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15";

/** Admin-only: list users, toggle role/status, and invite new people. Light EY theme. */
export default function AdminUsersPage({ onBack }: { onBack: () => void }) {
  const { user: me } = useAuth();
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"consultant" | "admin">("consultant");
  const [lastInvite, setLastInvite] = useState<InviteResult | null>(null);

  const load = async () => {
    try {
      setUsers(await adminListUsers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    }
  };
  useEffect(() => {
    load();
  }, []);

  const patch = async (
    id: number,
    body: { role?: "admin" | "consultant"; status?: "active" | "disabled" },
  ) => {
    setError(null);
    try {
      const updated = await adminUpdateUser(id, body);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const invite = async () => {
    setError(null);
    setLastInvite(null);
    try {
      setLastInvite(await apiInvite(inviteEmail.trim(), inviteRole));
      setInviteEmail("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invite failed");
    }
  };

  const pill = (text: string, tone: "emerald" | "red" | "amber") => {
    const map = {
      emerald: "bg-emerald-50 text-emerald-700",
      red: "bg-red-50 text-red-600",
      amber: "bg-amber-50 text-amber-700",
    } as const;
    return <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${map[tone]}`}>{text}</span>;
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] text-ink">
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/85 px-5 backdrop-blur-lg">
        <div className="flex items-center gap-3">
          <img src={logoSrc} alt="EY" className="h-7 w-auto" />
          <span className="h-4 w-px bg-slate-200" />
          <span className="text-sm font-medium text-slate-500">Team &amp; access</span>
        </div>
        <button
          onClick={onBack}
          className="btn-secondary"
        >
          <Home className="h-3.5 w-3.5" /> Home
        </button>
      </header>

      <div className="mx-auto max-w-3xl px-5 py-10">
        {/* Invite */}
        <section className="mb-8 rounded-2xl border border-slate-100 bg-white/80 p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
          <h2 className="mb-3 text-sm font-bold text-slate-800">Invite a colleague</h2>
          <div className="flex flex-wrap items-center gap-2.5">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              className={`${INPUT} flex-1`}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as "consultant" | "admin")}
              className={INPUT}
            >
              <option value="consultant">Consultant</option>
              <option value="admin">Admin</option>
            </select>
            <button
              onClick={invite}
              disabled={!inviteEmail}
              className="rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-hover disabled:opacity-40"
            >
              Send invite
            </button>
          </div>
          {lastInvite && (
            <p className="mt-3 break-all rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Invitation created for <span className="font-semibold">{lastInvite.email}</span>. An email
              was sent; if delivery isn’t configured, share this link:{" "}
              <span className="text-[#B8860B] underline">{lastInvite.accept_path}</span>
            </p>
          )}
        </section>

        {error && (
          <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-600">{error}</p>
        )}

        {/* Users */}
        <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-5 py-3">User</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === me?.id;
                return (
                  <tr key={u.id} className="border-t border-slate-100">
                    <td className="px-5 py-3">
                      <div className="font-semibold text-slate-800">{u.full_name}</div>
                      <div className="text-xs text-slate-400">{u.email}</div>
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-600">{u.role}</td>
                    <td className="px-4 py-3">
                      {u.status === "active"
                        ? pill("active", "emerald")
                        : u.status === "disabled"
                          ? pill("disabled", "red")
                          : pill("pending", "amber")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {u.role === "consultant" ? (
                          <button
                            onClick={() => patch(u.id, { role: "admin" })}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300"
                          >
                            Make admin
                          </button>
                        ) : (
                          <button
                            disabled={isSelf}
                            onClick={() => patch(u.id, { role: "consultant" })}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300 disabled:opacity-30"
                          >
                            Make consultant
                          </button>
                        )}
                        {u.status !== "disabled" ? (
                          <button
                            disabled={isSelf}
                            onClick={() => patch(u.id, { status: "disabled" })}
                            className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-600 hover:bg-red-100 disabled:opacity-30"
                          >
                            Disable
                          </button>
                        ) : (
                          <button
                            onClick={() => patch(u.id, { status: "active" })}
                            className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                          >
                            Enable
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
