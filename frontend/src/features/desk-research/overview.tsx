/**
 * The desk-research executive overview, laid out rather than read.
 *
 * The backend now returns this as structured data instead of one markdown blob, so the parts a
 * consultant scans for — the counts, the problems, what to do — can be given their own shape
 * instead of being sentences to hunt through.
 *
 * Every number here was computed in Python from the CX findings; nothing on this page is a figure
 * a model chose to repeat.
 *
 * Grouped by the CX capability framework (Manage / Analyze / Improve), which is what cx_findings
 * carries. The issue log's Excel export groups by strategic dimension instead -- where in the
 * business a problem sits, rather than which CX capability it is evidence about -- so the two
 * will not line up, by design.
 *
 * Sessions generated before this shipped have no `overview` and fall back to the markdown
 * renderer, which is why the hub keeps both paths.
 */

import React from "react";

import { MarkdownRenderer } from "./markdown";

/* ------------------------------------------------------------------ types */

export type OverviewKpi = { label: string; value: string | number; tone?: string };
export type OverviewFinding = {
  axis?: string;
  capability?: string;
  type?: string;
  severity?: string | null;
  title?: string;
  description?: string;
  evidence?: string;
  source_document?: string;
};
export type OverviewDocument = {
  name?: string;
  what_it_is?: string;
  period?: string;
  key_point?: string;
};
export type OverviewTakeaway = { point?: string; source?: string | null };
export type OverviewRecommendation = {
  action?: string;
  why?: string;
  capability?: string;
  source?: string | null;
};
export type OverviewCoverage = {
  axis: string;
  findings: number;
  problems: number;
  capabilities: string[];
};

export type ReportOverview = {
  headline?: string;
  period?: string | null;
  kpis?: OverviewKpi[];
  takeaways?: OverviewTakeaway[];
  documents?: OverviewDocument[];
  connections?: string[];
  problems?: OverviewFinding[];
  strengths?: OverviewFinding[];
  /** Absent on sessions generated before opportunities were split out of strengths. */
  opportunities?: OverviewFinding[];
  coverage?: OverviewCoverage[];
  recommendations?: OverviewRecommendation[];
};

/* ------------------------------------------------------------------ pieces */

const SEVERITY_STYLE: Record<string, string> = {
  critical: "bg-rose-50 text-rose-700 ring-rose-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-slate-50 text-slate-600 ring-slate-200",
};

const TONE_VALUE: Record<string, string> = {
  bad: "text-rose-600",
  warn: "text-amber-600",
  good: "text-emerald-600",
  neutral: "text-slate-900",
};

function SeverityBadge({ severity }: { severity?: string | null }) {
  if (!severity) return null;
  const key = severity.toLowerCase();
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
        SEVERITY_STYLE[key] ?? SEVERITY_STYLE.low
      }`}
    >
      {severity}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="pdf-block">
      <h2 className="mb-3 text-base font-bold tracking-tight text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ view */

export function ReportOverviewView({
  overview,
  markdown,
}: {
  overview: ReportOverview | null | undefined;
  /** Rendered instead when a session predates the structured overview. */
  markdown?: string | null;
}) {
  if (!overview) {
    return markdown ? <MarkdownRenderer content={markdown} /> : null;
  }

  const {
    headline, period, kpis = [], takeaways = [], documents = [],
    connections = [], problems = [], strengths = [], opportunities = [],
    coverage = [], recommendations = [],
  } = overview;

  return (
    <div className="flex flex-col gap-8">
      {/* headline ------------------------------------------------------ */}
      {(headline || period) && (
        <header className="pdf-block">
          {period && (
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {period}
            </p>
          )}
          {headline && (
            <p className="text-lg font-semibold leading-snug text-slate-900">{headline}</p>
          )}
        </header>
      )}

      {/* the counts, all computed ---------------------------------------- */}
      {kpis.length > 0 && (
        <div className="pdf-block grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {kpis.map((k) => (
            <div
              key={k.label}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div
                className={`text-2xl font-bold tabular-nums ${TONE_VALUE[k.tone ?? "neutral"] ?? TONE_VALUE.neutral}`}
              >
                {k.value}
              </div>
              <div className="mt-1 text-xs font-medium leading-tight text-slate-500">
                {k.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {takeaways.length > 0 && (
        <Section title="What this set shows">
          <ul className="flex flex-col gap-2">
            {takeaways.map((t, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-700">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ey-gold" />
                <span>
                  {t.point}
                  {t.source && (
                    <span className="ml-1.5 text-xs text-slate-500">{t.source}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {problems.length > 0 && (
        <Section title="Problems found">
          <div className="flex flex-col gap-2.5">
            {problems.map((p, i) => (
              <article
                key={i}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {p.title || p.description}
                  </h3>
                  <SeverityBadge severity={p.severity} />
                </div>
                {p.title && p.description && (
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{p.description}</p>
                )}
                {p.evidence && (
                  <p className="mt-2 border-l-2 border-slate-200 pl-3 text-xs italic leading-relaxed text-slate-500">
                    {p.evidence}
                  </p>
                )}
                <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                  {p.capability && (
                    <span className="font-medium text-slate-600">{p.capability}</span>
                  )}
                  {p.axis && <span>{p.axis}</span>}
                  {p.source_document && <span className="truncate">{p.source_document}</span>}
                </div>
              </article>
            ))}
          </div>
        </Section>
      )}

      {recommendations.length > 0 && (
        <Section title="What to do next">
          <ol className="flex flex-col gap-2.5">
            {recommendations.map((r, i) => (
              <li
                key={i}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ey-navy text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900">{r.action}</p>
                    {r.why && (
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">{r.why}</p>
                    )}
                    {(r.capability || r.source) && (
                      <p className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-slate-500">
                        {r.capability && <span className="font-medium">{r.capability}</span>}
                        {r.source && <span>{r.source}</span>}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {strengths.length > 0 && (
        <Section title="What is working">
          <ul className="flex flex-col gap-2">
            {strengths.map((s, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-700">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                <span>
                  {s.title && <span className="font-semibold text-slate-900">{s.title} — </span>}
                  {s.description}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {opportunities.length > 0 && (
        <Section title="Opportunities">
          <ul className="flex flex-col gap-2">
            {opportunities.map((o, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-700">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                <span>
                  {o.title && <span className="font-semibold text-slate-900">{o.title} — </span>}
                  {o.description}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {coverage.some((c) => c.findings > 0) && (
        <Section title="Coverage across the CX framework">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {coverage.map((c) => (
              <div
                key={c.axis}
                className={`rounded-2xl border p-4 shadow-sm ${
                  c.findings === 0
                    ? "border-dashed border-slate-300 bg-slate-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <h3 className="text-sm font-bold text-slate-900">{c.axis}</h3>
                  <span className="text-lg font-bold tabular-nums text-slate-900">
                    {c.findings}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  {c.findings === 0
                    ? "nothing in these documents"
                    : `${c.problems} problem${c.problems === 1 ? "" : "s"}`}
                </p>
                {c.capabilities.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {c.capabilities.map((cap) => (
                      <span
                        key={cap}
                        className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {documents.length > 0 && (
        <Section title="What each document contains">
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full min-w-[540px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Document</th>
                  <th className="px-4 py-2.5 font-semibold">What it is</th>
                  <th className="px-4 py-2.5 font-semibold">Period</th>
                  <th className="px-4 py-2.5 font-semibold">What it tells you</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((d, i) => (
                  <tr key={i} className="align-top">
                    <td className="px-4 py-2.5 font-medium text-slate-900">{d.name}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.what_it_is}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-slate-500">{d.period}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.key_point}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {connections.length > 0 && (
        <Section title="How they connect">
          <ul className="flex flex-col gap-2">
            {connections.map((c, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-700">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
