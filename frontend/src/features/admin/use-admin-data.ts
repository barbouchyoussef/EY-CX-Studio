/**
 * Everything the admin dashboard loads from the server.
 *
 * The dashboard held thirteen pieces of server state, a loading flag, an error, four loaders and
 * the effects that drive them, mixed in among its form drafts and table state. Reading any one of
 * them meant reading all sixty-odd. They are all here instead, and the dashboard destructures
 * them under the names it already used, so the rendering code is unchanged.
 *
 * `run` is exported because every mutation in the dashboard follows the same shape: do the write,
 * then reload, with one loading flag and one error covering both.
 */

import { useCallback, useEffect, useState } from "react";

import { authFetch } from "../../lib/api";
import {
  DEFAULT_ADMIN_UI_METADATA,
  mergeAdminUiMetadata,
  type AdminUiMetadata,
} from "./ui-metadata";
import type {
  AssessmentItem,
  Axis,
  Capability,
  CompanySize,
  MaturityLevel,
  MetabaseEmbedPayload,
  QuickWinTemplate,
  Region,
  Rubric,
  Sector,
  ViewKey,
} from "./types";

type Params = {
  view: ViewKey;
  /** Query string for the analytics endpoints, already built from the filter controls. */
  analyticsQuery: string;
  /** The history list is filtered server-side by region; the rest is filtered in the browser. */
  regionCode: string;
};

export function useAdminData({ view, analyticsQuery, regionCode }: Params) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [assessments, setAssessments] = useState<AssessmentItem[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [sizes, setSizes] = useState<CompanySize[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [axes, setAxes] = useState<Axis[]>([]);
  const [levels, setLevels] = useState<MaturityLevel[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [quickWinTemplates, setQuickWinTemplates] = useState<QuickWinTemplate[]>([]);
  const [uiMetadata, setUiMetadata] = useState<AdminUiMetadata>(DEFAULT_ADMIN_UI_METADATA);
  const [metabaseEmbedEnabled, setMetabaseEmbedEnabled] = useState(false);
  const [metabaseEmbedUrl, setMetabaseEmbedUrl] = useState<string | null>(null);

  /** One loading flag and one error for every request the dashboard makes, including mutations. */
  const run = useCallback(async (fn: () => Promise<void>) => {
    setLoading(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Filter dropdown options for the analytics and history views.
   *
   * These write to the same three pieces of state the CRUD views use, but with synthetic ids
   * built from the list position, because this endpoint returns labels rather than rows. Only
   * one of the two loaders runs for a given view, so they never contend.
   */
  const loadReferenceOptions = useCallback(async () => {
    const response = await authFetch(`/reference/options`);
    if (!response.ok) throw new Error("Failed to load reference options");
    const payload = await response.json();
    setSectors(
      (payload.sectors ?? []).map((row: { code: string; label: string }, index: number) => ({
        id: index + 1,
        code: row.code,
        name: row.label,
      })),
    );
    setSizes(
      (payload.company_sizes ?? []).map((row: { code: string; label: string }, index: number) => ({
        id: index + 1,
        code: row.code,
        name: row.label,
      })),
    );
    setRegions(
      (payload.regions ?? []).map((row: { label: string }, index: number) => ({
        id: index + 1,
        name: row.label,
      })),
    );
  }, []);

  const loadAnalytics = useCallback(async () => {
    const metabaseRes = await authFetch(`/admin/analytics/metabase-embed?${analyticsQuery}`);
    if (!metabaseRes.ok) throw new Error("Failed to load analytics");
    const metabasePayload = (await metabaseRes.json()) as MetabaseEmbedPayload;
    setMetabaseEmbedEnabled(Boolean(metabasePayload.enabled));
    setMetabaseEmbedUrl(metabasePayload.url ?? null);
  }, [analyticsQuery]);

  const loadHistory = useCallback(async () => {
    const params = new URLSearchParams({ limit: "200", offset: "0" });
    if (regionCode) params.set("region_code", regionCode);
    const response = await authFetch(`/assessments?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to load assessments");
    const payload = await response.json();
    setAssessments(payload.items ?? []);
  }, [regionCode]);

  /** One round trip for every CRUD view, so switching between them costs nothing. */
  const loadCrud = useCallback(async () => {
    const [secRes, sizeRes, regionRes, axisRes, levelRes, capRes, rubRes, quickWinRes, uiMetaRes] =
      await Promise.all([
        authFetch(`/admin/reference/sectors?limit=500`),
        authFetch(`/admin/reference/company-sizes?limit=500`),
        authFetch(`/admin/reference/regions?limit=500`),
        authFetch(`/admin/reference/axes?limit=200`),
        authFetch(`/admin/reference/maturity-levels?limit=500`),
        authFetch(`/admin/capabilities?limit=1000`),
        authFetch(`/admin/capability-maturity-rubrics?limit=2000`),
        authFetch(`/admin/capability-quick-win-templates?limit=2000`),
        authFetch(`/admin/reference/ui-metadata`),
      ]);
    if (
      !secRes.ok ||
      !sizeRes.ok ||
      !regionRes.ok ||
      !axisRes.ok ||
      !levelRes.ok ||
      !capRes.ok ||
      !rubRes.ok ||
      !quickWinRes.ok
    ) {
      throw new Error("Failed to load CRUD data");
    }
    setSectors(await secRes.json());
    setSizes(await sizeRes.json());
    setRegions(await regionRes.json());
    setAxes(await axisRes.json());
    setLevels(await levelRes.json());
    setCapabilities(await capRes.json());
    setRubrics(await rubRes.json());
    setQuickWinTemplates(await quickWinRes.json());
    // The metadata endpoint is allowed to fail: the dashboard renders with built-in labels.
    if (uiMetaRes.ok) {
      const payload = (await uiMetaRes.json()) as Partial<AdminUiMetadata>;
      setUiMetadata(mergeAdminUiMetadata(payload));
    } else {
      setUiMetadata(DEFAULT_ADMIN_UI_METADATA);
    }
  }, []);

  useEffect(() => {
    run(loadReferenceOptions);
  }, [run, loadReferenceOptions]);

  useEffect(() => {
    if (view === "analytics") run(loadAnalytics);
    else if (view === "history") run(loadHistory);
    else run(loadCrud);
  }, [view, analyticsQuery, run, loadAnalytics, loadHistory, loadCrud]);

  return {
    loading,
    error,
    setError,
    run,

    assessments,
    sectors,
    sizes,
    regions,
    axes,
    levels,
    capabilities,
    rubrics,
    quickWinTemplates,
    uiMetadata,
    metabaseEmbedEnabled,
    metabaseEmbedUrl,

    loadHistory,
    loadCrud,

    /** Exposed for the drag-to-reorder handlers, which move a row locally for immediate feedback
     *  before the PATCHes land and `loadCrud` replaces the list with the server's order. */
    setCapabilities,
  };
}
