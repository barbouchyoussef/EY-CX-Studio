import { Check } from "lucide-react";
import { PASSWORD_RULES } from "../../lib/password";

/** Live checklist under a password field: ticks each rule as it's met, greys the rest. */
export default function PasswordRequirements({ pw }: { pw: string }) {
  return (
    <ul className="mb-4 space-y-1">
      {PASSWORD_RULES.map((r) => {
        const ok = r.test(pw);
        return (
          <li
            key={r.key}
            className={`flex items-center gap-2 text-[11px] transition-colors ${
              ok ? "text-emerald-600" : "text-slate-400"
            }`}
          >
            <span
              className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border ${
                ok ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300"
              }`}
            >
              {ok && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
            </span>
            {r.label}
          </li>
        );
      })}
    </ul>
  );
}
