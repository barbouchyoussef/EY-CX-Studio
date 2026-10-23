/**
 * The project's consolidated interview report, laid out rather than read.
 *
 * Mirrors the desk-research overview deliberately: same structured-object contract, same
 * "the model writes prose, Python computes figures" split, so a consultant who has read one
 * report already knows how to read this one.
 *
 * The section order is the reading order, not the generation order. Contradictions come near the
 * top because they are what a consultant opens this for — where the interviews disagree with the
 * client's own self-assessment is the one thing neither source shows alone.
 */

import React from "react";

export type ReportKpi = { label: string; value: string | number; tone?: string };
export type ReportTheme = {
  theme?: string;
  detail?: string;
  heard_from?: string;
  quote?: string;
};
export type ReportContradiction = {
  between?: string;
  claimed?: string;
  heard?: string;
  so_what?: string;
};
export type ReportIssue = {
  title?: string;
  description?: string;
  evidence?: string;
  severity?: string | null;
  dimension?: string;
  interview_id?: number;
  interview_profile?: string;
};
export type ReportCoverage = {
  interview_id: number;
  profile: string;
  answered: number;
  total: number;
  findings: number;
  has_insights?: boolean;
  assessment_id?: number | null;
};
export type ReportMaturity = {
  axis: string;
  capability: string;
  level: number | null;
  level_label?: string | null;
};
export type ReportRecommendation = { action?: string; why?: string; source?: string };

export type InterviewProjectReport = {
  company?: string;
  headline?: string;
  kpis?: ReportKpi[];
  cx_culture?: { verdict?: string; evidence?: string[] };
  themes?: ReportTheme[];
  contradictions?: ReportContradiction[];
  issues?: ReportIssue[];
  coverage?: ReportCoverage[];
  maturity?: ReportMaturity[];
  recommendations?: ReportRecommendation[];
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

/** Level 1 of 5 is ad hoc, 5 is optimised — so the bar is a claim, and it reads worst-first. */
const LEVEL_MAX = 5;

function SeverityBadge({ severity }: { severity?: string | null }) {
  if (!severity) return null;
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
        SEVERITY_STYLE[severity.toLowerCase()] ?? SEVERITY_STYLE.low
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

export default function InterviewProjectReportView({
  report,
}: {
  report: InterviewProjectReport | null | undefined;
}) {
  if (!report) return null;

  const {
    company, headline, kpis = [], cx_culture, themes = [], contradictions = [],
    issues = [], coverage = [], maturity = [], recommendations = [],
  } = report;

  return (
    <div className="flex flex-col gap-8">
      {/* headline ------------------------------------------------------ */}
      {(company || headline) && (
        <header className="pdf-block">
          {company && (
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {company}
            </p>
          )}
          {headline && (
            <p className="text-lg font-semibold leading-snug text-slate-900">{headline}</p>
          )}
        </header>
      )}

      {kpis.length > 0 && (
        <div className="pdf-block grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {kpis.map((k) => (
            <div key={k.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div
                className={`text-2xl font-bold tabular-nums ${
                  TONE_VALUE[k.tone ?? "neutral"] ?? TONE_VALUE.neutral
                }`}
              >
                {k.value}
              </div>
              <div className="mt-1 text-xs font-medium leading-tight text-slate-500">{k.label}</div>
            </div>
          ))}
        </div>
      )}

      {(cx_culture?.verdict || (cx_culture?.evidence?.length ?? 0) > 0) && (
        <Section title="How customer experience actually works here">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            {cx_culture?.verdict && (
              <p className="text-sm leading-relaxed text-slate-700">{cx_culture.verdict}</p>
            )}
            {(cx_culture?.evidence?.length ?? 0) > 0 && (
              <ul className="mt-4 flex flex-col gap-2.5 border-t border-slate-100 pt-4">
                {cx_culture!.evidence!.map((e, i) => (
                  <li
                    key={i}
                    className="border-l-2 border-ey-gold pl-3 text-sm italic leading-relaxed text-slate-600"
                  >
                    {e}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Section>
      )}

      {/* the reason this report exists ---------------------------------- */}
      {contradictions.length > 0 && (
        <Section title="Where the accounts disagree">
          <div className="flex flex-col gap-3">
            {contradictions.map((c, i) => (
              <article
                key={i}
                className="rounded-2xl border border-rose-200 bg-rose-50/40 p-4 shadow-sm"
              >
                {c.between && (
                  <h3 className="text-sm font-bold text-slate-900">{c.between}</h3>
                )}
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Claimed
                    </p>
                    <p className="text-sm leading-relaxed text-slate-600">{c.claimed}</p>
                  </div>
                  <div className="rounded-xl border border-rose-200 bg-white p-3">
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-rose-500">
                      The interview said
                    </p>
                    <p className="text-sm leading-relaxed text-slate-700">{c.heard}</p>
                  </div>
                </div>
                {c.so_what && (
                  <p className="mt-3 text-sm font-medium leading-relaxed text-slate-700">
                    {c.so_what}
                  </p>
                )}
              </article>
            ))}
          </div>
        </Section>
      )}

      {themes.length > 0 && (
        <Section title="What came up across the interviews">
          <div className="flex flex-col gap-2.5">
            {themes.map((t, i) => (
              <article
                key={i}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <h3 className="text-sm font-semibold text-slate-900">{t.theme}</h3>
                {t.detail && (
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{t.detail}</p>
                )}
                {t.quote && (
                  <p className="mt-2.5 border-l-2 border-ey-gold pl-3 text-sm italic leading-relaxed text-slate-600">
                    “{t.quote}”
                  </p>
                )}
                {t.heard_from && (
                  <p className="mt-2.5 text-[11px] font-medium text-slate-500">{t.heard_from}</p>
                )}
              </article>
            ))}
          </div>
        </Section>
      )}

      {recommendations.length > 0 && (
        <Section title="What to do next">
          <ol className="flex flex-col gap-2.5">
            {recommendations.map((r, i) => (
              <li key={i} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ey-navy text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900">{r.action}</p>
                    {r.why && (
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">{r.why}</p>
                    )}
                    {r.source && (
                      <p className="mt-1.5 text-[11px] text-slate-500">{r.source}</p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {issues.length > 0 && (
        <Section title={`Issues raised (${issues.length})`}>
          <div className="flex flex-col gap-2">
            {issues.map((it, i) => (
              <article
                key={i}
                className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {it.title || it.description}
                  </h3>
                  <SeverityBadge severity={it.severity} />
                </div>
                {it.title && it.description && (
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">{it.description}</p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                  {it.dimension && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      {it.dimension}
                    </span>
                  )}
                  {it.interview_id != null && <span>Interview {it.interview_id}</span>}
                </div>
              </article>
            ))}
          </div>
        </Section>
      )}

      {maturity.length > 0 && (
        <Section title="What the client scored themselves">
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Axis</th>
                  <th className="px-4 py-2.5 font-semibold">Capability</th>
                  <th className="px-4 py-2.5 font-semibold">Self-assessed level</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {maturity.map((m, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2.5 text-slate-500">{m.axis}</td>
                    <td className="px-4 py-2.5 font-medium text-slate-800">{m.capability}</td>
                    <td className="px-4 py-2.5">
                      {m.level == null ? (
                        <span className="text-slate-400">not scored</span>
                      ) : (
                        <span className="flex items-center gap-2">
                          <span className="flex gap-0.5">
                            {Array.from({ length: LEVEL_MAX }, (_, n) => (
                              <span
                                key={n}
                                className={`h-1.5 w-4 rounded-full ${
                                  n < m.level! ? "bg-ey-navy" : "bg-slate-200"
                                }`}
                              />
                            ))}
                          </span>
                          <span className="tabular-nums text-slate-600">{m.level}</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {coverage.length > 0 && (
        <Section title="Who was interviewed">
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Interview</th>
                  <th className="px-4 py-2.5 font-semibold">Stated role</th>
                  <th className="px-4 py-2.5 font-semibold">Answered</th>
                  <th className="px-4 py-2.5 font-semibold">Issues</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {coverage.map((c) => (
                  <tr key={c.interview_id}>
                    <td className="px-4 py-2.5 tabular-nums text-slate-500">#{c.interview_id}</td>
                    <td className="px-4 py-2.5 font-medium text-slate-800">{c.profile}</td>
                    <td className="px-4 py-2.5 tabular-nums text-slate-600">
                      {c.answered} of {c.total}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums text-slate-600">{c.findings}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}
