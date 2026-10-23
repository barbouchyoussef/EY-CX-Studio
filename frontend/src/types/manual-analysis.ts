// Mirrors backend/app/schemas/manual_analysis.py — the consultant-filled
// "Social Media & Website Analysis" workbook, whether produced by uploading the
// Excel template or filled directly through the in-app form.

export type ChannelName = "LinkedIn" | "Facebook" | "Instagram" | "X (ex Twitter)";

export const CHANNEL_NAMES: ChannelName[] = ["LinkedIn", "Facebook", "Instagram", "X (ex Twitter)"];

export type ChannelPost = {
  date: string | null;
  post: string | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  total_engagement: number | null;
  notes: string | null;
};

export type ChannelAnalysis = {
  channel: string;
  account_handle: string | null;
  followers_growth: string | null;
  page_verification: string | null;
  engagement_rate: string | null;
  post_interaction_rate: string | null;
  response_time_to_comments: string | null;
  response_quality: string | null;
  posting_frequency: string | null;
  content_format_variety: string | null;
  campaign: string | null;
  complaints_handling: string | null;
  resolution_effectiveness: string | null;
  sentiment_analysis: string | null;
  posts: ChannelPost[];
  avg_likes: number | null;
  avg_comments: number | null;
  avg_shares: number | null;
  avg_engagement: number | null;
  notes: string | null;
};

export type WebsiteTraffic = {
  total_visits: string | null;
  desktop_share: string | null;
  mobile_share: string | null;
  pages_per_visit: string | null;
  bounce_rate: string | null;
  avg_visit_duration: string | null;
};

export type WebsiteAnalysis = {
  url: string | null;
  sections: string[];
  traffic: WebsiteTraffic;
};

export type ThemeInsight = {
  theme: string;
  type: string | null;
  source: string | null;
  description: string | null;
  opinions_count: number | null;
  share_of_mentions: number | null;
  examples: string | null;
  interpretation: string | null;
};

export type ManualAnalysisWorkbook = {
  company_name: string | null;
  reporting_period: string | null;
  analyst: string | null;
  channels: ChannelAnalysis[];
  website: WebsiteAnalysis | null;
  themes: ThemeInsight[];
};

export type ManualAnalysisParseResponse = {
  workbook: ManualAnalysisWorkbook;
  warnings: string[];
};

export function emptyWorkbook(): ManualAnalysisWorkbook {
  return { company_name: null, reporting_period: null, analyst: null, channels: [], website: null, themes: [] };
}

export function emptyChannel(channel: string): ChannelAnalysis {
  return {
    channel,
    account_handle: null,
    followers_growth: null,
    page_verification: null,
    engagement_rate: null,
    post_interaction_rate: null,
    response_time_to_comments: null,
    response_quality: null,
    posting_frequency: null,
    content_format_variety: null,
    campaign: null,
    complaints_handling: null,
    resolution_effectiveness: null,
    sentiment_analysis: null,
    posts: [],
    avg_likes: null,
    avg_comments: null,
    avg_shares: null,
    avg_engagement: null,
    notes: null,
  };
}

export function emptyPost(): ChannelPost {
  return { date: null, post: null, likes: null, comments: null, shares: null, total_engagement: null, notes: null };
}

export function emptyTheme(): ThemeInsight {
  return {
    theme: "",
    type: null,
    source: null,
    description: null,
    opinions_count: null,
    share_of_mentions: null,
    examples: null,
    interpretation: null,
  };
}

export function emptyWebsite(): WebsiteAnalysis {
  return {
    url: null,
    sections: [],
    traffic: {
      total_visits: null,
      desktop_share: null,
      mobile_share: null,
      pages_per_visit: null,
      bounce_rate: null,
      avg_visit_duration: null,
    },
  };
}

/** Recomputes total_engagement per post and the channel-level averages, mirroring the
 * backend parser's logic, so form-entered data matches uploaded-workbook data exactly. */
export function recomputeChannelAverages(channel: ChannelAnalysis): ChannelAnalysis {
  const posts = channel.posts.map((p) => ({
    ...p,
    total_engagement: [p.likes, p.comments, p.shares].reduce((sum: number, v) => sum + (v ?? 0), 0),
  }));
  const avg = (values: (number | null)[]): number | null => {
    const present = values.filter((v): v is number => v !== null && v !== undefined);
    if (present.length === 0) return null;
    return Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 100) / 100;
  };
  return {
    ...channel,
    posts,
    avg_likes: avg(posts.map((p) => p.likes)),
    avg_comments: avg(posts.map((p) => p.comments)),
    avg_shares: avg(posts.map((p) => p.shares)),
    avg_engagement: avg(posts.map((p) => p.total_engagement)),
  };
}

/** Strips form-editing scaffolding (padding blanks, empty rows) before the workbook is sent to the backend. */
export function cleanWorkbookForSubmit(wb: ManualAnalysisWorkbook): ManualAnalysisWorkbook {
  return {
    ...wb,
    website: wb.website ? { ...wb.website, sections: wb.website.sections.filter((s) => !!s && s.trim() !== "") } : null,
    themes: wb.themes.filter((t) => !!t.theme && t.theme.trim() !== ""),
  };
}

/** Recomputes each theme's share_of_mentions from the opinions_count values, mirroring the backend parser. */
export function recomputeThemeShares(themes: ThemeInsight[]): ThemeInsight[] {
  const total = themes.reduce((sum, t) => sum + (t.opinions_count ?? 0), 0);
  if (total <= 0) return themes.map((t) => ({ ...t, share_of_mentions: null }));
  return themes.map((t) => ({
    ...t,
    share_of_mentions: t.opinions_count ? Math.round((t.opinions_count / total) * 1000) / 1000 : null,
  }));
}
