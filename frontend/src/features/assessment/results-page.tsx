import type { ReactNode } from "react";

type FinalReport = {
  assessment_id: number;
  hero: {
    report_title: string;
    report_date_label?: string | null;
    company_name?: string | null;
    sector_name?: string | null;
    region?: string | null;
    overall_level?: number | null;
    overall_level_label?: string | null;
    overall_maturity_band: string;
    hero_message?: string | null;
    strongest_axis?: string | null;
    strongest_axis_level?: number | null;
    strongest_axis_level_label?: string | null;
    strongest_axis_description?: string | null;
    priority_axis?: string | null;
    priority_axis_level?: number | null;
    priority_axis_level_label?: string | null;
    priority_axis_description?: string | null;
  };
  summary: {
    overall_score_percent: number;
    overall_maturity_band: string;
    strongest_axis: string;
    strongest_axis_score_percent: number;
    priority_axis: string;
    priority_axis_score_percent: number;
    strengths_count: number;
    pain_points_count: number;
    executive_summary_text?: string | null;
    priority_message_text?: string | null;
  };
  axes: { axis: string; score_percent: number; maturity_band: string }[];
  strengths: { axis: string; capability: string; maturity_band: string; rationale?: string | null; recommendation?: string | null; priority?: string | null }[];
  pain_points: { axis: string; capability: string; maturity_band: string; rationale?: string | null; recommendation?: string | null; priority?: string | null }[];
  capabilities: { axis: string; capability: string; maturity_band: string; rationale?: string | null; recommendation?: string | null; priority?: string | null; confidence?: number | null }[];
  benchmarks: { title: string; url: string; site_name?: string | null; published_at?: string | null; summary?: string | null; method_signal?: string | null }[];
};

type Props = {
  report: FinalReport;
  onBack: () => void;
  companyName?: string | null;
  heroSlot?: ReactNode;
  sectionsSlot?: ReactNode;
};

export default function AssessmentResultsPage({ heroSlot, sectionsSlot }: Props) {
  return (
    <div
      className="min-h-screen print:bg-white print:px-0 print:py-0"
      style={{
        background: "linear-gradient(118deg, #121318 0%, #17315f 34%, #2a29a7 68%, #491fd8 100%)",
      }}
    >
      <div>{heroSlot ?? null}</div>
      <div>{sectionsSlot ?? null}</div>
    </div>
  );
}
