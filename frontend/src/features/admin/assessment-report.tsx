import { useEffect, useState } from "react";
import { authFetch } from "../../lib/api";
// Both come from the assessment module's public surface, not from paths inside it.
import { AssessmentGeneratingPage, AssessmentReport } from "../assessment";


type FinalReport = Parameters<typeof AssessmentReport>[0]["report"];

const inFlightFinalReportRequests = new Map<number, Promise<FinalReport>>();

function fetchFinalReport(assessmentId: number): Promise<FinalReport> {
  const existingRequest = inFlightFinalReportRequests.get(assessmentId);
  if (existingRequest) {
    return existingRequest;
  }

  const request = authFetch(`/assessments/${assessmentId}/final-report`)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error("Failed to load final report");
      }
      return (await response.json()) as FinalReport;
    })
    .finally(() => {
      inFlightFinalReportRequests.delete(assessmentId);
    });

  inFlightFinalReportRequests.set(assessmentId, request);
  return request;
}

type Props = {
  assessmentId: number;
  onBack: () => void;
};

export default function AdminAssessmentReport({ assessmentId, onBack }: Props) {
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    fetchFinalReport(assessmentId)
      .then((reportPayload) => {
        if (!mounted) return;
        setReport(reportPayload);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load report");
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [assessmentId]);

  if (loading) return <AssessmentGeneratingPage mode="admin" onBack={onBack} />;

  if (error || !report) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="mx-auto max-w-3xl rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error ?? "Report unavailable."}
        </div>
        <div className="mx-auto mt-4 max-w-3xl">
          <button onClick={onBack} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
            Back to admin
          </button>
        </div>
      </div>
    );
  }

  return <AssessmentReport report={report} onBack={onBack} />;
}
