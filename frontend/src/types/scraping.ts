// Mirrors backend/app/schemas/scraping.py

import type { ManualAnalysisWorkbook } from "./manual-analysis";

export interface ReviewClassification {
  sentiment: "positive" | "neutral" | "negative";
  confidence: number;
  themes: string[];
  complaint_category: string | null;
}

export interface ScrapedReview {
  platform: string;
  author: string | null;
  text: string;
  rating: number | null;
  date: string | null;
  url: string | null;
  classification?: ReviewClassification | null;
  /** Facebook only: "page" (official page comments) vs "keyword" (keyword-search mention). */
  source?: string | null;
}

export interface PlatformResult {
  platform: string;
  status: "success" | "error" | "empty";
  review_count: number;
  reviews: ScrapedReview[];
  error_message: string | null;
  summary_stat?: string | null;
  reply_rate_pct?: number | null;
  /** Real-world places the reviews came from, so the match can be verified. */
  matched_places?: string[];
  /** Places dropped for sitting outside the requested location. */
  excluded_places?: string[];
}

export interface TopicCount {
  topic: string;
  count: number;
}

export interface AnalysisSummary {
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
  top_themes: string[];
  top_complaints: TopicCount[];
  summary_text: string | null;
}

export interface CompanyOption {
  id: number;
  name: string;
}

/* ---------- Detailed merged social report ---------- */

export interface ChannelReportSection {
  channel: string;
  summary: string;
  strengths: string[];
  friction_points: string[];
  key_stats: string[];
}

export interface FrictionPoint {
  theme: string;
  source: "scraped" | "consultant" | "both" | string;
  description: string;
  supporting_evidence: string[];
  // Set server-side when the point maps to a counted label.
  related_label?: string | null;
  mention_count?: number | null;
  share_pct?: number | null;
}

/** A cross-channel strength, quantified from the same tables as the friction points.
 *  Older saved reports stored these as bare strings; the backend coerces them on load. */
export interface Strength {
  text: string;
  related_label?: string | null;
  mention_count?: number | null;
  share_pct?: number | null;
}

/** An action tied to the friction point it resolves, so its reach is visible. */
export interface Recommendation {
  text: string;
  /** `theme` of the friction point this addresses, once verified server-side. */
  addresses?: string | null;
  mention_count?: number | null;
  share_pct?: number | null;
}

export interface SentimentBreakdown {
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
  classified_count: number;
}

export interface PlatformSentiment {
  platform: string;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
  classified_count: number;
  review_count: number;
  avg_rating?: number | null;
  summary_stat?: string | null;
  reply_rate_pct?: number | null;
}

export interface RatingDistribution {
  one: number;
  two: number;
  three: number;
  four: number;
  five: number;
  total: number;
  average?: number | null;
}

export interface ThemeFrequency {
  label: string;
  count: number;
  share_pct: number;
  negative_pct: number;
  /** Which channels the mentions came from, e.g. { "Google Maps": 6, "Trustpilot": 2 }. */
  by_platform?: Record<string, number>;
}

export interface ThemeVerbatim {
  label: string;
  platform: string;
  text: string;
  rating?: number | null;
  date?: string | null;
  sentiment?: string | null;
  /** Link to the original review, so a quote can be opened at source. */
  url?: string | null;
  /** Facebook only: "page" vs "keyword". */
  source?: string | null;
}

/** Where the star rating and the written sentiment disagree — a rating-inflation signal. */
export interface RatingSentimentCheck {
  both_count: number;
  high_rating_negative: number;
  low_rating_positive: number;
  mismatch_count: number;
  mismatch_pct: number;
}

/** One period on the time axis. `negative_pct` / `avg_rating` are null when that period's
 *  sample is too small to state them — a break in the line, not an invented point. */
export interface TrendPoint {
  period: string;
  label: string;
  reviews: number;
  classified_count: number;
  negative_pct?: number | null;
  positive_pct?: number | null;
  neutral_pct?: number | null;
  avg_rating?: number | null;
}

/** Present only when the collected reviews can support a time axis at all. */
export interface TrendSeries {
  granularity: "month" | "quarter" | string;
  points: TrendPoint[];
  has_sentiment: boolean;
  has_rating: boolean;
  min_sample: number;
}

/** One complaint category's change in share between the earlier and recent windows.
 *  Shares are of all classified feedback in each window, so a rise means the category grew
 *  as a proportion of what customers talked about. */
export interface TopicMovement {
  label: string;
  earlier_count: number;
  recent_count: number;
  earlier_share: number;
  recent_share: number;
  delta: number;
  direction: "rising" | "falling" | "stable" | string;
}

/** Present only when each half of the history carries a real sample. */
export interface TopicMomentum {
  earlier_label: string;
  recent_label: string;
  earlier_total: number;
  recent_total: number;
  items: TopicMovement[];
}

/** Computed server-side in Python — never generated by the LLM. */
export interface ReportEvidence {
  reviews_collected: number;
  /** Reviews carrying a written comment; the rest are star-only ratings. */
  reviews_with_text: number;
  reviews_classified: number;
  overall_sentiment: SentimentBreakdown | null;
  platform_sentiment: PlatformSentiment[];
  rating_distribution: RatingDistribution | null;
  top_themes: ThemeFrequency[];
  top_complaints: ThemeFrequency[];
  verbatims: ThemeVerbatim[];
  /** Null when review volume per period is too thin to plot honestly. */
  trend?: TrendSeries | null;
  /** Which complaint categories are gaining or losing share; null when the history is thin. */
  momentum?: TopicMomentum | null;
  /** Reviews-weighted share of reviews the brand publicly replied to; null if unmeasured. */
  reply_rate_pct?: number | null;
  /** How many reviews that reply rate rests on. */
  reply_rate_base?: number;
  /** Rating-vs-comment disagreement; null when too few reviews carry both. */
  rating_sentiment?: RatingSentimentCheck | null;
}

export interface DetailedSocialReport {
  executive_summary: string;
  overall_sentiment: SentimentBreakdown | null;
  evidence?: ReportEvidence | null;
  channel_breakdown: ChannelReportSection[];
  top_strengths: Strength[];
  top_friction_points: FrictionPoint[];
  website_assessment: string | null;
  recommendations: Recommendation[];
  methodology_note: string;
}

export interface ScrapingResponse {
  brand_name: string;
  scraped_at: string;
  platforms: PlatformResult[];
  total_reviews: number;
  analysis?: AnalysisSummary | null;
  detailed_report?: DetailedSocialReport | null;
  /** The consultant's workbook, echoed back so a past report can be reopened and re-run. */
  manual_analysis?: ManualAnalysisWorkbook | null;
  /** The saved report's filename, used to address this report (e.g. its chatbot endpoint). */
  report_filename?: string | null;
  /** Persisted chat history for this report's assistant (loaded with the report). */
  chat_messages?: { id: string; role: string; text: string; sources?: string[]; ts?: number }[] | null;
  /** The inputs this run was launched with, so the form can be repopulated to correct a field
   *  and re-run. Absent on reports saved before the field was returned. */
  scrape_request?: {
    brand_name?: string;
    facebook_url?: string | null;
    instagram_url?: string | null;
    trustpilot_domain?: string | null;
    trustpilot_period?: string | null;
    google_location?: string | null;
    keywords?: string | null;
  } | null;
}

export interface PastReportItem {
  filename: string;
  brand_name: string;
  scraped_at: string;
  total_reviews: number;
  owned?: boolean;
}

export function sourceLabel(source: string): string {
  if (source === "scraped") return "Scraped reviews";
  if (source === "consultant") return "Manual analysis";
  if (source === "both") return "Both sources";
  return source;
}
