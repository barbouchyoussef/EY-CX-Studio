/**
 * Presentational building blocks for the social report.
 *
 * Extracted from the report view, which was 2,811 lines. Everything here takes props and
 * returns markup: section headings, KPI tiles, panels, the sticky table of contents, and the
 * small donut charts. None of it reads report data directly, so each piece can be understood, and
 * changed, without opening the report itself.
 */

import { NEGATIVE_MARK, NEUTRAL_MARK, POSITIVE_MARK } from "./colors";
import { type NavSection } from "./nav";

/** Numbered section heading — gives the single page a report's spine, and the anchor the
    sidebar navigates to. */
export function Section({
  id,
  title,
  subtitle,
  icon,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-4 border-b border-slate-200 pb-2.5">
        <h2 className="flex items-center gap-2.5 text-[22px] font-bold tracking-tight text-slate-900">
          {icon}
          {title}
        </h2>
        {subtitle && <p className="mt-1 text-[13px] text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

/** Separates the decision-ready half of the report from the supporting detail, and forces
    a page break when printed. */
export function PartDivider({ label, hint }: { label: string; hint: string }) {
  return (
    <div className="page-break flex items-center gap-4 pt-2">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ey-gold">{label}</p>
        <p className="text-[12px] text-slate-400">{hint}</p>
      </div>
      <div className="h-px flex-1 bg-slate-200" />
    </div>
  );
}

/** Big-number scorecard. The top row must land the story in five seconds. */
export function Kpi({
  label,
  value,
  unit,
  sub,
  delta,
  icon,
  strip,
  size = "lg",
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  /** Period-over-period change, e.g. "+1.8%". Green when up, rose when down. */
  delta?: string | null;
  icon?: React.ReactNode;
  /** Small distribution bar under the number — a sparkline stands in for a trend we do not
      have, so this shows the make-up of the figure instead of a history of it. */
  strip?: React.ReactNode;
  size?: "lg" | "sm";
  tone?: "neutral" | "good" | "bad";
}) {
  const valueTone = tone === "good" ? "text-emerald-600" : "text-slate-900";
  const up = delta?.startsWith("+");
  return (
    <div className="pdf-block flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_3px_rgba(15,23,42,0.04)]">
      {/* Reserved height for two lines: a label that wraps must not shove its own number
          out of line with the four cards beside it. */}
      <p className="flex min-h-[2.6em] items-start gap-1.5 text-[11px] font-bold uppercase leading-[1.3] tracking-[0.06em] text-slate-500">
        {icon && <span className="mt-px shrink-0">{icon}</span>}
        {label}
      </p>
      <p
        className={`font-bold leading-none tabular-nums ${valueTone} ${
          size === "lg" ? "text-[2.35rem]" : "text-2xl"
        }`}
        style={tone === "bad" ? { color: NEGATIVE_MARK } : undefined}
      >
        {value}
        {unit && <span className="ml-1 text-base font-semibold text-slate-400">{unit}</span>}
      </p>
      {strip && <div className="mt-4">{strip}</div>}
      {(delta || sub) && (
        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
          {delta && (
            <span
              className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${
                up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
              }`}
            >
              {up ? "▲" : "▼"} {delta.replace(/[+-]/, "")}
            </span>
          )}
          {sub && <span className="text-[11px] leading-snug text-slate-500">{sub}</span>}
        </div>
      )}
    </div>
  );
}

/** White panel used for every chart / table block. */
export function Panel({
  title,
  hint,
  accent,
  className = "",
  children,
}: {
  title?: string;
  hint?: string;
  accent?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`pdf-block rounded-xl border border-slate-200 bg-white p-6 ${className}`}
      style={accent ? { borderTop: `3px solid ${accent}` } : undefined}
    >
      {title && (
        <h3 className="text-[12px] font-bold uppercase tracking-wider text-slate-700">{title}</h3>
      )}
      {hint && <p className="mb-5 mt-1 text-[11px] text-slate-400">{hint}</p>}
      {!hint && title && <div className="mb-5" />}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Navigation                                                         */
/* ------------------------------------------------------------------ */

export function TableOfContents({ sections, active }: { sections: NavSection[]; active: string }) {
  return (
    /* Pinned for the whole document: `sticky` with an explicit height, so the list itself
       scrolls internally if it ever outgrows the viewport rather than the reader scrolling
       past it. Requires that no ancestor sets `overflow: hidden` — that would silently turn
       this back into a normal element. */
    <aside className="no-print sticky top-[76px] hidden h-[calc(100vh-76px)] w-56 shrink-0 self-start overflow-y-auto py-8 xl:block">
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">
        Contents
      </p>
      <nav>
        <ul className="border-l border-slate-200">
          {sections.map((s) => {
            const on = s.id === active;
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  aria-current={on ? "true" : undefined}
                  className={`-ml-px block border-l-2 py-2 pl-4 pr-2 text-[13.5px] leading-snug transition ${
                    on
                      ? "border-ey-gold font-semibold text-slate-900"
                      : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-900"
                  }`}
                >
                  {s.label}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Charts                                                             */
/* ------------------------------------------------------------------ */

export function StatusBadge({ status, count }: { status: string; count: number }) {
  const cls =
    status === "success"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-600/10"
      : status === "empty"
        ? "bg-amber-50 text-amber-800 ring-amber-600/10"
        : "bg-red-50 text-red-800 ring-red-600/10";
  const text = status === "success" ? `${count} reviews` : status === "empty" ? "No reviews" : "Failed";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ${cls}`}>
      {text}
    </span>
  );
}

/** Stacked positive / neutral / negative bar. */
export function SentimentBar({ pos, neu, neg }: { pos: number; neu: number; neg: number }) {
  return (
    <div className="flex h-2.5 w-full min-w-[90px] gap-[2px] overflow-hidden rounded-full bg-slate-100">
      <div style={{ width: `${pos}%`, background: POSITIVE_MARK }} />
      <div style={{ width: `${neu}%`, background: NEUTRAL_MARK }} />
      <div style={{ width: `${neg}%`, background: NEGATIVE_MARK }} />
    </div>
  );
}

/** Sentiment donut — the chart every social report is built around. */
export function Donut({
  pos,
  neu,
  neg,
  size = 104,
  centerValue,
  centerLabel,
}: {
  pos: number;
  neu: number;
  neg: number;
  size?: number;
  centerValue?: string;
  centerLabel?: string;
}) {
  const stroke = size >= 130 ? 14 : 11;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const segments = [
    { value: pos, color: POSITIVE_MARK },
    { value: neu, color: NEUTRAL_MARK },
    { value: neg, color: NEGATIVE_MARK },
  ];
  let offset = 0;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f1f5f9" strokeWidth={stroke} />
        {segments.map((s, i) => {
          const dash = (s.value / 100) * c;
          const el = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return el;
        })}
      </svg>
      {/* The ring already carries the colour; the figure inside stays in ink so the card
          isn't reading red twice. */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={`font-bold leading-none tabular-nums text-slate-900 ${
            size >= 130 ? "text-[1.75rem]" : "text-lg"
          }`}
        >
          {centerValue ?? `${Math.round(neg)}%`}
        </span>
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          {centerLabel ?? "negative"}
        </span>
      </div>
    </div>
  );
}

/** Generic multi-segment donut (share by category), used for the language mix. */
export function CategoryDonut({
  data,
  size = 140,
  centerValue,
  centerLabel,
}: {
  data: { label: string; value: number; color: string }[];
  size?: number;
  centerValue?: string;
  centerLabel?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f1f5f9" strokeWidth={stroke} />
        {data.map((d, i) => {
          const dash = (d.value / total) * c;
          const el = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={d.color}
              strokeWidth={stroke}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return el;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[1.6rem] font-bold leading-none tabular-nums text-slate-900">{centerValue ?? total}</span>
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">{centerLabel ?? "items"}</span>
      </div>
    </div>
  );
}

/** Reviews below this cannot support a percentage stated to one decimal. */
export const MIN_RELIABLE_SAMPLE = 10;

export function SmallSampleNote({ n }: { n: number }) {
  return (
    <p className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] leading-snug text-amber-700">
      Only {n} comment{n === 1 ? "" : "s"} — indicative, not statistically reliable.
    </p>
  );
}

export function LegendDot({ color, label, value }: { color: string; label: string; value?: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] text-slate-600">
      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} />
      {label}
      {value && <span className="ml-auto pl-3 font-semibold tabular-nums text-slate-800">{value}</span>}
    </span>
  );
}
