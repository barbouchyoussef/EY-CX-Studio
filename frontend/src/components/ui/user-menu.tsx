import { useEffect, useRef, useState } from "react";
import { ChevronDown, KeyRound, LogOut, Users } from "lucide-react";

type Props = {
  fullName: string;
  role: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

/** Light-themed account menu (name + dropdown). Meant to sit inside a header/nav, not float. */
export default function UserMenu({ fullName, role, onNavigate, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const initials =
    fullName.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "U";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 py-1 pl-1 pr-2.5 text-xs font-semibold text-slate-700 shadow-sm backdrop-blur transition hover:border-slate-300"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-[10px] text-white">
          {initials}
        </span>
        <span className="max-w-[9rem] truncate">{fullName}</span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-xl border border-slate-100 bg-white py-1 shadow-[0_12px_40px_rgba(15,23,42,0.12)]">
          <div className="px-3 py-2 text-[11px] uppercase tracking-wide text-slate-400">
            {role === "admin" ? "Administrator" : "Consultant"}
          </div>
          <button
            onClick={() => { setOpen(false); onNavigate("/account"); }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
          >
            <KeyRound className="h-4 w-4 text-slate-400" /> Change password
          </button>
          {role === "admin" && (
            <button
              onClick={() => { setOpen(false); onNavigate("/manage-users"); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
            >
              <Users className="h-4 w-4 text-slate-400" /> Team &amp; access
            </button>
          )}
          <div className="my-1 h-px bg-slate-100" />
          <button
            onClick={() => { setOpen(false); onLogout(); }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
