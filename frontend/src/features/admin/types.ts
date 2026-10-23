/**
 * The shapes the admin API returns.
 *
 * Split out of `dashboard.tsx` so `use-admin-data.ts` can load them and the dashboard can
 * render them without either owning the definitions.
 */

export type ViewKey =
  | "analytics"
  | "history"
  | "sectors"
  | "sizes"
  | "regions"
  | "axes"
  | "levels"
  | "capabilities"
  | "rubrics"
  | "recommendations";

export type SortKey = string;

export type Sector = { id: number; code: string; name: string };
export type CompanySize = { id: number; code: string; name: string };
export type Region = { id: number; name: string };
export type Axis = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  question_guidelines: string | null;
  sort_order: number;
};
export type MaturityLevel = {
  id: number;
  level_number: number;
  label: string;
  description: string | null;
};
export type Capability = {
  id: number;
  axis_id: number;
  code: string;
  name: string;
  description: string | null;
  evidence_required: string | null;
  question_guidelines: string | null;
  sort_order: number;
};
export type Rubric = {
  id: number;
  capability_id: number;
  maturity_level_id: number;
  description: string;
};
export type QuickWinTemplate = {
  id: number;
  capability_id: number;
  maturity_level_id: number;
  quick_win_guideline: string;
  after_text: string | null;
  owner_hint: string | null;
  timeline_hint: string | null;
  active: boolean;
};
export type AssessmentItem = {
  id: number;
  status: string;
  company_name: string;
  sector: string;
  size: string;
  region?: string | null;
  created_at: string;
};
export type MetabaseEmbedPayload = {
  enabled: boolean;
  url?: string | null;
  token?: string | null;
  instance_url?: string | null;
};
