import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import StudioNav from "./studio-nav";

/**
 * The product header every module page opens with.
 *
 * Copied from the interview hub's header so the modules match exactly -- same logo (`ey_logo.svg`),
 * same spacing, same right-hand cluster. The dashboard views of the other modules had only a bare
 * Back button, which left the project band with nothing above it and made each page look like a
 * different product.
 */
export default function ModuleHeader({
  title,
  subtitle,
  onBack,
  backLabel,
  right,
  isFrench = false,
}: {
  title: string;
  subtitle?: string;
  onBack: () => void;
  backLabel?: string;
  /** Module-specific controls, placed before the account cluster. */
  right?: ReactNode;
  isFrench?: boolean;
}) {
  return (
    <header className="no-print sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/80 bg-white/95 px-6 py-4 backdrop-blur-sm">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onBack}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-500 transition-all hover:border-slate-300 hover:text-slate-800"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {backLabel ?? (isFrench ? "Retour" : "Back")}
        </button>

        <div className="h-6 w-px shrink-0 bg-slate-200" />

        <div className="flex min-w-0 items-center gap-2.5">
          <img
            src={`${import.meta.env.BASE_URL}ey_logo.svg`}
            alt="EY"
            className="block h-7 w-auto shrink-0"
          />
          <div className="min-w-0">
            <h1 className="flex items-center gap-1.5 truncate text-sm font-bold leading-none tracking-tight text-slate-900">
              {title}
              <span className="inline-block h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-yellow-400" />
            </h1>
            {subtitle && (
              <p className="mt-0.5 truncate text-[9px] font-medium uppercase leading-none tracking-widest text-slate-400">
                {subtitle}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {right}
        <span className="h-6 w-px bg-slate-200" />
        <StudioNav isFrench={isFrench} />
      </div>
    </header>
  );
}
