/**
 * The report's charts: one component per figure, each taking already-computed data and drawing it.
 *
 * They live apart from the report because they are the part with no reasoning in them. Every
 * number they receive was computed in Python and carried through unchanged -- these decide colour,
 * axis and label, and nothing else. Reading the report's structure no longer means scrolling past
 * five hundred lines of axis configuration, and changing how a figure looks cannot touch what it
 * says.
 */

import { ShieldCheck } from "lucide-react";
import type {
  PlatformSentiment,
  RatingDistribution,
  RatingSentimentCheck,
  ThemeFrequency,
  TopicMomentum,
  TrendSeries,
} from "../../types/scraping";
import { CATEGORY_HUES, NEGATIVE_MARK, NEUTRAL_MARK, OTHER_HUE, POSITIVE_MARK } from "./colors";
import { CategoryDonut, LegendDot } from "./primitives";

export function ComplaintDonut({ items }: { items: ThemeFrequency[] }) {
  // Keep a single "Other" slice: fold any category literally named "Other" into the remainder.
  const isOther = (l: string) => l.trim().toLowerCase() === "other";
  const named = items.filter((i) => !isOther(i.label));
  const otherSeed = items.filter((i) => isOther(i.label)).reduce((s, x) => s + x.count, 0);
  const sorted = [...named].sort((a, b) => b.count - a.count);
  const top = sorted.slice(0, 5);
  const restTotal = sorted.slice(5).reduce((s, x) => s + x.count, 0) + otherSeed;
  const slices = top.map((t, i) => ({ label: t.label, value: t.count, color: CATEGORY_HUES[i] ?? OTHER_HUE }));
  if (restTotal > 0) slices.push({ label: "Other", value: restTotal, color: OTHER_HUE });
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row">
      <CategoryDonut data={slices} size={172} centerValue={String(total)} centerLabel="complaints" />
      <div className="w-full flex-1 space-y-1.5">
        {slices.map((s, i) => (
          <LegendDot key={i} color={s.color} label={s.label} value={`${s.value} · ${Math.round((s.value / total) * 100)}%`} />
        ))}
      </div>
    </div>
  );
}

/* Sentiment mix over time: a 100%-stacked area of positive / neutral / negative share per period.
   Shows whether the *mix* is improving or worsening, which the single negativity line cannot. */
export function SentimentMixArea({ trend }: { trend: TrendSeries }) {
  const pts = trend.points.filter(
    (p) => p.positive_pct != null && p.neutral_pct != null && p.negative_pct != null,
  );
  if (pts.length < 2) return null;

  const W = 720;
  const H = 200;
  const padT = 8;
  const padB = 22;
  const plotH = H - padT - padB;
  const n = pts.length;
  const x = (i: number) => (n === 1 ? W / 2 : (i / (n - 1)) * W);
  const y = (pct: number) => padT + plotH * (1 - pct / 100);

  // Normalise each period to 100% so the band heights read as share, not raw count.
  const norm = pts.map((p) => {
    const pos = p.positive_pct as number;
    const neu = p.neutral_pct as number;
    const neg = p.negative_pct as number;
    const t = pos + neu + neg || 1;
    return { pos: (pos / t) * 100, neu: (neu / t) * 100, neg: (neg / t) * 100, label: p.label };
  });

  const band = (lower: (d: (typeof norm)[number]) => number, upper: (d: (typeof norm)[number]) => number) => {
    const top = norm.map((d, i) => `${x(i)},${y(upper(d))}`);
    const bottom = norm.map((d, i) => `${x(i)},${y(lower(d))}`).reverse();
    return `M ${top.join(" L ")} L ${bottom.join(" L ")} Z`;
  };

  // Stack bottom→top: positive (green base), neutral, negative (red on top shrinking = better).
  const posBand = band(() => 0, (d) => d.pos);
  const neuBand = band((d) => d.pos, (d) => d.pos + d.neu);
  const negBand = band((d) => d.pos + d.neu, () => 100);
  const NEUTRAL = "#94a3b8";
  const last = norm[norm.length - 1];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        <LegendDot color={POSITIVE_MARK} label="Positive" value={`${Math.round(last.pos)}%`} />
        <LegendDot color={NEUTRAL} label="Neutral" value={`${Math.round(last.neu)}%`} />
        <LegendDot color={NEGATIVE_MARK} label="Negative" value={`${Math.round(last.neg)}%`} />
        <span className="ml-auto text-[11px] text-slate-400">latest: {last.label}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Positive, neutral and negative share by ${trend.granularity}`}
      >
        {[0, 25, 50, 75, 100].map((g) => (
          <line key={g} x1={0} x2={W} y1={y(g)} y2={y(g)} stroke="#eef2f7" strokeWidth={1} />
        ))}
        <path d={posBand} fill={POSITIVE_MARK} fillOpacity={0.85} />
        <path d={neuBand} fill={NEUTRAL} fillOpacity={0.7} />
        <path d={negBand} fill={NEGATIVE_MARK} fillOpacity={0.85} />
        {/* period marks along the bottom */}
        {norm.map((d, i) =>
          i % Math.ceil(n / 6) === 0 || i === n - 1 ? (
            <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="fill-slate-400 text-[10px]">
              {d.label}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}

/** Volume of reviews per channel — colours here seed every other channel-coded chart. */
export function ChannelVolumeChart({
  rows,
  colors,
}: {
  rows: PlatformSentiment[];
  colors: Record<string, string>;
}) {
  const max = Math.max(...rows.map((r) => r.review_count), 1);
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.platform} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate text-[12px] font-medium text-slate-600">
            {r.platform}
          </span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100">
            <div
              className="h-full rounded"
              style={{
                width: `${(r.review_count / max) * 100}%`,
                background: colors[r.platform] ?? "#64748b",
              }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-[12px] font-bold tabular-nums text-slate-700">
            {r.review_count}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Complaint volume, each bar split by the channel it was found on.
 *
 * This is the "where does each category surface" question answered graphically rather than
 * as a footnote: bar length is volume, the segments are the channel mix. */
export function ComplaintChart({
  items,
  colors,
}: {
  items: ThemeFrequency[];
  colors: Record<string, string>;
}) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="space-y-3.5">
      {items.map((item) => {
        const entries = Object.entries(item.by_platform ?? {});
        const total = entries.reduce((s, [, n]) => s + n, 0) || item.count || 1;
        return (
          <div key={item.label}>
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="truncate text-[13px] font-semibold text-slate-800">{item.label}</span>
              <span className="shrink-0 text-[12px] tabular-nums text-slate-500">
                <span className="font-bold text-slate-800">{item.count}</span> · {item.share_pct}%
              </span>
            </div>
            <div className="h-3.5 w-full overflow-hidden rounded bg-slate-100">
              {/* 2px surface gaps keep adjacent segments legible when two channel hues sit
                  side by side, including for a colourblind reader. */}
              <div className="flex h-full gap-[2px]" style={{ width: `${(item.count / max) * 100}%` }}>
                {entries.length > 0 ? (
                  entries.map(([platform, n]) => (
                    <div
                      key={platform}
                      title={`${platform}: ${n}`}
                      style={{ width: `${(n / total) * 100}%`, background: colors[platform] ?? "#64748b" }}
                    />
                  ))
                ) : (
                  <div className="w-full bg-slate-400" />
                )}
              </div>
            </div>
            {entries.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-400">
                {entries.map(([platform, n]) => (
                  <span key={platform} className="tabular-nums">
                    {platform} {n}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Topic volume with how negative each topic runs — the discussion agenda, not the problems. */
export function TopicChart({ items }: { items: ThemeFrequency[] }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="space-y-3.5">
      {items.map((item) => (
        <div key={item.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="truncate text-[13px] font-semibold text-slate-800">{item.label}</span>
            <span className="shrink-0 text-[12px] tabular-nums text-slate-500">
              <span className="font-bold text-slate-800">{item.count}</span> · {item.share_pct}%
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="h-3.5 flex-1 overflow-hidden rounded bg-slate-100">
              {/* Split by sentiment: the negative part of the bar is the part that matters. */}
              <div className="flex h-full gap-[2px]" style={{ width: `${(item.count / max) * 100}%` }}>
                <div style={{ width: `${item.negative_pct}%`, background: NEGATIVE_MARK }} />
                <div style={{ width: `${100 - item.negative_pct}%`, background: NEUTRAL_MARK }} />
              </div>
            </div>
            <span
              className={`w-[4.5rem] shrink-0 text-right text-[11px] font-semibold tabular-nums ${
                item.negative_pct >= 60
                  ? "text-rose-600"
                  : item.negative_pct >= 30
                    ? "text-amber-600"
                    : "text-emerald-600"
              }`}
            >
              {item.negative_pct}% neg.
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Which complaint categories are gaining or losing share of the conversation.
 *
 * A dumbbell per category: the earlier share and the recent share joined by a bar whose
 * colour is the direction of travel. This is the one section that says whether a problem is
 * growing, not just how big it is now — so rising problems (rose) are what the eye should
 * catch first, and the list is already ordered by size of movement. */
export function MomentumChart({ momentum }: { momentum: TopicMomentum }) {
  // A real dumbbell on a shared share axis, which is what the section always claimed to be.
  // The previous version drew the DELTA outward from a centre line, so both dots sat at an
  // arbitrary position: two categories at very different sizes looked identical if they moved
  // by the same amount, and a chart where everything moved one way left half the plot empty.
  // Plotting both shares on one 0→max axis shows size and movement at once.
  const maxShare = Math.max(
    5,
    ...momentum.items.flatMap((i) => [i.earlier_share, i.recent_share]),
  );
  const pos = (share: number) => (share / maxShare) * 100;

  const color = (d: string) => (d === "rising" ? NEGATIVE_MARK : d === "falling" ? POSITIVE_MARK : "#94a3b8");
  const word = (d: string) => (d === "rising" ? "rising" : d === "falling" ? "easing" : "steady");
  const icon = (d: string) => (d === "rising" ? "▲" : d === "falling" ? "▼" : "→");
  const GRID = "grid grid-cols-[minmax(9rem,1fr)_1.7fr_auto] items-center gap-4";

  return (
    <div>
      {/* Both windows are the same length by construction, so the comparison is like-for-like. */}
      <div className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-500">
        <span className="inline-block h-2 w-2 rounded-full bg-slate-300" />
        <span className="font-medium text-slate-600">{momentum.earlier_label}</span>
        <span className="tabular-nums text-slate-400">({momentum.earlier_total} reviews)</span>
        <span className="mx-1 text-slate-300">→</span>
        <span className="inline-block h-2 w-2 rounded-full bg-slate-600" />
        <span className="font-medium text-slate-600">{momentum.recent_label}</span>
        <span className="tabular-nums text-slate-400">({momentum.recent_total} reviews)</span>
      </div>

      <div className="space-y-3.5">
        {momentum.items.map((it) => {
          const c = color(it.direction);
          const from = pos(it.earlier_share);
          const to = pos(it.recent_share);
          const left = Math.min(from, to);
          const width = Math.abs(to - from);
          return (
            <div key={it.label} className={GRID}>
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold text-slate-800" title={it.label}>
                  {it.label}
                </div>
                {/* Counts, not just shares: "5 → 3 mentions" makes thin evidence obvious in a
                    way that "16.7% → 7.1%" hides. */}
                <div className="mt-0.5 text-[11px] tabular-nums text-slate-400">
                  {it.earlier_count} <span className="text-slate-300">→</span>{" "}
                  <span className="font-semibold text-slate-600">{it.recent_count}</span> mentions
                </div>
              </div>

              <div
                className="relative h-5"
                title={`${it.label}: ${it.earlier_share}% (${it.earlier_count}) → ${it.recent_share}% (${it.recent_count})`}
              >
                {/* baseline */}
                <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-slate-100" />
                {/* the movement */}
                <div
                  className="absolute top-1/2 h-[5px] -translate-y-1/2 rounded-full"
                  style={{ left: `${left}%`, width: `${Math.max(width, 0.6)}%`, background: c, opacity: 0.35 }}
                />
                {/* earlier: hollow, recent: filled — direction reads without relying on colour */}
                <span
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full border-2 bg-white"
                  style={{ left: `${from}%`, marginLeft: -5, borderColor: c }}
                />
                <span
                  className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-white"
                  style={{ left: `${to}%`, marginLeft: -6, background: c }}
                />
              </div>

              <span
                className="flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold tabular-nums"
                style={{ color: c }}
              >
                {icon(it.direction)} {Math.abs(it.delta)} pts
                <span className="font-normal text-slate-400">{word(it.direction)}</span>
              </span>
            </div>
          );
        })}
      </div>

      {/* Axis: share of all analysed feedback, so the dots' positions are readable as sizes. */}
      <div className={`mt-2 ${GRID}`}>
        <div />
        <div className="flex justify-between text-[10px] tabular-nums text-slate-400">
          <span>0%</span>
          <span>{Math.round(maxShare)}% of feedback</span>
        </div>
        <div />
      </div>

      <p className="mt-3 border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-500">
        Each category's share of all analysed feedback in two consecutive windows of equal length.
        The hollow dot is the earlier window, the filled dot the recent one.{" "}
        <span style={{ color: NEGATIVE_MARK }} className="font-semibold">Rising</span> categories grow as a
        proportion of what customers raise;{" "}
        <span style={{ color: POSITIVE_MARK }} className="font-semibold">easing</span> ones shrink.
      </p>
    </div>
  );
}

/** Sentiment or rating over time.
 *
 * One measure, one axis — never both at once, which would need two scales and make the
 * crossing point meaningless. Periods whose sample was too small arrive as nulls and are
 * drawn as a break in the line with a hollow marker, so a quiet quarter reads as "not
 * measured" rather than as a value. Sample size is printed under every period, because the
 * whole reason this chart is conditional is that samples here are small. */
export function TrendChart({ trend }: { trend: TrendSeries }) {
  const useSentiment = trend.has_sentiment;
  const values = trend.points.map((p) => (useSentiment ? p.negative_pct : p.avg_rating) ?? null);
  const measured = values.filter((v): v is number => v != null);
  if (measured.length < 2) return null;

  const max = useSentiment ? Math.max(100, ...measured) : 5;
  const min = 0;
  const width = 100; // viewBox units; the SVG scales to its container
  const height = 42;
  const stepX = trend.points.length > 1 ? width / (trend.points.length - 1) : width;
  const toXY = (v: number, i: number) => ({
    x: i * stepX,
    y: height - ((v - min) / (max - min)) * height,
  });

  /* One <polyline> per unbroken run, so a gap is a real gap rather than a straight line
     drawn through a period we never measured. */
  const runs: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  values.forEach((v, i) => {
    if (v == null) {
      if (run.length) runs.push(run);
      run = [];
      return;
    }
    run.push(toXY(v, i));
  });
  if (run.length) runs.push(run);

  const first = measured[0];
  const last = measured[measured.length - 1];
  const delta = last - first;
  const worse = useSentiment ? delta > 0 : delta < 0;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[13px] font-bold text-slate-800">
          {useSentiment ? "Negative sentiment" : "Average rating"}
        </span>
        {Math.abs(delta) >= (useSentiment ? 1 : 0.05) && (
          <span
            className="text-[12px] font-semibold tabular-nums"
            style={{ color: worse ? NEGATIVE_MARK : POSITIVE_MARK }}
          >
            {worse ? "▲" : "▼"} {Math.abs(delta).toFixed(useSentiment ? 1 : 2)}
            {useSentiment ? " pts" : ""} since {trend.points[values.findIndex((v) => v != null)]?.label}
          </span>
        )}
      </div>

      <svg
        viewBox={`-2 -4 ${width + 4} ${height + 8}`}
        className="h-32 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`${useSentiment ? "Negative sentiment" : "Average rating"} by ${trend.granularity}`}
      >
        {[0, 0.5, 1].map((f) => (
          <line
            key={f}
            x1={0}
            x2={width}
            y1={height * f}
            y2={height * f}
            stroke="#e2e8f0"
            strokeWidth={0.3}
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {runs.map((points, i) => (
          <polyline
            key={i}
            points={points.map((p) => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke={useSentiment ? NEGATIVE_MARK : "#2a78d6"}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {values.map((v, i) =>
          v == null ? null : (
            <circle
              key={i}
              cx={toXY(v, i).x}
              cy={toXY(v, i).y}
              r={3}
              fill="#fff"
              stroke={useSentiment ? NEGATIVE_MARK : "#2a78d6"}
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          ),
        )}
      </svg>

      <div className="mt-1 flex">
        {trend.points.map((p, i) => (
          <div key={p.period} className="min-w-0 flex-1 text-center">
            <p className="truncate text-[10px] font-semibold text-slate-600">{p.label}</p>
            <p className="truncate text-[10px] tabular-nums text-slate-800">
              {values[i] != null
                ? useSentiment
                  ? `${values[i]}%`
                  : `${values[i]}`
                : <span className="text-slate-300">—</span>}
            </p>
            <p className="truncate text-[9px] tabular-nums text-slate-400">
              n={useSentiment ? p.classified_count : p.reviews}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Rating-vs-comment agreement. Reassurance when they align, a flag when they don't. */
export function RatingSentimentNote({ check }: { check: RatingSentimentCheck }) {
  const flagged = check.mismatch_pct >= 15;
  const parts: string[] = [];
  if (check.high_rating_negative > 0) {
    parts.push(`${check.high_rating_negative} rated 4–5★ but read negative`);
  }
  if (check.low_rating_positive > 0) {
    parts.push(`${check.low_rating_positive} rated 1–2★ but read positive`);
  }
  return (
    <div
      className={`pdf-block flex items-start gap-2.5 rounded-xl border px-4 py-3 ${
        flagged ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50/60"
      }`}
    >
      <ShieldCheck
        className={`mt-0.5 h-4 w-4 shrink-0 ${flagged ? "text-amber-600" : "text-slate-400"}`}
      />
      <p className="text-[12px] leading-relaxed text-slate-600">
        <span className="font-semibold text-slate-800">
          Stars and comments agree {(100 - check.mismatch_pct).toFixed(0)}% of the time
        </span>{" "}
        across the {check.both_count} reviews carrying both.
        {parts.length > 0 && (
          <>
            {" "}
            {flagged
              ? "That gap is wide enough to watch — "
              : "The few that diverge: "}
            {parts.join(", ")}
            {flagged ? ", which can signal rating inflation or review-gaming." : "."}
          </>
        )}
      </p>
    </div>
  );
}

export function RatingHistogram({ dist }: { dist: RatingDistribution }) {
  const rows: Array<[number, number]> = [
    [5, dist.five],
    [4, dist.four],
    [3, dist.three],
    [2, dist.two],
    [1, dist.one],
  ];
  const max = Math.max(...rows.map(([, n]) => n), 1);
  return (
    <div className="space-y-2">
      {rows.map(([star, n]) => (
        <div key={star} className="flex items-center gap-2.5">
          <span className="w-7 shrink-0 text-[12px] font-semibold tabular-nums text-slate-500">{star}★</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100">
            <div
              className="h-full rounded"
              style={{
                width: `${(n / max) * 100}%`,
                background: star >= 4 ? POSITIVE_MARK : star === 3 ? "#94a3b8" : NEGATIVE_MARK,
              }}
            />
          </div>
          <span className="w-9 shrink-0 text-right text-[12px] tabular-nums text-slate-500">{n}</span>
        </div>
      ))}
    </div>
  );
}

/** Rich per-channel card. Used instead of a table when there are few channels, where a
    one-row table reads as broken rather than informative. */
