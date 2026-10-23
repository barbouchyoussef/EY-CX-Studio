import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  AlertTriangle,
  BarChart3,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Frown,
  Globe,
  Lightbulb,
  MessageSquare,
  Pencil,
  Reply,
  Star,
  ThumbsUp,
  TrendingUp,
  Users,
} from "lucide-react";
import type {
  ChannelReportSection,
  PlatformResult,
  PlatformSentiment,
  ScrapedReview,
  ScrapingResponse,
  ThemeVerbatim,
} from "../../types/scraping";
import { sourceLabel } from "../../types/scraping";
import type { ChannelAnalysis } from "../../types/manual-analysis";
import { compact, formatPercent, looksLikeStat, parseCount, parseDelta, postTotal } from "./format";
import {
  NEGATIVE_MARK, NEUTRAL_MARK, POSITIVE_MARK,
  buildChannelColors,
} from "./colors";
import {
  CategoryDonut, Donut, Kpi, LegendDot, Panel, PartDivider, Section, SentimentBar,
  MIN_RELIABLE_SAMPLE, SmallSampleNote, StatusBadge, TableOfContents,
} from "./primitives";
import {
  ChannelVolumeChart, ComplaintChart, ComplaintDonut, MomentumChart, RatingHistogram,
  RatingSentimentNote, SentimentMixArea, TopicChart, TrendChart,
} from "./charts";
import { useActiveSection, type NavSection } from "./nav";
import { LANG_COLORS, LANG_ORDER, detectLanguage, type LangBucket } from "./language";
import ModuleChat, { type ModuleChatMessage } from "../../components/ui/module-chat";
import ShareButton from "../../components/ui/share-button";
import AddToProjectButton from "../../components/ui/add-to-project-button";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/** Below this, a review is a rating with a word attached and adds nothing to read. */
const MIN_FEEDBACK_CHARS = 10;
/** How much of two texts must agree before one is treated as a quote of the other. */
const DUPLICATE_PREFIX_CHARS = 40;

function ChannelSentimentCard({ row, accent }: { row: PlatformSentiment; accent?: string }) {
  return (
    <div
      className="pdf-block rounded-xl border border-slate-200 bg-white p-5"
      style={accent ? { borderTop: `3px solid ${accent}` } : undefined}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h4 className="text-[15px] font-bold text-slate-900">{row.platform}</h4>
          {row.summary_stat && <p className="mt-0.5 text-[11px] text-slate-500">{row.summary_stat}</p>}
        </div>
        <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-slate-600">
          {row.classified_count} analysed
        </span>
      </div>

      <div className="flex items-center gap-5">
        <Donut pos={row.positive_pct} neu={row.neutral_pct} neg={row.negative_pct} />
        <dl className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-[12px] text-slate-500">Positive</dt>
            <dd className="text-[13px] font-semibold tabular-nums text-emerald-600">{row.positive_pct}%</dd>
          </div>
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-[12px] text-slate-500">Neutral</dt>
            <dd className="text-[13px] font-semibold tabular-nums text-slate-500">{row.neutral_pct}%</dd>
          </div>
          <div className="flex items-baseline justify-between gap-2 border-b border-slate-100 pb-1.5">
            <dt className="text-[12px] text-slate-500">Negative</dt>
            <dd className="text-[13px] font-semibold tabular-nums text-rose-600">{row.negative_pct}%</dd>
          </div>
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-[12px] text-slate-500">Avg rating</dt>
            <dd className="text-[13px] font-bold tabular-nums text-slate-800">
              {row.avg_rating != null ? `${row.avg_rating.toFixed(1)}/5` : "—"}
            </dd>
          </div>
          {row.reply_rate_pct != null && (
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-[12px] text-slate-500">Brand replies</dt>
              <dd
                className={`text-[13px] font-bold tabular-nums ${
                  row.reply_rate_pct < 10 ? "text-rose-600" : "text-slate-800"
                }`}
              >
                {row.reply_rate_pct}%
              </dd>
            </div>
          )}
        </dl>
      </div>

      {row.classified_count < MIN_RELIABLE_SAMPLE && <SmallSampleNote n={row.classified_count} />}
    </div>
  );
}

function ScrapedChannelTable({ rows }: { rows: PlatformSentiment[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
            <th className="pb-2 pr-4 font-semibold">Channel</th>
            <th className="w-24 pb-2 pr-4 text-right font-semibold">Analysed</th>
            <th className="w-20 pb-2 pr-6 text-right font-semibold">Avg</th>
            <th className="w-[38%] pb-2 font-semibold">Sentiment</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.platform} className="border-b border-slate-50 last:border-0">
              <td className="py-2.5 pr-4">
                <span className="text-[13px] font-semibold text-slate-800">{row.platform}</span>
                {row.summary_stat && <div className="text-[11px] text-slate-400">{row.summary_stat}</div>}
              </td>
              <td className="py-3 pr-4 text-right text-[13px] tabular-nums text-slate-600">
                {row.classified_count}
              </td>
              <td className="py-3 pr-6 text-right text-[13px] font-semibold tabular-nums text-slate-700">
                {row.avg_rating != null ? row.avg_rating.toFixed(1) : "—"}
              </td>
              <td className="py-2.5">
                <SentimentBar pos={row.positive_pct} neu={row.neutral_pct} neg={row.negative_pct} />
                <div className="mt-1 text-[11px] tabular-nums text-slate-400">
                  {row.positive_pct}% pos ·{" "}
                  <span className="font-semibold text-rose-600">{row.negative_pct}% neg</span>
                  {row.classified_count < MIN_RELIABLE_SAMPLE && (
                    <span className="ml-1.5 text-amber-600">· small sample</span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The provenance line under a quote. When the original review is linkable it becomes the
    link, so a client can open the source rather than take the quote on trust. */
function VerbatimMeta({ v }: { v: ThemeVerbatim }) {
  const src = sourceLabelOf(v.source);
  const date = fmtDate(v.date);
  const meta = (
    <>
      {v.platform}
      {src && ` · ${src}`}
      {v.rating != null && ` · ${v.rating}/5`}
      {date && ` · ${date}`}
    </>
  );
  if (!v.url) return <p className="mt-1 text-[11px] text-slate-400">{meta}</p>;
  return (
    <a
      href={v.url}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-1 inline-flex items-center gap-1 text-[11px] text-slate-400 transition hover:text-[#8a6d2f] hover:underline"
    >
      {meta}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}

function VerbatimGroups({ verbatims }: { verbatims: ThemeVerbatim[] }) {
  const groups = new Map<string, ThemeVerbatim[]>();
  for (const v of verbatims) {
    const bucket = groups.get(v.label);
    if (bucket) bucket.push(v);
    else groups.set(v.label, [v]);
  }
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {Array.from(groups.entries()).map(([label, items]) => (
        <div key={label} className="pdf-block">
          <h4 className="mb-2.5 text-[12px] font-bold uppercase tracking-wider text-slate-700">{label}</h4>
          <div className="space-y-2.5">
            {items.map((v, i) => (
              <blockquote
                key={i}
                className="pdf-block rounded-xl border border-slate-200 bg-white p-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:shadow-[0_6px_18px_rgba(15,23,42,0.07)]"
              >
                <div className="flex items-start gap-2.5">
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: sentimentDot(v.sentiment) }}
                  />
                  <p dir="auto" className="text-[13px] leading-relaxed text-slate-700">
                    {v.text}
                  </p>
                </div>
                <div className="mt-2 pl-5">
                  <VerbatimMeta v={v} />
                </div>
              </blockquote>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Reduce a review date to a period key at the chosen granularity ("2026-07" or "2026").
 *  Handles common formats (ISO, YYYY/MM, bare year) and falls back to Date parsing. */
function periodKeyOf(date: string | null | undefined, gran: "month" | "year"): string | null {
  if (!date) return null;
  const s = String(date);
  let m = s.match(/(\d{4})[-/.](\d{1,2})/);
  if (m) {
    const key = `${m[1]}-${m[2].padStart(2, "0")}`;
    return gran === "year" ? m[1] : key;
  }
  m = s.match(/\b(\d{4})\b/);
  if (m) return gran === "year" ? m[1] : null;
  const d = new Date(s);
  if (isNaN(d.getTime())) return null;
  return gran === "year"
    ? String(d.getFullYear())
    : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const _MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function periodLabel(key: string): string {
  if (/^\d{4}$/.test(key)) return key;
  const [y, mo] = key.split("-");
  return `${_MONTH_NAMES[parseInt(mo, 10) - 1] ?? mo} ${y}`;
}

const sourceLabelOf = (s?: string | null) =>
  s === "page" ? "Official page" : s === "keyword" ? "Keyword search" : null;

/** Format a date, or return null if it can't be parsed — so we never render "Invalid Date". */
function fmtDate(s?: string | null): string | null {
  if (!s) return null;
  const d = new Date(s);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Dot colour for a sentiment. */
const sentimentDot = (s?: string | null) =>
  s === "negative" ? "#d03b3b" : s === "positive" ? "#1f9d6b" : "#94a3b8";

/** Interactive per-channel sentiment & feedbacks component.
 * Allows viewing each channel's sentiment stats, AI summary, strengths, friction points,
 * and direct customer feedbacks via dedicated channel tabs. */
/** One piece of customer feedback, from whichever source it reached us. */
type Feedback = {
  text: string;
  sentiment: "positive" | "neutral" | "negative";
  rating?: number | null;
  date?: string | null;
  platform: string;
  label?: string;
  url?: string | null;
  author?: string | null;
  source?: string | null;
};

/** A verbatim the report already classified. */
function feedbackFromVerbatim(v: ThemeVerbatim): Feedback {
  return {
    text: v.text,
    sentiment: (v.sentiment as Feedback["sentiment"]) || "neutral",
    rating: v.rating,
    date: v.date,
    platform: v.platform,
    label: v.label,
    url: v.url,
    source: v.source,
  };
}

/** A raw scraped review, which may never have reached the classifier.
 *
 *  When it did not, the star rating stands in: 1-2 reads as negative, 4-5 as positive, and 3 is
 *  left neutral rather than guessed at. Coarser than the model, but showing an unclassified
 *  review as "neutral" would put genuine one-star complaints in the calm bucket. */
function feedbackFromReview(r: ScrapedReview): Feedback {
  let sentiment: Feedback["sentiment"] = "neutral";
  if (r.classification?.sentiment) {
    sentiment = r.classification.sentiment;
  } else if (r.rating != null) {
    if (r.rating <= 2) sentiment = "negative";
    else if (r.rating >= 4) sentiment = "positive";
  }
  return {
    text: r.text,
    sentiment,
    rating: r.rating,
    date: r.date,
    platform: r.platform,
    author: r.author,
    url: r.url,
    label: r.classification?.complaint_category || r.classification?.themes?.[0],
    source: r.source,
  };
}

function ChannelSentimentTabbedView({
  rows,
  colors,
  verbatims = [],
  scrapedPlatforms = [],
  channelBreakdown = [],
}: {
  rows: PlatformSentiment[];
  colors: Record<string, string>;
  verbatims?: ThemeVerbatim[];
  scrapedPlatforms?: PlatformResult[];
  channelBreakdown?: ChannelReportSection[];
}) {
  const [activeTab, setActiveTab] = useState<string>("all");
  const [sentimentFilter, setSentimentFilter] = useState<"all" | "negative" | "neutral" | "positive">("all");
  // Facebook-only: filter by where the comment came from (official page vs keyword search).
  const [sourceFilter, setSourceFilter] = useState<"all" | "page" | "keyword">("all");
  // Period filter (applies to any channel with dated feedback).
  const [periodGranularity, setPeriodGranularity] = useState<"month" | "year">("month");
  const [periodFilter, setPeriodFilter] = useState<string>("all");

  const isFacebook = activeTab.toLowerCase() === "facebook";
  const resetFilters = () => {
    setSentimentFilter("all");
    setSourceFilter("all");
    setPeriodFilter("all");
  };

  const activeRow = useMemo(
    () => (activeTab === "all" ? null : rows.find((r) => r.platform === activeTab)),
    [activeTab, rows]
  );

  const activeBreakdown = useMemo(
    () =>
      activeTab === "all"
        ? null
        : channelBreakdown.find((b) => b.channel.toLowerCase() === activeTab.toLowerCase()),
    [activeTab, channelBreakdown]
  );

  // Feedbacks with sentiment + source filters applied (but NOT the period filter, so the period
  // options can be derived from what's actually present).
  const baseFeedbacks = useMemo(() => {
    let items: Feedback[] = [];

    // "All channels" shows the verbatims the report selected. A single channel additionally
    // shows the raw reviews behind them, so the consultant can read past the chosen quotes.
    if (activeTab === "all") {
      items = verbatims.map(feedbackFromVerbatim);
    } else {
      items = verbatims
        .filter((v) => v.platform.toLowerCase() === activeTab.toLowerCase())
        .map(feedbackFromVerbatim);

      const scraped = scrapedPlatforms.find(
        (p) => p.platform.toLowerCase() === activeTab.toLowerCase()
      );
      for (const review of scraped?.reviews ?? []) {
        // A verbatim is an edited quote of a review, so the two rarely match character for
        // character; comparing openings catches the duplicate without demanding they be equal.
        if (!review.text || review.text.trim().length < MIN_FEEDBACK_CHARS) continue;
        const opening = review.text.slice(0, DUPLICATE_PREFIX_CHARS);
        if (items.some((existing) => existing.text.slice(0, DUPLICATE_PREFIX_CHARS) === opening)) continue;
        items.push(feedbackFromReview(review));
      }
    }

    if (sentimentFilter !== "all") {
      items = items.filter((i) => i.sentiment === sentimentFilter);
    }
    // Source filter only applies to Facebook (the only platform tagged page/keyword).
    if (isFacebook && sourceFilter !== "all") {
      items = items.filter((i) => i.source === sourceFilter);
    }

    return items;
  }, [activeTab, verbatims, scrapedPlatforms, sentimentFilter, sourceFilter, isFacebook]);

  // Distinct periods present (at the chosen granularity), newest first.
  const availablePeriods = useMemo(() => {
    const keys = new Set<string>();
    for (const f of baseFeedbacks) {
      const k = periodKeyOf(f.date, periodGranularity);
      if (k) keys.add(k);
    }
    return [...keys].sort().reverse();
  }, [baseFeedbacks, periodGranularity]);

  const channelFeedbacks = useMemo(() => {
    if (periodFilter === "all") return baseFeedbacks;
    return baseFeedbacks.filter((f) => periodKeyOf(f.date, periodGranularity) === periodFilter);
  }, [baseFeedbacks, periodFilter, periodGranularity]);

  return (
    <div className="space-y-6">
      {/* ── Channel Tab Selector ── */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => {
            setActiveTab("all");
            resetFilters();
          }}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${
            activeTab === "all"
              ? "bg-ink text-white shadow-sm"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          <span>All Channels</span>
          <span className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-extrabold">
            {rows.length}
          </span>
        </button>

        {rows.map((row) => {
          const isActive = activeTab === row.platform;
          const hue = colors[row.platform] ?? "#64748b";
          return (
            <button
              key={row.platform}
              onClick={() => {
                setActiveTab(row.platform);
                resetFilters();
              }}
              className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${
                isActive
                  ? "bg-ink text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: hue }} />
              <span>{row.platform}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold ${
                  isActive ? "bg-white/20 text-white" : "bg-slate-200 text-slate-700"
                }`}
              >
                {row.classified_count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Filters for the selected channel (sit right under the channel tabs) ── */}
      {activeTab !== "all" && activeRow && (
        <div className="-mt-2 mb-6 flex flex-col gap-2.5 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 w-16 text-[11px] font-bold uppercase tracking-wide text-slate-400">Sentiment</span>
            {(["all", "negative", "neutral", "positive"] as const).map((st) => (
              <button
                key={st}
                onClick={() => setSentimentFilter(st)}
                className={`rounded-full px-3 py-1 text-xs font-bold capitalize transition ${
                  sentimentFilter === st
                    ? st === "negative"
                      ? "bg-rose-600 text-white"
                      : st === "positive"
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-800 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {isFacebook && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 w-16 text-[11px] font-bold uppercase tracking-wide text-slate-400">Source</span>
              {([
                { key: "all", label: "All" },
                { key: "page", label: "Official page" },
                { key: "keyword", label: "Keyword search" },
              ] as const).map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setSourceFilter(opt.key)}
                  className={`rounded-full px-3 py-1 text-xs font-bold transition ${
                    sourceFilter === opt.key ? "bg-[#1877F2] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {availablePeriods.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 w-16 text-[11px] font-bold uppercase tracking-wide text-slate-400">Period</span>
              <div className="flex overflow-hidden rounded-full border border-slate-200">
                {(["month", "year"] as const).map((g) => (
                  <button
                    key={g}
                    onClick={() => {
                      setPeriodGranularity(g);
                      setPeriodFilter("all");
                    }}
                    className={`px-3 py-1 text-xs font-bold capitalize transition ${
                      periodGranularity === g ? "bg-slate-800 text-white" : "bg-white text-slate-500 hover:bg-slate-100"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <select
                value={periodFilter}
                onChange={(e) => setPeriodFilter(e.target.value)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 outline-none focus:border-ey-gold"
              >
                <option value="all">All {periodGranularity === "month" ? "months" : "years"}</option>
                {availablePeriods.map((p) => (
                  <option key={p} value={p}>
                    {periodLabel(p)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* ── Tab Content: All Channels Overview ── */}
      {activeTab === "all" && (
        <div className="space-y-6">
          {rows.length <= 3 ? (
            <div className={`grid gap-4 ${rows.length > 1 ? "sm:grid-cols-2" : ""}`}>
              {rows.map((row) => (
                <ChannelSentimentCard key={row.platform} row={row} accent={colors[row.platform]} />
              ))}
            </div>
          ) : (
            <Panel>
              <ScrapedChannelTable rows={rows} />
            </Panel>
          )}

          {verbatims.length > 0 && (
            <Panel
              title="Consolidated Customer Feedbacks Across Channels"
              hint="Top extracts supporting sentiment breakdown"
            >
              <VerbatimGroups verbatims={verbatims} />
            </Panel>
          )}
        </div>
      )}

      {/* ── Tab Content: Specific Channel View ── */}
      {activeTab !== "all" && activeRow && (
        <div className="space-y-6">
          {/* Header Card / Scorecard for the specific channel */}
          <div
            className="pdf-block rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            style={{ borderTop: `4px solid ${colors[activeRow.platform] ?? "#2a78d6"}` }}
          >
            <div className="mb-5 flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <span
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: colors[activeRow.platform] ?? "#2a78d6" }}
                  />
                  <h3 className="text-xl font-bold text-slate-900">{activeRow.platform}</h3>
                </div>
                {activeRow.summary_stat && (
                  <p className="mt-1 text-xs text-slate-500">{activeRow.summary_stat}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {activeRow.classified_count} Analysed Reviews
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {activeRow.review_count} Total Collected
                </span>
              </div>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {/* Donut Chart */}
              <div className="flex items-center gap-4 rounded-xl bg-slate-50 p-4">
                <Donut
                  pos={activeRow.positive_pct}
                  neu={activeRow.neutral_pct}
                  neg={activeRow.negative_pct}
                />
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Sentiment Split
                  </p>
                  <p className="text-xs font-semibold text-emerald-600">
                    {activeRow.positive_pct}% Pos
                  </p>
                  <p className="text-xs font-semibold text-slate-500">
                    {activeRow.neutral_pct}% Neu
                  </p>
                  <p className="text-xs font-semibold text-rose-600">
                    {activeRow.negative_pct}% Neg
                  </p>
                </div>
              </div>

              {/* Avg Rating */}
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Avg Score / Rating
                </p>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold text-slate-900">
                    {activeRow.avg_rating != null ? activeRow.avg_rating.toFixed(1) : "—"}
                  </span>
                  <span className="text-xs text-slate-400">/ 5</span>
                </div>
                <div className="mt-1.5 flex items-center text-amber-500">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                      key={star}
                      className={`h-3.5 w-3.5 ${
                        (activeRow.avg_rating ?? 0) >= star
                          ? "fill-amber-400 text-amber-400"
                          : "text-slate-200"
                      }`}
                    />
                  ))}
                </div>
              </div>

              {/* Brand Reply Rate */}
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Brand Reply Rate
                </p>
                <p
                  className={`mt-1 text-2xl font-extrabold ${
                    activeRow.reply_rate_pct != null && activeRow.reply_rate_pct < 10
                      ? "text-rose-600"
                      : "text-slate-900"
                  }`}
                >
                  {activeRow.reply_rate_pct != null ? `${activeRow.reply_rate_pct}%` : "N/A"}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">Public responses to feedback</p>
              </div>

              {/* Negative Share */}
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Negative Share
                </p>
                <p
                  className="mt-1 text-2xl font-extrabold tabular-nums"
                  style={{ color: NEGATIVE_MARK }}
                >
                  {activeRow.negative_pct}%
                </p>
                <p className="mt-1 text-[11px] text-slate-400">Critical complaints ratio</p>
              </div>
            </div>
          </div>

          {/* AI Channel Breakdown (Summary, Strengths, Friction Points) */}
          {activeBreakdown && (
            <Panel
              title={`${activeRow.platform} AI Analysis & Diagnostic`}
              hint="Extracted channel summary and observations"
            >
              <div className="space-y-4">
                {activeBreakdown.summary && (
                  <p className="text-sm leading-relaxed text-slate-700">
                    {activeBreakdown.summary}
                  </p>
                )}

                {activeBreakdown.strengths && activeBreakdown.strengths.length > 0 && (
                  <div>
                    <h5 className="mb-2 text-xs font-bold uppercase tracking-wider text-emerald-700">
                      Channel Strengths
                    </h5>
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      {activeBreakdown.strengths.map((str: string, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 transition hover:border-emerald-200 hover:bg-emerald-50"
                        >
                          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
                            <ThumbsUp className="h-4 w-4" />
                          </span>
                          <p dir="auto" className="text-[13px] font-medium leading-relaxed text-emerald-900">{str}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeBreakdown.friction_points && activeBreakdown.friction_points.length > 0 && (
                  <div>
                    <h5 className="mb-2 text-xs font-bold uppercase tracking-wider text-rose-700">
                      Channel Friction Points
                    </h5>
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      {activeBreakdown.friction_points.map((fric: string, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 rounded-xl border border-rose-100 bg-rose-50/50 p-3 transition hover:border-rose-200 hover:bg-rose-50"
                        >
                          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-600">
                            <AlertTriangle className="h-4 w-4" />
                          </span>
                          <p dir="auto" className="text-[13px] font-medium leading-relaxed text-rose-900">{fric}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Panel>
          )}

          {/* Feedbacks / Reviews list for this channel */}
          <Panel
            title={`Customer Feedbacks for ${activeRow.platform}`}
            hint={`${channelFeedbacks.length} items matching active filters`}
          >
            <div className="space-y-4">

              {channelFeedbacks.length === 0 ? (
                <p className="py-6 text-center text-xs text-slate-400">
                  No feedback items found for this sentiment filter.
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {channelFeedbacks.map((fb, idx) => (
                    <blockquote
                      key={idx}
                      className="pdf-block flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:shadow-[0_8px_22px_rgba(15,23,42,0.08)]"
                    >
                      <div>
                        <div className="mb-2.5 flex flex-wrap items-center gap-2">
                          <span
                            className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                            style={{
                              color: sentimentDot(fb.sentiment),
                              background: `${sentimentDot(fb.sentiment)}14`,
                            }}
                          >
                            <span className="h-1.5 w-1.5 rounded-full" style={{ background: sentimentDot(fb.sentiment) }} />
                            {fb.sentiment}
                          </span>
                          {fb.label && (
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                              {fb.label}
                            </span>
                          )}
                          {fb.rating != null && (
                            <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[11px] font-bold text-amber-700">
                              <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                              {fb.rating}/5
                            </span>
                          )}
                        </div>

                        <p dir="auto" className="text-[13.5px] leading-relaxed text-slate-700">
                          {fb.text}
                        </p>
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-[11px] text-slate-400">
                        <span className="flex items-center gap-1.5">
                          <span>
                            {fb.author || fb.platform}
                            {fmtDate(fb.date) && ` · ${fmtDate(fb.date)}`}
                          </span>
                          {sourceLabelOf(fb.source) && (
                            <span
                              className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                                fb.source === "page"
                                  ? "bg-[#1877F2]/10 text-[#1877F2]"
                                  : "bg-slate-100 text-slate-500"
                              }`}
                            >
                              {sourceLabelOf(fb.source)}
                            </span>
                          )}
                        </span>
                        {fb.url && (
                          <a
                            href={fb.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-semibold text-[#8a6d2f] hover:underline"
                          >
                            View
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </blockquote>
                  ))}
                </div>
              )}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Owned-channel visuals (from the consultant's workbook)             */
/* ------------------------------------------------------------------ */

function OwnedChannelTable({ channels }: { channels: ChannelAnalysis[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
            <th className="pb-2.5 pr-4 font-semibold">Channel</th>
            <th className="pb-2.5 pr-4 text-right font-semibold">Audience</th>
            <th className="pb-2.5 pr-4 text-right font-semibold">Growth</th>
            <th className="pb-2.5 pr-6 text-right font-semibold">Engagement</th>
            <th className="pb-2.5 pr-6 font-semibold">Response time</th>
            <th className="pb-2.5 font-semibold">Complaints handling</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((c) => {
            const audience = parseCount(c.followers_growth);
            const delta = parseDelta(c.followers_growth);
            const up = delta?.startsWith("+");
            return (
              <tr key={c.channel} className="border-b border-slate-50 last:border-0">
                <td className="py-2.5 pr-4">
                  <span className="text-[13px] font-semibold text-slate-800">{c.channel}</span>
                  {c.account_handle && (
                    <span className="ml-2 text-[11px] text-slate-400">{c.account_handle}</span>
                  )}
                </td>
                <td className="py-3 pr-4 text-right text-[15px] font-bold tabular-nums text-slate-800">
                  {compact(audience)}
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {delta ? (
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${
                        up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                      }`}
                    >
                      {up ? "▲" : "▼"} {delta.replace(/[+-]/, "")}
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-300">—</span>
                  )}
                </td>
                <td className="py-3 pr-6 text-right text-[13px] font-semibold tabular-nums text-slate-700">
                  {c.engagement_rate ?? "—"}
                </td>
                <td className="py-3 pr-6 text-[13px] text-slate-600">{c.response_time_to_comments ?? "—"}</td>
                <td className="py-3 text-[13px] text-slate-600">{c.complaints_handling ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TopPostsTable({ channels }: { channels: ChannelAnalysis[] }) {
  const posts = channels
    .flatMap((c) => c.posts.map((p) => ({ channel: c.channel, post: p })))
    .filter((x) => postTotal(x.post) > 0)
    .sort((a, b) => postTotal(b.post) - postTotal(a.post))
    .slice(0, 5);

  if (posts.length === 0) return null;
  const max = Math.max(...posts.map((p) => postTotal(p.post)), 1);

  /* A ranked bar list rather than a plain table: with five rows the relative size of the
     best post is the point, and a column of numbers hides it. */
  return (
    <div className="space-y-3">
      {posts.map(({ channel, post }, i) => {
        const total = postTotal(post);
        return (
          <div key={i} className="pdf-block">
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-[13px] font-medium text-slate-800">
                {post.post || "Untitled"}
                <span className="ml-2 text-[11px] font-normal text-slate-400">
                  {channel}
                  {post.date && ` · ${post.date.slice(0, 10)}`}
                </span>
              </span>
              <span className="shrink-0 text-[13px] font-bold tabular-nums text-slate-800">
                {total.toLocaleString()}
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded bg-slate-100">
              <div className="h-full rounded bg-slate-700" style={{ width: `${(total / max) * 100}%` }} />
            </div>
            <p className="mt-1 text-[11px] tabular-nums text-slate-400">
              {post.likes ?? 0} likes · {post.comments ?? 0} comments · {post.shares ?? 0} shares
            </p>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Report page                                                        */
/* ------------------------------------------------------------------ */
type Props = {
  result: ScrapingResponse;
  onBack: () => void;
  onExportExcel: () => void;
  onReuseInputs?: () => void;
};

export default function SocialReportView({ result, onBack, onExportExcel, onReuseInputs }: Props) {
  const report = result.detailed_report;
  const evidence = report?.evidence ?? null;
  const manual = result.manual_analysis ?? null;

  // Report chatbot: answers from this report's computed findings, persisted per report.
  const [chatMessages, setChatMessages] = useState<ModuleChatMessage[]>([]);
  const appendChatMessage = (m: ModuleChatMessage) => setChatMessages((prev) => [...prev, m]);
  const canChat = Boolean(result.report_filename && report);

  // Load the persisted conversation when a report opens (and switch cleanly between reports).
  useEffect(() => {
    const stored = result.chat_messages;
    setChatMessages(
      Array.isArray(stored) && stored.length
        ? stored.map((m) => ({
            id: m.id ?? `${Math.random()}`,
            role: m.role === "assistant" ? "assistant" : "user",
            text: m.text ?? "",
            sources: m.sources,
            ts: m.ts ?? Date.now(),
          }))
        : [],
    );
  }, [result.report_filename, result.chat_messages]);
  /* Memoised because the `?? []` fallback would otherwise mint a new array on every render,
     re-running the section memo and re-subscribing the scroll listener each time. */
  const channels = useMemo(() => manual?.channels ?? [], [manual]);
  const website = manual?.website ?? null;

  // KPI inputs
  /* Both states mean the source contributed nothing to the analysis, and the reader needs
     to know either way: an empty Google Maps that silently drops a national brand to 14
     reviews is as misleading as one that errored. */
  const failedSources = result.platforms.filter(
    (p) => p.status === "error" || p.status === "empty",
  );
  const coveredSources = [
    ...result.platforms.filter((p) => p.status === "success").map((p) => p.platform),
    ...channels.map((c) => c.channel),
    ...(website ? ["Website"] : []),
  ].filter((name, i, all) => all.indexOf(name) === i);
  const audience = channels.reduce((sum, c) => sum + (parseCount(c.followers_growth) ?? 0), 0);
  /* Growth of the largest channel stands in for overall audience momentum: the workbook
     records growth per channel, never a consolidated figure, and averaging percentages
     across channels of wildly different sizes would be misleading. */
  const biggestChannel = channels
    .slice()
    .sort((a, b) => (parseCount(b.followers_growth) ?? 0) - (parseCount(a.followers_growth) ?? 0))[0];
  const topChannelDelta = parseDelta(biggestChannel?.followers_growth);
  const visits = parseCount(website?.traffic?.total_visits);
  const sentiment = report?.overall_sentiment ?? null;
  const ratings = evidence?.rating_distribution ?? null;
  const metricPanelCount =
    (sentiment ? 1 : 0) + (ratings ? 1 : 0) + ((evidence?.platform_sentiment?.length ?? 0) > 1 ? 1 : 0);
  const platformRows = useMemo(() => evidence?.platform_sentiment ?? [], [evidence]);

  /* Language / dialect mix, inferred from the comment text (anonymous — no gender/age).
     Computed from the raw reviews + verbatims already in the report, so it works on past
     reports too. Suppressed below a minimum sample so a thin dataset doesn't fake a chart. */
  const languageMix = useMemo(() => {
    const seen = new Set<string>();
    const texts: string[] = [];
    const push = (t?: string | null) => {
      const s = (t || "").trim();
      if (s.length < 6) return;
      const key = s.slice(0, 60);
      if (seen.has(key)) return;
      seen.add(key);
      texts.push(s);
    };
    for (const p of result.platforms ?? []) for (const r of p.reviews ?? []) push(r.text);
    for (const v of evidence?.verbatims ?? []) push(v.text);
    if (texts.length < 15) return null;

    const counts = new Map<LangBucket, number>();
    for (const t of texts) {
      const l = detectLanguage(t);
      counts.set(l, (counts.get(l) ?? 0) + 1);
    }
    const total = texts.length;
    const data = LANG_ORDER.map((l) => ({
      label: l,
      value: counts.get(l) ?? 0,
      pct: Math.round((100 * (counts.get(l) ?? 0)) / total),
      color: LANG_COLORS[l],
    })).filter((d) => d.value > 0);
    return { data, total };
  }, [result.platforms, evidence]);

  /* One hue per channel, reused by the volume chart, the complaint split and the channel
     cards, so a colour in one chart is legible from the legend in another. */
  const channelColors = useMemo(
    () => buildChannelColors(platformRows.map((p) => p.platform)),
    [platformRows],
  );

  /* Verbatims indexed by the label they were collected under, so a friction point can show
     its own proof instead of sending the reader to a section three pages away. */
  const verbatimsByLabel = useMemo(() => {
    const map = new Map<string, ThemeVerbatim[]>();
    for (const v of evidence?.verbatims ?? []) {
      const bucket = map.get(v.label);
      if (bucket) bucket.push(v);
      else map.set(v.label, [v]);
    }
    return map;
  }, [evidence]);

  /* Order follows how the report is read, not how the data was gathered: the numbers, then
     the problems, then what to do about them, and only then the supporting detail. A section
     that has no data drops out of both the page and the index. */
  const visibleSections = useMemo<NavSection[]>(() => {
    const defs: { id: string; label: string; show: boolean }[] = [
      { id: "summary", label: "Executive summary", show: !!report },
      { id: "metrics", label: "Key metrics", show: !!report },
      { id: "friction", label: "Friction points", show: !!report },
      { id: "strengths", label: "What's working", show: !!report && report.top_strengths.length > 0 },
      {
        id: "recommendations",
        label: "Recommendations",
        show: !!report && report.recommendations.length > 0,
      },
      {
        id: "topics",
        label: "Complaint categories",
        show:
          !!report &&
          !!evidence &&
          (evidence.top_complaints.length > 0 || evidence.top_themes.length > 0),
      },
      {
        id: "momentum",
        label: "What's rising & falling",
        // Present only when each half of the history carries a real sample.
        show: !!report && !!evidence?.momentum && evidence.momentum.items.length > 0,
      },
      {
        id: "trend",
        label: "Trend over time",
        // Present only when the collection was dense enough per period to plot honestly.
        show: !!report && !!evidence?.trend,
      },
      {
        id: "sentiment",
        label: "Sentiment by channel",
        show: !!report && platformRows.length > 0,
      },
      { id: "language", label: "Language & dialect", show: !!report && !!languageMix },
      { id: "channels", label: "Owned channels", show: !!report && channels.length > 0 },
      {
        id: "posts",
        label: "Top performing posts",
        show: !!report && channels.some((c) => c.posts.length > 0),
      },
      {
        id: "website",
        label: "Website performance",
        show: !!report && !!(website || report.website_assessment),
      },
      { id: "sources", label: "Sources & methodology", show: true },
    ];
    return defs.filter((s) => s.show).map((s) => ({ id: s.id, label: s.label }));
  }, [report, evidence, channels, website, platformRows, languageMix]);

  const sectionIds = useMemo(() => visibleSections.map((s) => s.id), [visibleSections]);
  const activeSection = useActiveSection(sectionIds);
  const shows = (id: string) => visibleSections.some((s) => s.id === id);
  const hasDetail = ["topics", "sentiment", "language", "channels", "posts", "website"].some(shows);

  return (
    /* No `overflow-hidden` here: it makes this element a scroll container, which silently
       kills the sticky index in the left margin. The decorative wash is clipped by its own
       fixed wrapper instead. */
    <div className="relative min-h-screen bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_40%,#f7f9fb_72%,#ffffff_100%)] text-slate-800">
      <style>{`
        @media print {
          @page { size: A4; margin: 13mm 11mm; }
          html, body { background: #fff !important; }
          body * { visibility: hidden !important; }
          #report-print-area, #report-print-area * { visibility: visible !important; }
          #report-print-area {
            position: absolute !important; left: 0; top: 0;
            width: 100% !important; max-width: none !important;
            margin: 0 !important; padding: 0 !important;
          }
          #report-print-area .no-print { display: none !important; }
          #report-print-area * { box-shadow: none !important; backdrop-filter: none !important; }
          /* Keep cards and quotes whole; never a whole section, which forces blank pages
             when the section is taller than one page. */
          #report-print-area .pdf-block,
          #report-print-area blockquote,
          #report-print-area li { break-inside: avoid; page-break-inside: avoid; }
          #report-print-area h1, #report-print-area h2,
          #report-print-area h3, #report-print-area h4 { break-after: avoid; page-break-after: avoid; }
          #report-print-area .page-break { break-before: page; page-break-before: always; }
          /* Tailwind's lg/xl breakpoints never fire on an A4 page (~794px), so the KPI row
             and the chart row would print stacked one per line and run to four pages. Pin
             the column counts the layout was designed around. */
          #report-print-area .print-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
          #report-print-area .print-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
          /* Wide tables must reflow to the page instead of being clipped by the scroller. */
          #report-print-area .overflow-x-auto { overflow: visible !important; }
          #report-print-area table { min-width: 0 !important; width: 100% !important; font-size: 9.5pt; }
          #report-print-area thead { display: table-header-group; }
          #report-print-area tr { break-inside: avoid; page-break-inside: avoid; }
          * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        }
      `}</style>

      <div className="no-print pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute right-[-10%] top-[-4%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.10),rgba(255,255,255,0))] blur-3xl" />
      </div>

      {/* ── Top bar ── */}
      <header className="no-print sticky top-0 z-30 flex flex-wrap items-center gap-4 border-b border-slate-200/70 bg-white/85 px-6 py-4 backdrop-blur-lg">
        <button
          onClick={onBack}
          className="btn-secondary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          New analysis
        </button>
        <div className="flex items-center gap-3">
          <img src={`${import.meta.env.BASE_URL}ey_logo.svg`} alt="EY" className="h-6 w-auto" />
          <span className="h-4 w-px bg-slate-200" />
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-900">{result.brand_name}</h1>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Social &amp; Web CX Report
            </p>
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          {result.report_filename && (
            <AddToProjectButton
              kind="social_report"
              refId={result.report_filename}
              stepKey="social"
              title={result.brand_name}
              suggestedName={result.brand_name}
              compact
            />
          )}
          {result.report_filename && (
            <ShareButton kind="social_report" refId={result.report_filename} compact />
          )}
          {/* Shown for any report we can repopulate the form from: either the saved scrape
              inputs, or a manual workbook. Older reports predating both stay hidden. */}
          {onReuseInputs && (result.scrape_request || result.manual_analysis) && (
            <button
              onClick={onReuseInputs}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-ey-gold/50 hover:text-slate-900"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit inputs &amp; re-run
            </button>
          )}
          <button
            onClick={() => window.print()}
            className="btn-secondary"
          >
            <FileText className="h-3.5 w-3.5" />
            Export PDF
          </button>
          <button
            onClick={onExportExcel}
            className="inline-flex items-center gap-1.5 rounded-full bg-[#2E2E38] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#1a1a22]"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            Export Excel
          </button>
        </div>
      </header>

      {/* The index sits in the left margin and the document keeps the centre of the screen:
          a mirrored spacer on the right balances the sidebar so nothing is pushed off-centre. */}
      <main className="relative z-10 mx-auto flex w-full max-w-[1560px] gap-8 px-6 py-10">
        <TableOfContents sections={visibleSections} active={activeSection} />
        <section id="report-print-area" className="mx-auto w-full min-w-0 max-w-[1000px] space-y-12">
          {/* ── Cover strip ── */}
          <div className="border-b-2 border-ey-gold pb-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ey-gold">
              Customer Experience Analysis
            </p>
            <h1 className="mt-1.5 text-4xl font-bold tracking-tight text-slate-900">
              {result.brand_name}
            </h1>
            <p className="mt-2 text-[13px] text-slate-500">
              {manual?.reporting_period && (
                <>
                  <span className="font-semibold text-slate-700">{manual.reporting_period}</span>
                  {" · "}
                </>
              )}
              Generated {new Date(result.scraped_at).toLocaleDateString()}
            </p>
            {/* Which sources this report actually rests on, stated before any finding —
                the reader should never have to reach the methodology page to learn it. */}
            {coveredSources.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Sources
                </span>
                {coveredSources.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600"
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>

          {!report && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
              This saved report predates the current format and has no analysis section.
            </p>
          )}

          {/* A thin report should explain itself at the top rather than leave the reader
              wondering why a section looks empty. */}
          {failedSources.length > 0 && (
            <div className="pdf-block flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <p className="text-[12px] leading-relaxed text-amber-800">
                <span className="font-semibold">
                  {failedSources.map((p) => p.platform).join(" and ")} returned no data
                </span>{" "}
                for this run, so the findings below rest on the remaining sources
                {evidence ? ` (${evidence.reviews_collected} reviews)` : ""}. Re-running may
                recover them.
              </p>
            </div>
          )}

          {report && (
            <>
              {/* ── 01 · Executive summary ── */}
              <Section id="summary" title="Executive summary">
                <p className="pdf-block rounded-2xl border border-slate-200 bg-white p-6 text-[15px] leading-[1.75] text-slate-700">
                  {report.executive_summary}
                </p>
              </Section>

              {/* ── 02 · Key metrics: the numbers lead, exactly as an official report does ── */}
              <Section
                id="metrics"
                title="Key metrics"
                icon={<BarChart3 className="h-5 w-5 text-slate-500" />}
                subtitle="Measured, not inferred"
              >
                <div className="space-y-5">
                  {/* Ordered so the headline lands first: a reader who looks for five seconds
                      should leave with the sentiment split, not the sample size. Three across
                      rather than five, so each card has room to breathe. */}
                  <div className="print-cols-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <Kpi
                      label="Negative sentiment"
                      icon={<Frown className="h-3.5 w-3.5" />}
                      value={sentiment ? `${sentiment.negative_pct}` : "—"}
                      unit={sentiment ? "%" : undefined}
                      sub={sentiment ? `${sentiment.positive_pct}% positive` : undefined}
                      tone={sentiment && sentiment.negative_pct >= 25 ? "bad" : "good"}
                      strip={
                        sentiment ? (
                          <SentimentBar
                            pos={sentiment.positive_pct}
                            neu={sentiment.neutral_pct}
                            neg={sentiment.negative_pct}
                          />
                        ) : undefined
                      }
                    />
                    <Kpi
                      label="Average rating"
                      icon={<Star className="h-3.5 w-3.5" />}
                      value={ratings?.average != null ? ratings.average.toFixed(2) : "—"}
                      unit={ratings?.average != null ? "/5" : undefined}
                      sub={ratings ? `${ratings.total} rated reviews` : undefined}
                      tone={ratings?.average != null && ratings.average < 3 ? "bad" : "neutral"}
                    />
                    <Kpi
                      label="Reviews analysed"
                      icon={<MessageSquare className="h-3.5 w-3.5" />}
                      value={(evidence?.reviews_collected ?? result.total_reviews).toLocaleString()}
                      sub={evidence ? `${evidence.reviews_classified} comments read in depth` : undefined}
                    />
                    {/* Only when a channel actually reports replies; the base is shown so a 0%
                        on a handful of Trustpilot reviews can't read as covering all of them. */}
                    {evidence?.reply_rate_pct != null && (
                      <Kpi
                        label="Reply rate"
                        icon={<Reply className="h-3.5 w-3.5" />}
                        value={`${evidence.reply_rate_pct}`}
                        unit="%"
                        sub={`brand replies · ${evidence.reply_rate_base} reviews checked`}
                        tone={evidence.reply_rate_pct < 20 ? "bad" : "good"}
                      />
                    )}
                    <Kpi
                      label="Social audience"
                      icon={<Users className="h-3.5 w-3.5" />}
                      value={audience > 0 ? compact(audience) : "—"}
                      delta={topChannelDelta}
                      sub={
                        audience > 0
                          ? `${channels.length} owned channel${channels.length === 1 ? "" : "s"}`
                          : "no workbook supplied"
                      }
                    />
                    <Kpi
                      label="Website visits"
                      icon={<Globe className="h-3.5 w-3.5" />}
                      value={compact(visits)}
                      sub={
                        website?.traffic?.bounce_rate
                          ? `bounce ${formatPercent(website.traffic.bounce_rate)}`
                          : undefined
                      }
                    />
                  </div>

                  {/* Between them these state the whole quantitative picture. The column count
                      follows how many actually render, so two panels fill the row instead of
                      leaving a gap where a third would have been. */}
                  <div
                    className={`grid gap-5 ${
                      metricPanelCount >= 3
                        ? "print-cols-3 lg:grid-cols-3"
                        : metricPanelCount === 2
                          ? "print-cols-2 lg:grid-cols-2"
                          : ""
                    }`}
                  >
                    {sentiment && (
                      <Panel title="Overall sentiment" hint={`${sentiment.classified_count} comments classified`}>
                        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-5 py-2">
                          <Donut
                            pos={sentiment.positive_pct}
                            neu={sentiment.neutral_pct}
                            neg={sentiment.negative_pct}
                            size={140}
                          />
                          <div className="flex w-32 flex-col gap-3">
                            <LegendDot color={POSITIVE_MARK} label="Positive" value={`${sentiment.positive_pct}%`} />
                            <LegendDot color={NEUTRAL_MARK} label="Neutral" value={`${sentiment.neutral_pct}%`} />
                            <LegendDot color={NEGATIVE_MARK} label="Negative" value={`${sentiment.negative_pct}%`} />
                          </div>
                        </div>
                      </Panel>
                    )}
                    {ratings && (
                      <Panel
                        title="Rating spread"
                        hint={`${ratings.total} rated reviews · average ${ratings.average?.toFixed(2) ?? "—"}/5`}
                      >
                        <RatingHistogram dist={ratings} />
                        <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
                          {ratings.one + ratings.two} at 1–2★ · {ratings.four + ratings.five} at 4–5★
                        </p>
                      </Panel>
                    )}
                    {/* Only worth a panel once there is a split to show. With a single
                        channel the bar says nothing the source chips on the cover didn't,
                        and it leaves a half-empty card. */}
                    {platformRows.length > 1 && (
                      <Panel title="Where the evidence comes from" hint="Reviews collected per channel">
                        <ChannelVolumeChart rows={platformRows} colors={channelColors} />
                        <p className="mt-4 border-t border-slate-100 pt-3 text-[11px] leading-snug text-slate-500">
                          These colours identify each channel in the charts below.
                        </p>
                      </Panel>
                    )}
                  </div>

                  {/* Rating vs. comment agreement — a quiet data-quality note when the two
                      align, an amber flag when they diverge enough to suggest rating
                      inflation or gaming. Only shown when enough reviews carry both. */}
                  {evidence?.rating_sentiment && (
                    <RatingSentimentNote check={evidence.rating_sentiment} />
                  )}
                </div>
              </Section>

              {/* ── 03 · Friction points ── */}
              <Section
                id="friction"
                title="Friction points"
                icon={<AlertTriangle className="h-5 w-5 text-rose-600" />}
                subtitle="Ranked by volume of evidence"
              >
                {report.top_friction_points.length > 0 ? (
                  <div className="space-y-2.5">
                    {report.top_friction_points.map((f, i) => {
                      return (
                        <div
                          key={i}
                          className="pdf-block flex gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:-translate-y-0.5 hover:border-rose-200 hover:shadow-[0_12px_30px_rgba(15,23,42,0.08)]"
                        >
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500 to-rose-600 text-[15px] font-bold text-white shadow-[0_4px_10px_rgba(225,29,72,0.25)]">
                            {i + 1}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[16px] font-bold text-slate-900">{f.theme}</span>
                              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                {sourceLabel(f.source)}
                              </span>
                              {f.mention_count != null && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide tabular-nums text-rose-700">
                                  {f.mention_count} {f.source === "consultant" ? "opinions" : "mentions"}
                                  {f.share_pct != null && ` · ${f.share_pct}%`}
                                </span>
                              )}
                            </div>
                            <p dir="auto" className="mt-2 text-[14px] leading-relaxed text-slate-600">{f.description}</p>
                            {/* Proof sits with the claim. A real review carries its channel,
                                rating and date, so it is preferred over the model's own
                                paraphrase whenever one exists for this category. */}
                            {(() => {
                              const quoted = f.related_label ? verbatimsByLabel.get(f.related_label) : undefined;
                              if (quoted && quoted.length > 0) {
                                return (
                                  <div className="mt-3 space-y-2">
                                    {quoted.slice(0, 2).map((v, j) => (
                                      <blockquote key={j} className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                                        <p dir="auto" className="text-[12.5px] leading-relaxed text-slate-600">{v.text}</p>
                                        <VerbatimMeta v={v} />
                                      </blockquote>
                                    ))}
                                  </div>
                                );
                              }
                              // Keep only genuine quotes; the stat lines are already told
                              // by the badge and would read as fabricated verbatims.
                              const quotes = f.supporting_evidence.filter((e) => !looksLikeStat(e));
                              if (quotes.length === 0) return null;
                              return (
                                <div className="mt-3 space-y-2">
                                  {quotes.map((e, j) => (
                                    <blockquote key={j} className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                                      <p dir="auto" className="text-[12.5px] leading-relaxed text-slate-600">{e}</p>
                                    </blockquote>
                                  ))}
                                </div>
                              );
                            })()}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[13px] italic text-slate-400">No recurring friction points identified.</p>
                )}
              </Section>

              {/* ── 04 · What's working ── */}
              {report.top_strengths.length > 0 && (
                <Section
                  id="strengths"
                  title="What's working"
                  icon={<ThumbsUp className="h-5 w-5 text-emerald-600" />}
                  subtitle="Worth protecting"
                >
                  <ul className="pdf-block grid gap-3.5 rounded-xl border border-emerald-200 bg-white p-6 sm:grid-cols-2">
                    {report.top_strengths.map((s, i) => (
                      <li key={i} className="flex gap-2.5">
                        <span
                          className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: POSITIVE_MARK }}
                        />
                        <span className="min-w-0">
                          <span className="text-[14px] leading-relaxed text-slate-700">{s.text}</span>
                          {s.mention_count != null && (
                            <span className="ml-2 whitespace-nowrap rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide tabular-nums text-emerald-700">
                              {s.mention_count} mentions
                              {s.share_pct != null && ` · ${s.share_pct}%`}
                            </span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {/* ── 05 · Recommendations ── */}
              {report.recommendations.length > 0 && (
                <Section
                  id="recommendations"
                  title="Recommendations"
                  icon={<Lightbulb className="h-5 w-5 text-ey-gold" />}
                  subtitle="Prioritised by volume of friction addressed"
                >
                  <ol className="space-y-2.5">
                    {report.recommendations.map((r, i) => (
                      <li
                        key={i}
                        className="pdf-block flex gap-3.5 rounded-xl border border-slate-200 bg-white p-4"
                        style={{ borderLeft: "4px solid #C5A04F" }}
                      >
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ey-gold/15 text-[12px] font-bold text-[#8a6d2f]">
                          {i + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[14px] leading-relaxed text-slate-700">{r.text}</p>
                          {/* What this action would actually fix, and for how many people. */}
                          {r.addresses && (
                            <p className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] text-slate-500">
                              <span className="font-semibold uppercase tracking-wide text-slate-400">
                                Addresses
                              </span>
                              <span className="font-semibold text-slate-700">{r.addresses}</span>
                              {r.mention_count != null && (
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 font-bold tabular-nums text-slate-600">
                                  {r.mention_count} mentions
                                  {r.share_pct != null && ` · ${r.share_pct}%`}
                                </span>
                              )}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                </Section>
              )}

              {hasDetail && (
                <PartDivider
                  label="Supporting detail"
                  hint="The evidence behind the findings above"
                />
              )}

              {/* ── Complaint categories ── */}
              {evidence && (evidence.top_complaints.length > 0 || evidence.top_themes.length > 0) && (
                <Section
                  id="topics"
                  title="Complaint categories"
                  subtitle={`${evidence.reviews_classified} comments classified`}
                >
                  <div className="space-y-4">
                  {evidence.top_complaints.length > 0 && (
                    <Panel
                      title="Complaint mix"
                      hint="Share of classified complaints by category"
                      accent="#e11d48"
                    >
                      <ComplaintDonut items={evidence.top_complaints} />
                    </Panel>
                  )}
                  <div className="grid gap-4 lg:grid-cols-2">
                    {evidence.top_complaints.length > 0 && (
                      <Panel
                        title="Complaints by volume"
                        hint="Bar length is volume · segments show which channel it was found on"
                        accent="#e11d48"
                      >
                        {platformRows.length > 1 && (
                          <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 border-b border-slate-100 pb-2.5">
                            {platformRows.map((p) => (
                              <LegendDot
                                key={p.platform}
                                color={channelColors[p.platform] ?? "#64748b"}
                                label={p.platform}
                              />
                            ))}
                          </div>
                        )}
                        <ComplaintChart items={evidence.top_complaints} colors={channelColors} />
                      </Panel>
                    )}
                    {evidence.top_themes.length > 0 && (
                      <Panel
                        title="Topics by volume"
                        hint="What customers bring up · red share is how negative the topic runs"
                        accent="#475569"
                      >
                        <TopicChart items={evidence.top_themes} />
                      </Panel>
                    )}
                  </div>
                  </div>
                </Section>
              )}

              {/* ── What's rising & falling (only when each half has a real sample) ── */}
              {evidence?.momentum && evidence.momentum.items.length > 0 && (
                <Section
                  id="momentum"
                  title="What's rising &amp; falling"
                  icon={<Activity className="h-5 w-5 text-slate-500" />}
                  subtitle="Complaint categories gaining or losing share of the conversation"
                >
                  <Panel>
                    <MomentumChart momentum={evidence.momentum} />
                  </Panel>
                </Section>
              )}

              {/* ── Trend over time (only when the data supports one) ── */}
              {evidence?.trend && (
                <Section
                  id="trend"
                  title="Trend over time"
                  icon={<TrendingUp className="h-5 w-5 text-slate-500" />}
                  subtitle={`By ${evidence.trend.granularity} · periods with fewer than ${evidence.trend.min_sample} reviews are left unplotted`}
                >
                  <Panel>
                    <TrendChart trend={evidence.trend} />
                    {evidence.trend.has_sentiment && (
                      <div className="mt-5 border-t border-slate-100 pt-4">
                        <p className="mb-2 text-[12px] font-semibold text-slate-600">Sentiment mix by {evidence.trend.granularity}</p>
                        <SentimentMixArea trend={evidence.trend} />
                      </div>
                    )}
                    <p className="mt-4 border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-500">
                      Built from review dates.{" "}
                      {evidence.trend.granularity === "quarter"
                        ? "Grouped by quarter because monthly volume was too low to state a percentage."
                        : "Monthly volume was high enough to plot each month separately."}{" "}
                      Reviews are collected newest-first, so earlier periods reflect a smaller
                      sample and the line is not a complete history of the brand.
                    </p>
                  </Panel>
                </Section>
              )}

              {/* ── Sentiment by channel ── */}
              {platformRows.length > 0 && (
                <Section
                  id="sentiment"
                  title="Sentiment by channel"
                  subtitle="Public reviews & customer feedbacks per channel"
                >
                  <ChannelSentimentTabbedView
                    rows={platformRows}
                    colors={channelColors}
                    verbatims={evidence?.verbatims ?? []}
                    scrapedPlatforms={result.platforms}
                    channelBreakdown={report?.channel_breakdown ?? []}
                  />
                </Section>
              )}

              {/* ── Language & dialect mix (inferred from comment text) ── */}
              {languageMix && (
                <Section
                  id="language"
                  title="Language &amp; dialect"
                  subtitle="Inferred from how customers wrote — comments are anonymous"
                >
                  <Panel>
                    <div className="flex flex-col items-center gap-8 sm:flex-row">
                      <CategoryDonut
                        data={languageMix.data}
                        size={150}
                        centerValue={String(languageMix.total)}
                        centerLabel="comments"
                      />
                      <div className="w-full flex-1 space-y-2.5">
                        {languageMix.data.map((d) => (
                          <div key={d.label} className="flex items-center gap-3">
                            <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: d.color }} />
                            <span className="flex-1 text-sm text-slate-700">{d.label}</span>
                            <div className="hidden h-1.5 w-28 overflow-hidden rounded-full bg-slate-100 sm:block">
                              <div className="h-full rounded-full" style={{ width: `${d.pct}%`, background: d.color }} />
                            </div>
                            <span className="w-10 text-right text-sm font-semibold tabular-nums text-slate-900">{d.pct}%</span>
                            <span className="w-12 text-right text-xs tabular-nums text-slate-400">({d.value})</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <p className="mt-4 border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-400">
                      Detected heuristically from the comment text (Arabic vs Latin script, French/English markers,
                      Tunisian Derja &amp; Arabizi). A guide to the audience's language, not an exact measure. No gender
                      or age is inferred — the data is anonymous.
                    </p>
                  </Panel>
                </Section>
              )}

              {/* ── Owned channels (workbook) ── */}
              {channels.length > 0 && (
                <Section
                  id="channels"
                  title="Owned channels"
                  subtitle="From the consultant's workbook"
                >
                  <Panel>
                    <OwnedChannelTable channels={channels} />
                  </Panel>
                </Section>
              )}

              {/* ── Top posts (workbook) ── */}
              {channels.some((c) => c.posts.length > 0) && (
                <Section
                  id="posts"
                  title="Top performing posts"
                  subtitle="Ranked by total engagement"
                >
                  <Panel>
                    <TopPostsTable channels={channels} />
                  </Panel>
                </Section>
              )}

              {/* ── Website ── */}
              {(website || report.website_assessment) && (
                <Section
                  id="website"
                  title="Website performance"
                  icon={<Globe className="h-5 w-5 text-slate-500" />}
                >
                  <div className="space-y-4">
                    {website?.traffic && (
                      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                        <Kpi label="Visits" value={compact(parseCount(website.traffic.total_visits))} size="sm" />
                        <Kpi label="Bounce rate" value={formatPercent(website.traffic.bounce_rate)} size="sm" />
                        <Kpi label="Pages / visit" value={website.traffic.pages_per_visit ?? "—"} size="sm" />
                        <Kpi label="Avg. duration" value={website.traffic.avg_visit_duration ?? "—"} size="sm" />
                        <Kpi
                          label="Mobile share"
                          value={formatPercent(website.traffic.mobile_share)}
                          size="sm"
                          sub={
                            website.traffic.desktop_share
                              ? `desktop ${formatPercent(website.traffic.desktop_share)}`
                              : undefined
                          }
                        />
                      </div>
                    )}
                    {report.website_assessment && (
                      <p className="pdf-block rounded-2xl border border-slate-200 bg-white p-6 text-[14px] leading-relaxed text-slate-700">
                        {report.website_assessment}
                      </p>
                    )}
                  </div>
                </Section>
              )}

            </>
          )}

          {/* ── Sources & methodology ── */}
          <Section id="sources" title="Sources &amp; methodology">
            <Panel>
              <div className="space-y-2">
                {result.platforms.map((p) => (
                  <div
                    key={p.platform}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-50 pb-2 last:border-0 last:pb-0"
                  >
                    <span className="w-24 shrink-0 text-[13px] font-semibold text-slate-800">{p.platform}</span>
                    <StatusBadge status={p.status} count={p.review_count} />
                    {p.summary_stat && <span className="text-[12px] text-slate-500">{p.summary_stat}</span>}
                    {p.status === "error" && p.error_message && (
                      <span className="text-[12px] text-rose-600">{p.error_message}</span>
                    )}
                    {p.matched_places && p.matched_places.length > 0 && (
                      <span className="w-full text-[12px] text-slate-400">
                        Places: {p.matched_places.join(" · ")}
                      </span>
                    )}
                    {p.excluded_places && p.excluded_places.length > 0 && (
                      <span className="w-full text-[12px] text-amber-600">
                        Excluded as out of location: {p.excluded_places.join(" · ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {report?.methodology_note && (
                <p className="mt-4 border-t border-slate-100 pt-3 text-[12px] italic leading-relaxed text-slate-500">
                  {report.methodology_note}
                </p>
              )}
            </Panel>
          </Section>
        </section>
        {/* Mirrors the sidebar so the document stays optically centred on screen. */}
        <div className="no-print hidden w-56 shrink-0 xl:block" aria-hidden />
      </main>

      {/* Floating report assistant — answers from this report's computed findings. */}
      <div className="no-print">
        <ModuleChat
          endpoint={`${API_BASE_URL}/scraping/reports/${result.report_filename}/chat`}
          messages={chatMessages}
          onAppendMessage={appendChatMessage}
          title="Report Assistant"
          subtitle={result.brand_name}
          emptyTitle="Ask about this report"
          emptyHint="Sentiment, complaints, channels, trends, recommendations — I answer from the report."
          placeholder="Ask about the findings..."
          disabled={!canChat}
          disabledHint="Chat is available once the report is saved."
        />
      </div>
    </div>
  );
}
