import { Fragment, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { BRAND } from "../../lib/brand";
import {
  CHANNEL_NAMES,
  emptyChannel,
  emptyPost,
  emptyTheme,
  emptyWebsite,
  recomputeChannelAverages,
  recomputeThemeShares,
} from "../../types/manual-analysis";
import type {
  ChannelAnalysis,
  ChannelPost,
  ManualAnalysisWorkbook,
  ThemeInsight,
  WebsiteTraffic,
} from "../../types/manual-analysis";

type Props = {
  value: ManualAnalysisWorkbook;
  onChange: (next: ManualAnalysisWorkbook) => void;
};

/* ------------------------------------------------------------------ */
/*  Spreadsheet primitives                                             */
/*  The consultant fills the same data in Excel, so the form mirrors   */
/*  a worksheet: sheet tabs, a header row, bordered cells and a row    */
/*  gutter. Inputs are borderless until focused, the way a cell is.    */
/* ------------------------------------------------------------------ */
const GOLD = BRAND.gold;

const CELL =
  "w-full bg-transparent px-2.5 py-2 text-xs text-slate-800 placeholder-slate-300 outline-none transition " +
  "focus:bg-ey-gold/[0.07] focus:ring-2 focus:ring-inset focus:ring-ey-gold/40";

function CellInput({
  value,
  onChange,
  placeholder,
  align = "left",
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  placeholder?: string;
  align?: "left" | "right";
}) {
  return (
    <input
      type="text"
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      className={`${CELL} ${align === "right" ? "text-right" : ""}`}
    />
  );
}

function CellNumber({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <input
      type="number"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      className={`${CELL} text-right tabular-nums`}
    />
  );
}

function CellTextArea({
  value,
  onChange,
  placeholder,
  rows = 2,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      value={value ?? ""}
      placeholder={placeholder}
      rows={rows}
      onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      className={`${CELL} resize-y leading-relaxed`}
    />
  );
}

function CellSelect({
  value,
  options,
  onChange,
}: {
  value: string | null;
  options: string[];
  onChange: (v: string | null) => void;
}) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className={`${CELL} cursor-pointer`}
    >
      <option value="">—</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

/** Column header cell. */
function Th({
  children,
  width,
  align = "left",
  note,
}: {
  children: React.ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
  /** Tiny qualifier, e.g. "auto" on a column the form calculates rather than accepts. */
  note?: string;
}) {
  return (
    <th
      style={width ? { width, minWidth: width } : undefined}
      className={`border border-slate-300 bg-slate-100 px-2.5 py-2 text-[10px] font-bold uppercase tracking-wide text-slate-600 text-${align}`}
    >
      {children}
      {note && <span className="ml-1 font-normal normal-case tracking-normal text-slate-400">{note}</span>}
    </th>
  );
}

/** Row-number gutter cell, as in a spreadsheet. */
function RowNum({ n }: { n: number }) {
  return (
    <td className="w-9 border border-slate-300 bg-slate-50 text-center text-[10px] font-semibold text-slate-400">
      {n}
    </td>
  );
}

/** A titled block standing in for one Excel sheet region. */
function SheetSection({
  title,
  hint,
  right,
  children,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2.5">
          <span className="h-3 w-1 rounded-full" style={{ backgroundColor: GOLD }} />
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-700">{title}</h4>
          {hint && <span className="text-[11px] text-slate-400">{hint}</span>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Channel sheet                                                      */
/* ------------------------------------------------------------------ */
type MetricField = { key: keyof ChannelAnalysis; label: string; placeholder: string };
type MetricGroup = { group: string; fields: MetricField[] };

// Grouped exactly as the workbook groups them, and all of them visible: a 12-row table is
// easier to scan than five fields plus a "show more" toggle hiding the other seven.
const METRIC_GROUPS: MetricGroup[] = [
  {
    group: "Account performance",
    fields: [
      { key: "followers_growth", label: "Followers & growth", placeholder: "9 000 (+3% MoM)" },
      { key: "page_verification", label: "Page verification", placeholder: "Verified / Not verified" },
    ],
  },
  {
    group: "Engagement",
    fields: [
      { key: "engagement_rate", label: "Engagement rate", placeholder: "2.4%" },
      { key: "post_interaction_rate", label: "Post interaction rate", placeholder: "0.33%" },
      { key: "response_time_to_comments", label: "Response time to comments", placeholder: "< 24h" },
      { key: "response_quality", label: "Response quality", placeholder: "Personalised / Generic" },
    ],
  },
  {
    group: "Content strategy",
    fields: [
      { key: "posting_frequency", label: "Posting frequency", placeholder: "1.2 posts/day" },
      { key: "content_format_variety", label: "Content format variety", placeholder: "Image, Video, Story" },
      { key: "campaign", label: "Active campaign", placeholder: "Yes – #SummerPromo" },
    ],
  },
  {
    group: "Customer support",
    fields: [
      { key: "complaints_handling", label: "Complaints handling", placeholder: "Responsive within 24h" },
      { key: "resolution_effectiveness", label: "Resolution effectiveness", placeholder: "Effective / Limited" },
    ],
  },
  {
    group: "Brand perception",
    fields: [
      { key: "sentiment_analysis", label: "Overall sentiment", placeholder: "70% Pos / 20% Neu / 10% Neg" },
    ],
  },
];

const ALL_METRIC_FIELDS = METRIC_GROUPS.flatMap((g) => g.fields);

function channelHasData(channel: ChannelAnalysis): boolean {
  return (
    !!channel.account_handle ||
    !!channel.notes ||
    channel.posts.length > 0 ||
    ALL_METRIC_FIELDS.some((f) => !!channel[f.key])
  );
}

function MetricsTable({ channel, onChange }: { channel: ChannelAnalysis; onChange: (c: ChannelAnalysis) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse">
        <thead>
          <tr>
            <Th width="38%">Metric</Th>
            <Th>Value</Th>
          </tr>
        </thead>
        <tbody>
          {METRIC_GROUPS.map((group) => (
            // The group header and its rows are siblings in one <tbody>, so the key belongs
            // on the Fragment rather than on the first <tr>.
            <Fragment key={group.group}>
              <tr>
                <td
                  colSpan={2}
                  className="border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-500"
                >
                  {group.group}
                </td>
              </tr>
              {group.fields.map((f) => (
                <tr key={String(f.key)} className="hover:bg-slate-50/60">
                  <td className="border border-slate-200 px-2.5 py-2 text-xs font-medium text-slate-600">
                    {f.label}
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellInput
                      value={channel[f.key] as string | null}
                      placeholder={f.placeholder}
                      onChange={(v) => onChange({ ...channel, [f.key]: v })}
                    />
                  </td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PostLogTable({ channel, onChange }: { channel: ChannelAnalysis; onChange: (c: ChannelAnalysis) => void }) {
  const setPosts = (posts: ChannelPost[]) => onChange(recomputeChannelAverages({ ...channel, posts }));
  const patch = (idx: number, post: ChannelPost) =>
    setPosts(channel.posts.map((existing, i) => (i === idx ? post : existing)));
  const total = (p: ChannelPost) => [p.likes, p.comments, p.shares].reduce((s: number, v) => s + (v ?? 0), 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse">
        <thead>
          <tr>
            <Th width="36px" align="center">
              #
            </Th>
            <Th width="110px">Date</Th>
            <Th width="24%">Post / campaign</Th>
            <Th width="80px" align="right">
              Likes
            </Th>
            <Th width="90px" align="right">
              Comments
            </Th>
            <Th width="80px" align="right">
              Shares
            </Th>
            <Th width="90px" align="right" note="auto">
              Total
            </Th>
            <Th>Notes</Th>
            <Th width="40px" align="center">
              <span className="sr-only">Remove</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {channel.posts.map((post, idx) => (
            <tr key={idx} className="hover:bg-slate-50/60">
              <RowNum n={idx + 1} />
              <td className="border border-slate-200 p-0">
                <CellInput value={post.date} placeholder="2026-05-01" onChange={(v) => patch(idx, { ...post, date: v })} />
              </td>
              <td className="border border-slate-200 p-0">
                <CellInput value={post.post} placeholder="Post title" onChange={(v) => patch(idx, { ...post, post: v })} />
              </td>
              <td className="border border-slate-200 p-0">
                <CellNumber value={post.likes} onChange={(v) => patch(idx, { ...post, likes: v })} />
              </td>
              <td className="border border-slate-200 p-0">
                <CellNumber value={post.comments} onChange={(v) => patch(idx, { ...post, comments: v })} />
              </td>
              <td className="border border-slate-200 p-0">
                <CellNumber value={post.shares} onChange={(v) => patch(idx, { ...post, shares: v })} />
              </td>
              {/* Computed, like a formula column -- never typed by hand. */}
              <td className="border border-slate-200 bg-slate-50/70 px-2.5 py-2 text-right text-xs font-semibold tabular-nums text-slate-600">
                {total(post) || "—"}
              </td>
              <td className="border border-slate-200 p-0">
                <CellInput value={post.notes} onChange={(v) => patch(idx, { ...post, notes: v })} />
              </td>
              <td className="border border-slate-200 text-center">
                <button
                  type="button"
                  onClick={() => setPosts(channel.posts.filter((_, i) => i !== idx))}
                  className="rounded p-1 text-slate-300 transition hover:bg-rose-50 hover:text-rose-600"
                  title="Remove row"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </td>
            </tr>
          ))}
          {channel.posts.length === 0 && (
            <tr>
              <td colSpan={9} className="border border-slate-200 px-3 py-5 text-center text-[11px] italic text-slate-400">
                No posts recorded — add rows only if you tracked individual posts.
              </td>
            </tr>
          )}
          {channel.posts.length > 0 && (
            <tr className="bg-slate-50">
              <td className="border border-slate-300" />
              <td
                colSpan={2}
                className="border border-slate-300 px-2.5 py-2 text-[10px] font-bold uppercase tracking-wide text-slate-500"
              >
                Average
              </td>
              <td className="border border-slate-300 px-2.5 py-2 text-right text-xs font-semibold tabular-nums text-slate-600">
                {channel.avg_likes ?? "—"}
              </td>
              <td className="border border-slate-300 px-2.5 py-2 text-right text-xs font-semibold tabular-nums text-slate-600">
                {channel.avg_comments ?? "—"}
              </td>
              <td className="border border-slate-300 px-2.5 py-2 text-right text-xs font-semibold tabular-nums text-slate-600">
                {channel.avg_shares ?? "—"}
              </td>
              <td className="border border-slate-300 px-2.5 py-2 text-right text-xs font-bold tabular-nums text-slate-700">
                {channel.avg_engagement ?? "—"}
              </td>
              <td className="border border-slate-300" colSpan={2} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ChannelSheet({ channel, onChange }: { channel: ChannelAnalysis; onChange: (c: ChannelAnalysis) => void }) {
  return (
    <div className="space-y-6">
      <SheetSection title="Account">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse">
            <tbody>
              <tr>
                <td className="w-[38%] border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-600">
                  Account handle / URL
                </td>
                <td className="border border-slate-200 p-0">
                  <CellInput
                    value={channel.account_handle}
                    placeholder={`${channel.channel.toLowerCase().replace(/[^a-z]/g, "")}.com/yourbrand`}
                    onChange={(v) => onChange({ ...channel, account_handle: v })}
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SheetSection>

      <SheetSection title="Metrics">
        <MetricsTable channel={channel} onChange={onChange} />
      </SheetSection>

      <SheetSection
        title="Post log"
        hint={channel.posts.length > 0 ? `${channel.posts.length} rows` : "optional"}
        right={
          <button
            type="button"
            onClick={() => onChange(recomputeChannelAverages({ ...channel, posts: [...channel.posts, emptyPost()] }))}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:border-ey-gold/50 hover:text-slate-900"
          >
            <Plus className="h-3.5 w-3.5" /> Add row
          </button>
        }
      >
        <PostLogTable channel={channel} onChange={onChange} />
      </SheetSection>

      <SheetSection title="Summary notes" hint="Recurring themes, notable posts, campaigns">
        <div className="rounded border border-slate-200">
          <CellTextArea
            value={channel.notes}
            rows={4}
            placeholder="Strengths, weaknesses, recurring comment themes…"
            onChange={(v) => onChange({ ...channel, notes: v })}
          />
        </div>
      </SheetSection>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Website sheet                                                      */
/* ------------------------------------------------------------------ */
function websiteHasData(value: ManualAnalysisWorkbook): boolean {
  const w = value.website;
  if (!w) return false;
  return !!w.url || w.sections.some((s) => !!s) || Object.values(w.traffic).some((v) => !!v);
}

const TRAFFIC_ROWS: { key: keyof WebsiteTraffic; label: string; placeholder: string }[] = [
  { key: "total_visits", label: "Total visits (period)", placeholder: "1 245 000" },
  { key: "desktop_share", label: "Desktop share", placeholder: "32%" },
  { key: "mobile_share", label: "Mobile share", placeholder: "68%" },
  { key: "pages_per_visit", label: "Pages per visit", placeholder: "3.2" },
  { key: "bounce_rate", label: "Bounce rate", placeholder: "52%" },
  { key: "avg_visit_duration", label: "Avg. visit duration", placeholder: "00:02:45" },
];

function WebsiteSheet({ value, onChange }: { value: ManualAnalysisWorkbook; onChange: (v: ManualAnalysisWorkbook) => void }) {
  const website = value.website ?? emptyWebsite();
  const sections = website.sections;

  const patch = (p: Partial<typeof website>) => onChange({ ...value, website: { ...website, ...p } });
  const patchTraffic = (p: Partial<typeof website.traffic>) =>
    onChange({ ...value, website: { ...website, traffic: { ...website.traffic, ...p } } });

  return (
    <div className="space-y-6">
      <SheetSection title="Site">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse">
            <tbody>
              <tr>
                <td className="w-[38%] border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-600">
                  Website URL
                </td>
                <td className="border border-slate-200 p-0">
                  <CellInput value={website.url} placeholder="acmebank.com" onChange={(v) => patch({ url: v })} />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SheetSection>

      <SheetSection
        title="Main sections"
        hint="Top-level navigation"
        right={
          <button
            type="button"
            onClick={() => patch({ sections: [...sections, ""] })}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:border-ey-gold/50 hover:text-slate-900"
          >
            <Plus className="h-3.5 w-3.5" /> Add section
          </button>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] border-collapse">
            <thead>
              <tr>
                <Th width="36px" align="center">
                  #
                </Th>
                <Th>Section name</Th>
                <Th width="40px" align="center">
                  <span className="sr-only">Remove</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {sections.map((s, i) => (
                <tr key={i} className="hover:bg-slate-50/60">
                  <RowNum n={i + 1} />
                  <td className="border border-slate-200 p-0">
                    <CellInput
                      value={s}
                      placeholder="e.g. Gaming"
                      onChange={(v) => {
                        const next = [...sections];
                        next[i] = v ?? "";
                        patch({ sections: next });
                      }}
                    />
                  </td>
                  <td className="border border-slate-200 text-center">
                    <button
                      type="button"
                      onClick={() => patch({ sections: sections.filter((_, j) => j !== i) })}
                      className="rounded p-1 text-slate-300 transition hover:bg-rose-50 hover:text-rose-600"
                      title="Remove row"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {sections.length === 0 && (
                <tr>
                  <td colSpan={3} className="border border-slate-200 px-3 py-5 text-center text-[11px] italic text-slate-400">
                    No sections recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SheetSection>

      <SheetSection title="Traffic analytics" hint="From the client's analytics tool">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse">
            <thead>
              <tr>
                <Th width="38%">Metric</Th>
                <Th>Value</Th>
              </tr>
            </thead>
            <tbody>
              {TRAFFIC_ROWS.map((row) => (
                <tr key={row.key} className="hover:bg-slate-50/60">
                  <td className="border border-slate-200 px-2.5 py-2 text-xs font-medium text-slate-600">{row.label}</td>
                  <td className="border border-slate-200 p-0">
                    <CellInput
                      value={website.traffic[row.key] ?? null}
                      placeholder={row.placeholder}
                      onChange={(v) => patchTraffic({ [row.key]: v } as Partial<WebsiteTraffic>)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SheetSection>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Themes & Insights sheet                                            */
/* ------------------------------------------------------------------ */
const THEME_SOURCE_OPTIONS: string[] = [...CHANNEL_NAMES, "Website"];

function ThemesSheet({ value, onChange }: { value: ManualAnalysisWorkbook; onChange: (v: ManualAnalysisWorkbook) => void }) {
  const setThemes = (themes: ThemeInsight[]) => onChange({ ...value, themes: recomputeThemeShares(themes) });
  const patch = (idx: number, theme: ThemeInsight) =>
    setThemes(value.themes.map((existing, i) => (i === idx ? theme : existing)));

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-slate-500">
        Recurring customer themes consolidated across channels. These become the strengths and friction points in the
        report, ranked by the number of opinions behind each one.
      </p>

      <SheetSection
        title="Themes & insights"
        hint={value.themes.length > 0 ? `${value.themes.length} rows` : undefined}
        right={
          <button
            type="button"
            onClick={() => setThemes([...value.themes, emptyTheme()])}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:border-ey-gold/50 hover:text-slate-900"
          >
            <Plus className="h-3.5 w-3.5" /> Add row
          </button>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1080px] border-collapse">
            <thead>
              <tr>
                <Th width="36px" align="center">
                  #
                </Th>
                <Th width="170px">Theme</Th>
                <Th width="130px">Type</Th>
                <Th width="130px">Source</Th>
                <Th width="80px" align="right">
                  Opinions
                </Th>
                <Th width="80px" align="right" note="auto">
                  Share
                </Th>
                <Th width="220px">Description</Th>
                <Th width="220px">Representative quotes</Th>
                <Th width="220px">Interpretation</Th>
                <Th width="40px" align="center">
                  <span className="sr-only">Remove</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {value.themes.map((theme, idx) => (
                <tr key={idx} className="align-top hover:bg-slate-50/60">
                  <RowNum n={idx + 1} />
                  <td className="border border-slate-200 p-0">
                    <CellInput
                      value={theme.theme}
                      placeholder="Delivery delays"
                      onChange={(v) => patch(idx, { ...theme, theme: v ?? "" })}
                    />
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellSelect
                      value={theme.type}
                      options={["Friction point", "Like"]}
                      onChange={(v) => patch(idx, { ...theme, type: v })}
                    />
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellSelect
                      value={theme.source}
                      options={THEME_SOURCE_OPTIONS}
                      onChange={(v) => patch(idx, { ...theme, source: v })}
                    />
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellNumber
                      value={theme.opinions_count}
                      onChange={(v) => patch(idx, { ...theme, opinions_count: v })}
                    />
                  </td>
                  {/* Computed from the opinion counts across all rows, like a formula column. */}
                  <td className="border border-slate-200 bg-slate-50/70 px-2.5 py-2 text-right text-xs font-semibold tabular-nums text-slate-600">
                    {theme.share_of_mentions != null ? `${Math.round(theme.share_of_mentions * 100)}%` : "—"}
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellTextArea
                      value={theme.description}
                      placeholder="The observed pattern"
                      onChange={(v) => patch(idx, { ...theme, description: v })}
                    />
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellTextArea
                      value={theme.examples}
                      placeholder="Verbatim customer comments"
                      onChange={(v) => patch(idx, { ...theme, examples: v })}
                    />
                  </td>
                  <td className="border border-slate-200 p-0">
                    <CellTextArea
                      value={theme.interpretation}
                      placeholder="Implication and recommended focus"
                      onChange={(v) => patch(idx, { ...theme, interpretation: v })}
                    />
                  </td>
                  <td className="border border-slate-200 text-center">
                    <button
                      type="button"
                      onClick={() => setThemes(value.themes.filter((_, i) => i !== idx))}
                      className="rounded p-1 text-slate-300 transition hover:bg-rose-50 hover:text-rose-600"
                      title="Remove row"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {value.themes.length === 0 && (
                <tr>
                  <td colSpan={10} className="border border-slate-200 px-3 py-6 text-center text-[11px] italic text-slate-400">
                    No themes recorded. Add a row to start.
                  </td>
                </tr>
              )}
              {value.themes.length > 0 && (
                <tr className="bg-slate-50">
                  <td className="border border-slate-300" />
                  <td colSpan={3} className="border border-slate-300 px-2.5 py-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                    Total
                  </td>
                  <td className="border border-slate-300 px-2.5 py-2 text-right text-xs font-bold tabular-nums text-slate-700">
                    {value.themes.reduce((s, t) => s + (t.opinions_count ?? 0), 0) || "—"}
                  </td>
                  <td className="border border-slate-300" colSpan={5} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SheetSection>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Root — workbook header + sheet tabs                                */
/* ------------------------------------------------------------------ */
export default function ManualAnalysisForm({ value, onChange }: Props) {
  const [activeTab, setActiveTab] = useState<string>("Themes & Insights");

  const activeChannelNames = new Set(value.channels.map((c) => c.channel));

  const addChannel = (name: string) => {
    onChange({ ...value, channels: [...value.channels, emptyChannel(name)] });
    setActiveTab(name);
  };

  const removeChannel = (name: string) => {
    onChange({ ...value, channels: value.channels.filter((c) => c.channel !== name) });
    if (activeTab === name) setActiveTab("Themes & Insights");
  };

  const tabs: { key: string; label: string; hasData: boolean }[] = [
    ...value.channels.map((c) => ({ key: c.channel, label: c.channel, hasData: channelHasData(c) })),
    { key: "Website", label: "Website", hasData: websiteHasData(value) },
    {
      key: "Themes & Insights",
      label: `Themes & Insights${value.themes.length > 0 ? ` (${value.themes.length})` : ""}`,
      hasData: value.themes.length > 0,
    },
  ];

  const activeChannel = value.channels.find((c) => c.channel === activeTab);

  return (
    <div className="space-y-4">
      {/* One orienting line, so the optionality does not need repeating on every section. */}
      <p className="text-[11px] leading-relaxed text-slate-500">
        Same structure as the Excel template — one sheet per channel, plus Website and Themes.
        Every field is optional: leave blank anything you did not measure.
      </p>

      {/* Workbook header — mirrors the template's "Read Me" sheet */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-[480px] border-collapse">
          <tbody>
            <tr>
              <td className="w-[30%] border-b border-r border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-600">
                Reporting period
              </td>
              <td className="border-b border-slate-200 p-0">
                <CellInput
                  value={value.reporting_period}
                  placeholder="Q2 2026 (April – June)"
                  onChange={(v) => onChange({ ...value, reporting_period: v })}
                />
              </td>
            </tr>
            <tr>
              <td className="w-[30%] border-r border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-600">
                Analyst
              </td>
              <td className="p-0">
                <CellInput
                  value={value.analyst}
                  placeholder="Your name"
                  onChange={(v) => onChange({ ...value, analyst: v })}
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Channel picker — which sheets exist in this workbook */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Channels</span>
        <span className="text-[11px] text-slate-400">Add a sheet for each one you analysed</span>
        {CHANNEL_NAMES.map((name) => {
          const active = activeChannelNames.has(name);
          return (
            <button
              key={name}
              type="button"
              onClick={() => (active ? removeChannel(name) : addChannel(name))}
              className={`rounded-full border px-3.5 py-1.5 text-[11px] font-semibold transition ${
                active
                  ? "border-ey-gold/50 bg-ey-gold/10 text-slate-800"
                  : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
              }`}
            >
              {active ? "✓ " : "+ "}
              {name}
            </button>
          );
        })}
      </div>

      {/* Sheet tabs + the active sheet, styled as a workbook */}
      <div>
        <div className="flex flex-wrap items-end gap-1 border-b border-slate-300">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`-mb-px inline-flex items-center gap-1.5 rounded-t-lg border px-3.5 py-2 text-[11px] font-semibold transition ${
                  isActive
                    ? "border-slate-300 border-b-white bg-white text-slate-900"
                    : "border-transparent bg-slate-100/70 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                }`}
              >
                {tab.hasData && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="rounded-b-xl rounded-tr-xl border border-t-0 border-slate-300 bg-white p-5">
          {activeTab === "Website" ? (
            <WebsiteSheet value={value} onChange={onChange} />
          ) : activeTab === "Themes & Insights" ? (
            <ThemesSheet value={value} onChange={onChange} />
          ) : activeChannel ? (
            <ChannelSheet
              channel={activeChannel}
              onChange={(c) =>
                onChange({
                  ...value,
                  channels: value.channels.map((existing) => (existing.channel === c.channel ? c : existing)),
                })
              }
            />
          ) : (
            <p className="text-xs text-slate-400">Select a channel above to add its sheet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
