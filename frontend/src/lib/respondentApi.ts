// Client (respondent) API — used by the passwordless assessment link page.
// There is NO login here: the only credential is the link token, sent on every request as a
// header. These calls hit the public /respondent/* endpoints, never the consultant routes.

import type { FinalReport } from "../types/final-report";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function rfetch(path: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  headers.set("X-Respondent-Token", token);
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}

export type AxisProgress = { axis: string; covered: number; total: number };

export type RespondentAssessmentState = {
  id?: number;
  status?: string;
  current_axis?: string | null;
  progress?: AxisProgress[];
  company?: { name?: string | null } | null;
};

export type RespondentContext = {
  client_name: string | null;
  client_role: string | null;
  status: string;
  assessment: RespondentAssessmentState | null;
};

export type NextQuestion = {
  status: string; // "active" | "completed" | ...
  axis: string | null;
  question: string | null;
  message: string | null;
  options: string[] | null;
};

/** Validate the link + get who it's for. Throws "invalid" on a bad/expired/revoked token. */
export async function getRespondentContext(token: string): Promise<RespondentContext> {
  const res = await rfetch("/respondent/context", token);
  if (res.status === 401) throw new Error("invalid");
  if (!res.ok) throw new Error("error");
  return res.json();
}

export async function getRespondentNextQuestion(token: string): Promise<NextQuestion> {
  const res = await rfetch("/respondent/next-question", token);
  if (res.status === 401) throw new Error("invalid");
  if (!res.ok) throw new Error("error");
  return res.json();
}

export async function submitRespondentAnswer(token: string, answer: string): Promise<{ status: string }> {
  const res = await rfetch("/respondent/answers", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  if (res.status === 401) throw new Error("invalid");
  if (!res.ok) throw new Error("error");
  return res.json();
}

export type RefOption = { code: string; label: string };

/** Sector + size reference lists for the client's company-profile step (public endpoint). */
export async function getReferenceOptions(): Promise<{ sectors: RefOption[]; sizes: RefOption[] }> {
  const res = await fetch(`${API_BASE_URL}/reference/options`);
  if (!res.ok) throw new Error("error");
  const d = await res.json();
  return { sectors: d.sectors ?? [], sizes: d.company_sizes ?? [] };
}

/** The client sets their own company name, sector + company size before starting the questions. */
export async function setRespondentProfile(
  token: string,
  sector: string,
  size: string,
  companyName?: string,
): Promise<void> {
  const res = await rfetch("/respondent/profile", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sector, size, company_name: companyName }),
  });
  if (res.status === 401) throw new Error("invalid");
  if (!res.ok) throw new Error("error");
}

/** The final report once the assessment is complete (null until it's ready). */
export async function getRespondentFinalReport(token: string): Promise<FinalReport | null> {
  const res = await rfetch("/respondent/final-report", token);
  if (!res.ok) return null;
  return (await res.json()) as FinalReport;
}
