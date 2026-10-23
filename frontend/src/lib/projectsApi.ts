import { authFetch } from "./api";

export type StepStatus = "todo" | "in_progress" | "done";

export type ProjectMember = {
  user_id: number;
  full_name: string;
  email: string;
  role: string; // 'owner' | 'collaborator'
};

export type Project = {
  id: number;
  name: string;
  company_name?: string | null;
  sector?: string | null;
  owner_id: number;
  my_role: string; // requesting user's role on this project
  created_at: string;
  updated_at: string;
  steps: Record<string, StepStatus>;
  members: ProjectMember[];
};

/** Pipeline step keys, in engagement order (must match the backend PROJECT_STEPS). */
export const PROJECT_STEP_KEYS = ["assessment", "interview", "social", "desk_research", "issue_log"] as const;
export type StepKey = (typeof PROJECT_STEP_KEYS)[number];

export async function listProjects(): Promise<Project[]> {
  const res = await authFetch("/projects");
  if (!res.ok) throw new Error(`Failed to list projects (${res.status})`);
  return res.json();
}

export async function getProject(id: number | string): Promise<Project> {
  const res = await authFetch(`/projects/${id}`);
  if (!res.ok) throw new Error(`Failed to load project (${res.status})`);
  return res.json();
}

export async function createProject(body: {
  name: string;
  company_name?: string;
  sector?: string;
}): Promise<Project> {
  const res = await authFetch("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to create project (${res.status})`);
  return res.json();
}

export async function setProjectStep(
  id: number | string,
  stepKey: StepKey,
  status: StepStatus,
): Promise<Project> {
  const res = await authFetch(`/projects/${id}/steps/${stepKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`Failed to update step (${res.status})`);
  return res.json();
}

export async function deleteProject(id: number | string): Promise<void> {
  const res = await authFetch(`/projects/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`Failed to delete project (${res.status})`);
}

/** Add a collaborator by email (owner only). */
export async function addProjectMember(id: number | string, email: string): Promise<ProjectMember> {
  const res = await authFetch(`/projects/${id}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Failed to add member (${res.status})`);
  }
  return res.json();
}

/** Remove a collaborator (owner only). */
export async function removeProjectMember(id: number | string, userId: number): Promise<void> {
  const res = await authFetch(`/projects/${id}/members/${userId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`Failed to remove member (${res.status})`);
}

/* ---------- Artifacts (results attached to a project step) ---------- */

export type AnalysisKind =
  | "assessment"
  | "interview_guide"
  | "desk_session"
  | "social_report"
  // A finished issue log is a deliverable in its own right, so it shares like the rest.
  | "issue_log";

export type ProjectArtifact = {
  id: number;
  kind: AnalysisKind | string;
  ref_id: string;
  step_key: string;
  title?: string | null;
  created_at: string;
};

export async function listArtifacts(projectId: number | string): Promise<ProjectArtifact[]> {
  const res = await authFetch(`/projects/${projectId}/artifacts`);
  if (!res.ok) throw new Error(`Failed to load artifacts (${res.status})`);
  return res.json();
}

export async function attachArtifact(
  projectId: number | string,
  body: { kind: AnalysisKind; ref_id: string; step_key: string; title?: string },
): Promise<ProjectArtifact> {
  const res = await authFetch(`/projects/${projectId}/artifacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to attach result (${res.status})`);
  return res.json();
}

/** Unlink a result from a project (the underlying analysis stays in the normal tools). */
export async function detachArtifact(projectId: number | string, artifactId: number): Promise<void> {
  const res = await authFetch(`/projects/${projectId}/artifacts/${artifactId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`Failed to remove from project (${res.status})`);
}

// Where each analysis kind's own delete endpoint lives.
const DELETE_PATH: Record<AnalysisKind, (ref: string) => string> = {
  assessment: (r) => `/assessments/${r}`,
  interview_guide: (r) => `/assessments/interview-guide/${r}`,
  social_report: (r) => `/scraping/reports/${r}`,
  desk_session: (r) => `/desk-research/sessions/${r}`,
  issue_log: (r) => `/issue-log/${r}`,
};

/** Delete the underlying analysis for good (owner only). Cleans up its project links + shares.
 *  The backend returns 404 for non-owners, so any non-OK is surfaced to the caller. */
export async function deleteAnalysis(kind: AnalysisKind, refId: string): Promise<void> {
  const path = DELETE_PATH[kind]?.(refId);
  if (!path) throw new Error(`Unknown analysis kind: ${kind}`);
  const res = await authFetch(path, { method: "DELETE" });
  if (!res.ok) throw new Error(`delete-failed-${res.status}`);
}

/* ---------- Per-analysis sharing ---------- */

export type ShareRecipient = {
  share_id: number;
  user_id: number;
  email: string;
  full_name: string;
};

/** Who I've shared a specific analysis with. */
export async function listSharesFor(kind: AnalysisKind, refId: string): Promise<ShareRecipient[]> {
  const q = new URLSearchParams({ kind, ref_id: refId }).toString();
  const res = await authFetch(`/shares/for?${q}`);
  if (!res.ok) throw new Error(`Failed to load shares (${res.status})`);
  return res.json();
}

/** Share an analysis with an existing user by email. Throws with the server's message on error. */
export async function shareAnalysis(kind: AnalysisKind, refId: string, email: string): Promise<void> {
  const res = await authFetch("/shares", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, ref_id: refId, email }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Failed to share (${res.status})`);
  }
}

/** Revoke a share I created. */
export async function unshareAnalysis(shareId: number): Promise<void> {
  const res = await authFetch(`/shares/${shareId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`Failed to revoke share (${res.status})`);
}

/* --------------------------------------------------------------------------
 * The project's consolidated interview report
 *
 * One report per project, so generate and regenerate are the same POST. `stale` says the stored
 * report no longer matches the interviews behind it — another interview was attached, or more
 * answers were recorded — which is what turns "Generate" into "Regenerate" with a reason.
 * ------------------------------------------------------------------------ */

export type InterviewReportEnvelope = {
  status: "none" | "ready" | "success";
  report: { overview: unknown; markdown: string; generated_at: string | null } | null;
  stale?: boolean;
  can_generate: boolean;
  interview_count: number;
};

export async function getInterviewReport(
  projectId: number | string,
): Promise<InterviewReportEnvelope> {
  const res = await authFetch(`/projects/${projectId}/interview-report`);
  if (!res.ok) throw new Error(`Failed to load the interview report (${res.status})`);
  return res.json();
}

export async function generateInterviewReport(
  projectId: number | string,
): Promise<InterviewReportEnvelope> {
  const res = await authFetch(`/projects/${projectId}/interview-report`, { method: "POST" });
  if (!res.ok) {
    // The backend answers 400 with a plain reason when there is nothing to report on yet
    // ("no interviews", "no answers recorded"). That reason is worth showing verbatim.
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `Failed to generate the report (${res.status})`);
  }
  return res.json();
}
