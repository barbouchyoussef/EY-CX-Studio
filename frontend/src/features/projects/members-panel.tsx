import { useState, type FormEvent } from "react";
import { projectCopy } from "./copy";
import { UserPlus, X, Users } from "lucide-react";
import type { ProjectMember } from "../../lib/projectsApi";

type Props = {
  members: ProjectMember[];
  myRole: string; // 'owner' | 'collaborator'
  isFrench: boolean;
  onAdd: (email: string) => Promise<void>;
  onRemove: (userId: number) => void | Promise<void>;
};

const initials = (name: string) =>
  name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "U";

/** Collaborators on a project. The owner can add existing platform users by email and remove
 *  collaborators; everyone can see who's on the team. */
export default function ProjectMembersPanel({ members, myRole, isFrench, onAdd, onRemove }: Props) {
  const copy = projectCopy(isFrench);
  const isOwner = myRole === "owner";
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError(null);
    setBusy(true);
    try {
      await onAdd(email.trim());
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add member");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
        <Users className="h-4 w-4 text-ey-gold" />
        {copy.team}
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
          {members.length}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {members.map((m) => (
          <span
            key={m.user_id}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-1 pl-1 pr-2.5 text-xs"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-[10px] font-semibold text-white">
              {initials(m.full_name)}
            </span>
            <span className="font-medium text-slate-700">{m.full_name}</span>
            {m.role === "owner" ? (
              <span className="rounded-full bg-ey-gold/15 px-1.5 py-0.5 text-[10px] font-semibold text-ey-gold-deep">
                {copy.owner}
              </span>
            ) : (
              isOwner && (
                <button
                  type="button"
                  onClick={() => onRemove(m.user_id)}
                  title={copy.remove}
                  className="text-slate-300 transition hover:text-red-500"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )
            )}
          </span>
        ))}
      </div>

      {isOwner && (
        <form onSubmit={submit} className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={copy.collaboratorPlaceholder}
            className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-ey-gold focus:ring-2 focus:ring-ey-gold/15"
          />
          <button
            type="submit"
            disabled={busy || !email.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-ey-navy px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-ey-navy-hover disabled:opacity-40"
          >
            <UserPlus className="h-3.5 w-3.5" />
            {busy ? (copy.adding) : copy.add}
          </button>
        </form>
      )}
      {error && <p className="mt-2 text-xs font-medium text-red-600">{error}</p>}
      {isOwner && (
        <p className="mt-2 text-[11px] text-slate-400">
          {copy.mustHaveAccount}
        </p>
      )}
    </div>
  );
}
