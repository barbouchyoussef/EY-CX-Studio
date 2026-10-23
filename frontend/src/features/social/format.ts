/**
 * Parsing and formatting helpers for the social report.
 *
 * Extracted from the report view. All pure, no React — each one exists because a value
 * arriving from a workbook or from a language model does not render correctly as-is, and the
 * comments record which real problem each was written for.
 */

import type { ChannelPost } from "../../types/manual-analysis";

/** Pull a headline count out of a free-text workbook metric ("1 015 052 (+1.8% MoM)"). */
export function parseCount(raw?: string | null): number | null {
  if (!raw) return null;
  // Workbook figures use thin / non-breaking spaces as thousand separators ("1 015 052").
  const match = raw.match(/[0-9][0-9\s.,']*/);
  if (!match) return null;
  const digits = match[0].replace(/\D/g, "");
  return digits ? Number(digits) : null;
}

/** Pull the period-over-period delta out of the same string ("+1.8%"). */
export function parseDelta(raw?: string | null): string | null {
  if (!raw) return null;
  const match = raw.match(/[+-]\s*[\d.,]+\s*%/);
  return match ? match[0].replace(/\s+/g, "") : null;
}

/**
 * Render a workbook percentage.
 *
 * Excel stores percent-formatted cells as fractions, so the template's "52%" bounce rate arrives
 * as the string "0.52" and printed raw it reads as half a percent. Values that already carry a %
 * sign are passed through untouched.
 */
export function formatPercent(raw?: string | null): string {
  if (!raw) return "—";
  const trimmed = raw.trim();
  if (trimmed.includes("%")) return trimmed;
  const n = Number(trimmed.replace(",", "."));
  if (!Number.isFinite(n)) return trimmed;
  const pct = n <= 1 ? n * 100 : n;
  return `${Number.isInteger(pct) ? pct : pct.toFixed(1)}%`;
}

/**
 * Is this "supporting evidence" a statistic rather than a customer quote?
 *
 * The report prompt lets `supporting_evidence` hold either a verbatim or a stat, and the model
 * routinely puts stats there ("1 occurrence, i.e. 10% of negative reviews", "89 opinions on 4G
 * congestion", "5 of [Staff and customer relations]"). Rendered inside quotation marks those read
 * as fabricated customer quotes, and the bracketed taxonomy labels are internal names that must
 * never reach a client. The volume they carry is already shown in the badge, so the line adds
 * nothing and is dropped.
 */
export function looksLikeStat(text: string): boolean {
  if (/\[[^\]]+\]/.test(text)) return true; // internal taxonomy label leaked
  return [
    /\bi\.e\.\b/i,
    /\bof (negative|classified|consolidated) (reviews|mentions)\b/i,
    /\(source:\s*consultant\)/i,
    /^\s*\d+\s+(occurrence|occurrences|opinion|opinions|mention|mentions)\b/i,
    /\bconsolidated mentions\b/i,
  ].some((re) => re.test(text));
}

/** Short human count for a KPI tile: 12 400 becomes "12.4k". */
export function compact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  return String(n);
}

/** Total engagement on a post, treating any missing metric as zero. */
export function postTotal(p: ChannelPost): number {
  return [p.likes, p.comments, p.shares].reduce((s: number, v) => s + (v ?? 0), 0);
}
