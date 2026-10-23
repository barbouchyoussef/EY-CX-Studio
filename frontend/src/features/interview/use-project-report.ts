/**
 * Loading and generating the project's consolidated interview report.
 *
 * Kept out of the components because the hub re-renders on every keystroke elsewhere in the
 * module, and this owns a long-running request: generating reads every interview and every
 * self-assessment behind them, and takes tens of seconds.
 *
 * The hub owns the one instance and passes it down, so the buttons that generate the report and
 * the page that shows it never disagree and never fetch twice.
 */

import { useCallback, useEffect, useState } from "react";

import {
  generateInterviewReport,
  getInterviewReport,
  type InterviewReportEnvelope,
} from "../../lib/projectsApi";
import type { InterviewProjectReport } from "./project-report";

export type ProjectReportState = {
  report: InterviewProjectReport | null;
  markdown: string | null;
  generatedAt: string | null;
  /** The stored report predates the current interviews, so it is worth regenerating. */
  stale: boolean;
  loading: boolean;
  generating: boolean;
  error: string | null;
  generate: () => Promise<void>;
};

/**
 * The settled result for one project. `envelope: null` records a failed load, which is what
 * keeps `loading` derivable -- without it a failure would read as "still loading" forever.
 */
type Loaded = { projectId: number; envelope: InterviewReportEnvelope | null };

export function useProjectInterviewReport(projectId: number | null | undefined): ProjectReportState {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    // Guards against a slow response for a project the user has already navigated away from
    // overwriting the state of the one they are now looking at.
    let cancelled = false;
    getInterviewReport(projectId)
      .then((envelope) => {
        if (!cancelled) setLoaded({ projectId, envelope });
      })
      .catch(() => {
        // A failed load is not worth an error message: the button still offers to generate.
        // It is still recorded, so the page stops reporting itself as loading.
        if (!cancelled) setLoaded({ projectId, envelope: null });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const generate = useCallback(async () => {
    if (!projectId) return;
    setGenerating(true);
    setError(null);
    try {
      setLoaded({ projectId, envelope: await generateInterviewReport(projectId) });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate the report.");
    } finally {
      setGenerating(false);
    }
  }, [projectId]);

  // Both derived rather than stored. Clearing them in the effect would mean a synchronous
  // setState on every project change, and would let the previous project's report show for a
  // frame before the new one arrived.
  const settled = loaded !== null && loaded.projectId === projectId;
  const envelope = settled ? loaded.envelope : null;

  return {
    report: (envelope?.report?.overview as InterviewProjectReport) ?? null,
    markdown: envelope?.report?.markdown ?? null,
    generatedAt: envelope?.report?.generated_at ?? null,
    stale: Boolean(envelope?.stale),
    loading: Boolean(projectId) && !settled,
    generating,
    error,
    generate,
  };
}
