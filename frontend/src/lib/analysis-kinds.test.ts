/**
 * The labels for the four analysis kinds and the pipeline steps.
 *
 * Shared domain vocabulary: a project attaches these, the issue log consolidates them, sharing
 * grants access to them. The case that matters is an unrecognised kind, which must render as
 * itself rather than blank -- a module added without a label should be visibly wrong, not
 * silently invisible.
 */

import { describe, expect, it } from "vitest";

import {
  ANALYSIS_KIND_LABELS,
  STEP_LABELS,
  analysisKindLabel,
  stepLabel,
  type AnalysisKindName,
} from "./analysis-kinds";

const KINDS: AnalysisKindName[] = [
  "assessment",
  "interview_guide",
  "desk_session",
  "social_report",
];

describe("analysisKindLabel", () => {
  it.each(KINDS)("has English and French, short and long, for %s", (kind) => {
    for (const french of [false, true]) {
      for (const length of ["short", "long"] as const) {
        const label = analysisKindLabel(kind, french, length);
        expect(label.trim()).not.toBe("");
        expect(label).not.toBe(kind); // the raw key is the fallback, not a real label
      }
    }
  });

  it("defaults to the long form", () => {
    expect(analysisKindLabel("assessment", false)).toBe(
      ANALYSIS_KIND_LABELS.assessment.long.en,
    );
  });

  it("distinguishes short from long where the UI needs it", () => {
    // A step chip has room for "Assessment"; a row saying what a project holds does not.
    expect(analysisKindLabel("assessment", false, "short")).toBe("Assessment");
    expect(analysisKindLabel("assessment", false, "long")).toBe("Maturity assessment");
  });

  it("falls back to the raw key for an unknown kind", () => {
    expect(analysisKindLabel("brand_audit", false)).toBe("brand_audit");
    expect(analysisKindLabel("brand_audit", true)).toBe("brand_audit");
  });
});

describe("stepLabel", () => {
  it.each(Object.keys(STEP_LABELS))("has both languages for %s", (step) => {
    expect(stepLabel(step, false).trim()).not.toBe("");
    expect(stepLabel(step, true).trim()).not.toBe("");
  });

  it("falls back to the raw key for an unknown step", () => {
    expect(stepLabel("nonexistent", false)).toBe("nonexistent");
  });

  it("reuses the kind labels so the two vocabularies cannot drift", () => {
    expect(STEP_LABELS.assessment).toBe(ANALYSIS_KIND_LABELS.assessment.short);
    expect(STEP_LABELS.interview).toBe(ANALYSIS_KIND_LABELS.interview_guide.short);
  });

  it("covers every pipeline step, including the one that produces no analysis", () => {
    // The issue log is a step that consumes the others, so it has a label but no kind.
    expect(Object.keys(STEP_LABELS)).toContain("issue_log");
    expect(stepLabel("issue_log", false)).toBe("Issue Log");
  });
});
