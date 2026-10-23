import { useEffect, useMemo, useState, type ReactNode } from "react";
import { authFetch } from "../../lib/api";
import { useAdminData } from "./use-admin-data";
import type { SortKey, ViewKey } from "./types";
import {
  BarChart3,
  ClipboardList,
  Building2,
  Globe2,
  Users,
  Layers3,
  Target,
  Compass,
  BookOpenText,
  Lightbulb,
  Check,
  X,
} from "lucide-react";

import {
  Card, CrudNameOnly, CrudSimple, DangerButton, IconActionButton, IconEditButton, Pager,
  PrimaryActionButton, QuickWinTextCell, SimpleTable, paginate, sortRows, sortable,
  type SortDir,
} from "./table-kit";


const NAV_ITEMS: { key: ViewKey; label: string }[] = [
  { key: "analytics", label: "Analytics" },
  { key: "history", label: "Assessments history" },
  { key: "sectors", label: "Sectors" },
  { key: "sizes", label: "Company sizes" },
  { key: "regions", label: "Regions" },
  { key: "axes", label: "Axes" },
  { key: "levels", label: "Maturity levels" },
  { key: "capabilities", label: "Capabilities" },
  { key: "rubrics", label: "Maturity rubrics" },
  { key: "recommendations", label: "Quick win templates" },
];

const NAV_ICONS: Record<ViewKey, ReactNode> = {
  analytics: <BarChart3 className="h-4 w-4" />,
  history: <ClipboardList className="h-4 w-4" />,
  sectors: <Building2 className="h-4 w-4" />,
  sizes: <Users className="h-4 w-4" />,
  regions: <Globe2 className="h-4 w-4" />,
  axes: <Compass className="h-4 w-4" />,
  levels: <Layers3 className="h-4 w-4" />,
  capabilities: <Target className="h-4 w-4" />,
  rubrics: <BookOpenText className="h-4 w-4" />,
  recommendations: <Lightbulb className="h-4 w-4" />,
};

type Props = {
  onBack: () => void;
  onOpenAssessmentDetails: (assessmentId: number) => void;
  onOpenAssessmentReport: (assessmentId: number) => void;
};

export default function AdminDashboard({ onBack, onOpenAssessmentDetails, onOpenAssessmentReport }: Props) {
  const [view, setView] = useState<ViewKey>("analytics");

  const [fromDate, setFromDate] = useState("2026-01-01");
  const [toDate, setToDate] = useState("2026-12-31");
  const [sectorCode, setSectorCode] = useState("");
  const [sizeCode, setSizeCode] = useState("");
  const [regionCode, setRegionCode] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");


  const [newSectorCode, setNewSectorCode] = useState("");
  const [newSectorName, setNewSectorName] = useState("");
  const [newSizeCode, setNewSizeCode] = useState("");
  const [newSizeName, setNewSizeName] = useState("");
  const [newRegionName, setNewRegionName] = useState("");
  const [newAxisCode, setNewAxisCode] = useState("");
  const [newAxisName, setNewAxisName] = useState("");
  const [newAxisDescription, setNewAxisDescription] = useState("");
  const [newAxisGuidelines, setNewAxisGuidelines] = useState("");
  const [newLevelNumber, setNewLevelNumber] = useState("1");
  const [newLevelLabel, setNewLevelLabel] = useState("");
  const [newLevelDescription, setNewLevelDescription] = useState("");
  const [createModal, setCreateModal] = useState<null | "sector" | "size" | "region" | "axis" | "level">(null);
  const [newCapabilityAxisId, setNewCapabilityAxisId] = useState<number | null>(null);
  const [newCapabilityName, setNewCapabilityName] = useState("");
  const [newCapabilityCode, setNewCapabilityCode] = useState("");
  const [newCapabilityDescription, setNewCapabilityDescription] = useState("");
  const [newCapabilityEvidence, setNewCapabilityEvidence] = useState("");
  const [newCapabilityGuidelines, setNewCapabilityGuidelines] = useState("");
  const [newRubricCapabilityId, setNewRubricCapabilityId] = useState<number | null>(null);
  const [newRubricMaturityLevelId, setNewRubricMaturityLevelId] = useState("");
  const [newRubricDescription, setNewRubricDescription] = useState("");
  const [newQuickWinCapabilityId, setNewQuickWinCapabilityId] = useState<number | null>(null);
  const [newQuickWinMaturityLevelId, setNewQuickWinMaturityLevelId] = useState("");
  const [newQuickWinGuideline, setNewQuickWinGuideline] = useState("");
  const [newQuickWinAfterText, setNewQuickWinAfterText] = useState("");
  const [newQuickWinOwnerHint, setNewQuickWinOwnerHint] = useState("");
  const [newQuickWinTimelineHint, setNewQuickWinTimelineHint] = useState("");
  const [textEditModal, setTextEditModal] = useState<null | {
    kind:
      | "axis_description"
      | "axis_guideline"
      | "capability_description"
      | "capability_evidence"
      | "capability_guideline"
      | "level_description"
      | "rubric_description"
      | "quick_win_guideline"
      | "quick_win_after_text"
      | "quick_win_owner_hint"
      | "quick_win_timeline_hint";
    id: number;
    title: string;
    subtitle?: string;
    helperText?: string;
    placeholder?: string;
    value: string;
  }>(null);
  const [textEditDraft, setTextEditDraft] = useState("");

  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [editId, setEditId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [openAxes, setOpenAxes] = useState<Record<number, boolean>>({});
  const [draggingCapabilityId, setDraggingCapabilityId] = useState<number | null>(null);
  const [draggingLevelId, setDraggingLevelId] = useState<number | null>(null);
  const [draggingAxisId, setDraggingAxisId] = useState<number | null>(null);

  const analyticsQuery = useMemo(() => {
    const params = new URLSearchParams({ from: fromDate, to: toDate });
    if (sectorCode) params.set("sector_code", sectorCode);
    if (sizeCode) params.set("company_size_code", sizeCode);
    if (regionCode) params.set("region_code", regionCode);
    return params.toString();
  }, [fromDate, toDate, sectorCode, sizeCode, regionCode]);

  // Everything fetched from the server, plus its loading flag, error and loaders.
  // Destructured under the names the rendering code below already uses.
  const {
    loading,
    error,
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
    setCapabilities,
  } = useAdminData({ view, analyticsQuery, regionCode });

  // A view or filter change restarts paging. This was a side effect of the loaders before they
  // moved out. Axis expansion needs no equivalent: every read is `openAxes[id] ?? true`, so an
  // axis nobody has collapsed is already open.
  useEffect(() => {
    setPage(1);
  }, [view, analyticsQuery]);



  const filteredHistory = useMemo(() => {
    const rows = assessments.filter((item) => {
      const byCompany = companyFilter ? item.company_name.toLowerCase().includes(companyFilter.toLowerCase()) : true;
      const bySector = sectorCode ? item.sector.toLowerCase().includes(sectorCode.replace("_", " ").toLowerCase()) : true;
      const bySize = sizeCode ? item.size.toLowerCase().includes(sizeCode.toLowerCase()) : true;
      const byRegion = regionCode ? (item.region ?? "").toLowerCase().includes(regionCode.replaceAll("_", " ").toLowerCase()) : true;
      const byStatus = statusFilter ? item.status.toLowerCase() === statusFilter.toLowerCase() : true;
      return byCompany && bySector && bySize && byRegion && byStatus;
    });
    return sortRows(rows, sortKey, sortDir);
  }, [assessments, companyFilter, sectorCode, sizeCode, regionCode, statusFilter, sortKey, sortDir]);

  const capabilityRows = useMemo(
    () => [...capabilities].sort((a, b) => a.axis_id - b.axis_id || a.sort_order - b.sort_order || a.id - b.id),
    [capabilities],
  );
  const axisRows = useMemo(() => [...axes].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id), [axes]);
  const rubricRows = useMemo(() => sortRows(rubrics, sortKey, sortDir), [rubrics, sortKey, sortDir]);
  const quickWinTemplateRows = useMemo(() => sortRows(quickWinTemplates, sortKey, sortDir), [quickWinTemplates, sortKey, sortDir]);

  const pagedHistory = paginate(filteredHistory, page);

  const capabilityNameById = useMemo(() => {
    const map = new Map<number, string>();
    capabilities.forEach((c) => map.set(c.id, c.name));
    return map;
  }, [capabilities]);
  const levelLabelById = useMemo(() => {
    const map = new Map<number, string>();
    levels.forEach((l) => map.set(l.id, l.label));
    return map;
  }, [levels]);
  const post = async (path: string, body: unknown) => {
    const response = await authFetch(`${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`POST ${path} failed`);
  };
  const patch = async (path: string, body: unknown) => {
    const response = await authFetch(`${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`PATCH ${path} failed`);
  };
  const remove = async (path: string) => {
    const response = await authFetch(`${path}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`DELETE ${path} failed`);
  };

  const setSort = (key: string) => {
    if (sortKey === key) setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const startEdit = (id: number, draft: Record<string, string>) => {
    setEditId(id);
    setEditDraft(draft);
  };
  const stopEdit = () => {
    setEditId(null);
    setEditDraft({});
  };

  const reorderCapabilities = async (axisId: number, draggedId: number, targetId: number) => {
    if (draggedId === targetId) return;

    const axisRows = capabilityRows.filter((item) => item.axis_id === axisId);
    const fromIndex = axisRows.findIndex((item) => item.id === draggedId);
    const toIndex = axisRows.findIndex((item) => item.id === targetId);
    if (fromIndex < 0 || toIndex < 0) return;

    const reordered = [...axisRows];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);
    const updates = reordered.map((item, index) => ({ ...item, sort_order: index + 1 }));

    setCapabilities((current) =>
      current.map((item) => updates.find((updated) => updated.id === item.id) ?? item),
    );

    await Promise.all(
      updates.map((item) => patch(`/admin/capabilities/${item.id}`, { sort_order: item.sort_order })),
    );
    await loadCrud();
  };

  const reorderMaturityLevels = async (draggedId: number, targetId: number) => {
    if (draggedId === targetId) return;

    const ordered = [...levels].sort((a, b) => a.level_number - b.level_number || a.id - b.id);
    const fromIndex = ordered.findIndex((item) => item.id === draggedId);
    const toIndex = ordered.findIndex((item) => item.id === targetId);
    if (fromIndex < 0 || toIndex < 0) return;

    const reordered = [...ordered];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);

    // level_number is unique, so move through temporary values before assigning final order.
    for (const [index, item] of reordered.entries()) {
      await patch(`/admin/reference/maturity-levels/${item.id}`, {
        level_number: 1000 + index,
        label: item.label,
        description: item.description || null,
      });
    }
    for (const [index, item] of reordered.entries()) {
      await patch(`/admin/reference/maturity-levels/${item.id}`, {
        level_number: index + 1,
        label: item.label,
        description: item.description || null,
      });
    }
    await loadCrud();
  };

  const reorderAxes = async (draggedId: number, targetId: number) => {
    if (draggedId === targetId) return;

    const ordered = [...axisRows];
    const fromIndex = ordered.findIndex((item) => item.id === draggedId);
    const toIndex = ordered.findIndex((item) => item.id === targetId);
    if (fromIndex < 0 || toIndex < 0) return;

    const reordered = [...ordered];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);

    for (const [index, item] of reordered.entries()) {
      await patch(`/admin/reference/axes/${item.id}`, {
        code: item.code,
        name: item.name,
        description: item.description || null,
        question_guidelines: item.question_guidelines || null,
        sort_order: 1000 + index,
      });
    }
    for (const [index, item] of reordered.entries()) {
      await patch(`/admin/reference/axes/${item.id}`, {
        code: item.code,
        name: item.name,
        description: item.description || null,
        question_guidelines: item.question_guidelines || null,
        sort_order: index + 1,
      });
    }
    await loadCrud();
  };

  const createAxis = async () => {
    const nextSortOrder = Math.max(0, ...axes.map((item) => Number(item.sort_order) || 0)) + 1;
    await post("/admin/reference/axes", {
      code: newAxisCode,
      name: newAxisName,
      description: newAxisDescription || null,
      question_guidelines: newAxisGuidelines || null,
      sort_order: nextSortOrder,
    });
    setNewAxisCode("");
    setNewAxisName("");
    setNewAxisDescription("");
    setNewAxisGuidelines("");
    setCreateModal(null);
    await loadCrud();
  };

  const openCapabilityCreateModal = (axisId: number) => {
    setNewCapabilityAxisId(axisId);
    setNewCapabilityName("");
    setNewCapabilityCode("");
    setNewCapabilityDescription("");
    setNewCapabilityEvidence("");
    setNewCapabilityGuidelines("");
  };

  const createCapability = async () => {
    if (newCapabilityAxisId === null) return;
    const axisRows = capabilityRows.filter((item) => item.axis_id === newCapabilityAxisId);
    const nextSortOrder = Math.max(0, ...axisRows.map((item) => Number(item.sort_order) || 0)) + 1;
    await post("/admin/capabilities", {
      axis_id: newCapabilityAxisId,
      code: newCapabilityCode,
      name: newCapabilityName,
      description: newCapabilityDescription || null,
      evidence_required: newCapabilityEvidence || null,
      question_guidelines: newCapabilityGuidelines || null,
      sort_order: nextSortOrder,
    });
    setNewCapabilityAxisId(null);
    await loadCrud();
  };

  const openRubricCreateModal = (capabilityId: number) => {
    setNewRubricCapabilityId(capabilityId);
    setNewRubricMaturityLevelId(levels[0] ? String(levels[0].id) : "");
    setNewRubricDescription("");
  };

  const createRubric = async () => {
    if (newRubricCapabilityId === null || !newRubricMaturityLevelId) return;
    await post("/admin/capability-maturity-rubrics", {
      capability_id: newRubricCapabilityId,
      maturity_level_id: Number(newRubricMaturityLevelId),
      description: newRubricDescription,
    });
    setNewRubricCapabilityId(null);
    await loadCrud();
  };

  const openQuickWinCreateModal = (capabilityId: number) => {
    setNewQuickWinCapabilityId(capabilityId);
    setNewQuickWinMaturityLevelId(levels[0] ? String(levels[0].id) : "");
    setNewQuickWinGuideline("");
    setNewQuickWinAfterText("");
    setNewQuickWinOwnerHint("");
    setNewQuickWinTimelineHint("");
  };

  const createQuickWinTemplate = async () => {
    if (newQuickWinCapabilityId === null || !newQuickWinMaturityLevelId) return;
    await post("/admin/capability-quick-win-templates", {
      capability_id: newQuickWinCapabilityId,
      maturity_level_id: Number(newQuickWinMaturityLevelId),
      quick_win_guideline: newQuickWinGuideline,
      after_text: newQuickWinAfterText || null,
      owner_hint: newQuickWinOwnerHint || null,
      timeline_hint: newQuickWinTimelineHint || null,
      active: true,
    });
    setNewQuickWinCapabilityId(null);
    await loadCrud();
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#1A1A1A] lg:flex">
      <aside className="w-full border-r border-[#E5E7EB] bg-white lg:w-72">
        <div className="border-b border-[#E5E7EB] px-6 py-5">
          <div className="text-lg font-semibold">Admin</div>
          <div className="mt-1 text-sm text-[#6B7280]">Internal consultants</div>
        </div>
        <nav className="p-4">
          <div className="space-y-2">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.key}
                onClick={() => setView(item.key)}
                className={`flex w-full items-center gap-2 rounded-xl px-4 py-3 text-left text-sm font-medium transition ${
                  view === item.key ? "bg-[#FFF8CC] text-[#1A1A1A]" : "text-[#4B5563] hover:bg-[#F9FAFB]"
                }`}
              >
                <span className={view === item.key ? "text-[#1A1A1A]" : "text-[#6B7280]"}>{NAV_ICONS[item.key]}</span>
                {item.label}
              </button>
            ))}
          </div>
          <button onClick={onBack} className="mt-6 w-full rounded-xl border border-slate-300 px-4 py-3 text-left text-sm text-slate-700 hover:bg-slate-50">
            Back to app
          </button>
        </nav>
      </aside>

      <div className="flex-1">
        <header className="border-b border-[#E5E7EB] bg-[#FAFAFA] px-6 py-6 md:px-8">
          <h1 className="text-3xl font-semibold tracking-[-0.03em]">{NAV_ITEMS.find((item) => item.key === view)?.label}</h1>
          <p className="mt-2 text-sm text-[#6B7280]">Manage the business guidance the LLM uses for questions, scoring context, and final recommendations.</p>
        </header>
        <main className="space-y-4 px-6 py-8 md:px-8">
          {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
          {loading ? <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">Loading...</div> : null}

          {view === "history" && (
            <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-6">
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <select value={sectorCode} onChange={(e) => setSectorCode(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">All sectors</option>
                {sectors.map((s) => (
                  <option key={s.code} value={s.code}>{s.name}</option>
                ))}
              </select>
              <select value={sizeCode} onChange={(e) => setSizeCode(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">All sizes</option>
                {sizes.map((s) => (
                  <option key={s.code} value={s.code}>{s.name}</option>
                ))}
              </select>
              <select value={regionCode} onChange={(e) => setRegionCode(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">All regions</option>
                {regions.map((region) => (
                  <option key={region.name} value={region.name}>{region.name}</option>
                ))}
              </select>
              <button onClick={() => run(loadHistory)} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white">Refresh</button>
            </div>
          )}

          {view === "analytics" && (
            <>
              {metabaseEmbedEnabled ? (
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                    {metabaseEmbedUrl ? (
                      <iframe
                        title="Metabase analytics dashboard"
                        src={metabaseEmbedUrl}
                        className="w-full bg-white"
                        style={{ height: "calc(100vh - 210px)", minHeight: "760px" }}
                      />
                    ) : (
                      <div className="px-4 py-8 text-sm text-slate-500">Loading Metabase charts...</div>
                    )}
                </div>
              ) : (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  Metabase is not enabled yet. Add `METABASE_SITE_URL`, `METABASE_EMBED_SECRET`, and `METABASE_DASHBOARD_ID` in `backend/.env`, then restart backend.
                </div>
              )}
            </>
          )}

          {view === "history" && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <input value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)} placeholder="Filter by company name..." className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                  <option value="">All statuses</option>
                  <option value="active">active</option>
                  <option value="completed">completed</option>
                </select>
              </div>
              <Card title="Assessments">
                <SimpleTable
                  headers={sortable(["Assessment", "Company", "Sector", "Size", "Region", "Status", "Created", "Actions"], sortKey, sortDir)}
                  onSort={(index) => setSort(["id", "company_name", "sector", "size", "region", "status", "created_at", ""][index] || "created_at")}
                  rows={pagedHistory.items.map((item) => [
                    `#${item.id}`,
                    item.company_name,
                    item.sector,
                    item.size,
                    item.region ?? "",
                    item.status,
                    item.created_at?.slice(0, 19).replace("T", " "),
                    <div key={item.id} className="flex flex-nowrap gap-2">
                      <button className="whitespace-nowrap rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50" onClick={() => onOpenAssessmentDetails(item.id)}>Details</button>
                      <button className="whitespace-nowrap rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50" onClick={() => onOpenAssessmentReport(item.id)}>Final report</button>
                    </div>,
                  ])}
                />
                <Pager page={page} totalPages={pagedHistory.totalPages} onPage={setPage} />
              </Card>
            </>
          )}

          {view === "sectors" && <CrudSimple title="Sectors" rows={sectors} onAdd={() => setCreateModal("sector")} onDelete={(id) => run(async () => { await remove(`/admin/reference/sectors/${id}`); await loadCrud(); })} />}

          {view === "sizes" && <CrudSimple title="Company sizes" rows={sizes} onAdd={() => setCreateModal("size")} onDelete={(id) => run(async () => { await remove(`/admin/reference/company-sizes/${id}`); await loadCrud(); })} />}

          {view === "regions" && (
            <CrudNameOnly
              title="Regions"
              rows={regions}
              onAdd={() => setCreateModal("region")}
              onRename={(id, name) => run(async () => { await patch(`/admin/reference/regions/${id}`, { name }); await loadCrud(); })}
              onDelete={(id) => run(async () => { await remove(`/admin/reference/regions/${id}`); await loadCrud(); })}
            />
          )}

          {view === "axes" && (
            <Card title={uiMetadata.axes.title}>
              <div className="mb-4 flex justify-end">
                <PrimaryActionButton onClick={() => setCreateModal("axis")}>Add axis</PrimaryActionButton>
              </div>
              <div className="overflow-auto">
                <table className="w-full min-w-[920px] table-fixed text-left text-sm">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="w-[22%] py-2 pr-3">Axis</th>
                      <th className="w-[34%] py-2 pr-3">{uiMetadata.axes.fields.description?.label ?? "Axis definition"}</th>
                      <th className="w-[34%] py-2 pr-3">{uiMetadata.axes.fields.question_guidelines?.label ?? "Axis question strategy"}</th>
                      <th className="w-[10%] py-2 pr-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {axisRows.map((row) => (
                      <tr
                        key={row.id}
                        draggable={editId !== row.id}
                        onDragStart={() => setDraggingAxisId(row.id)}
                        onDragOver={(event) => event.preventDefault()}
                        onDragEnd={() => setDraggingAxisId(null)}
                        onDrop={(event) => {
                          event.preventDefault();
                          const draggedId = draggingAxisId;
                          setDraggingAxisId(null);
                          if (draggedId) {
                            run(async () => {
                              await reorderAxes(draggedId, row.id);
                            });
                          }
                        }}
                        className={`border-t border-slate-100 align-top ${draggingAxisId === row.id ? "bg-indigo-50" : ""}`}
                      >
                        {editId === row.id ? (
                          <>
                            <td className="py-2 pr-3">
                              <div className="space-y-1">
                                <input value={editDraft.name ?? row.name} onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))} className="w-full rounded border px-2 py-1 text-xs" />
                                <input value={editDraft.code ?? row.code} onChange={(e) => setEditDraft((d) => ({ ...d, code: e.target.value }))} className="w-full rounded border px-2 py-1 text-xs text-slate-500" />
                                <div className="flex gap-1 pt-1">
                                  <IconActionButton
                                    label="Save axis name and code"
                                    tone="confirm"
                                    onClick={() => run(async () => {
                                      await patch(`/admin/reference/axes/${row.id}`, {
                                        code: editDraft.code,
                                        name: editDraft.name,
                                        description: row.description || null,
                                        question_guidelines: row.question_guidelines || null,
                                        sort_order: row.sort_order,
                                      });
                                      stopEdit();
                                      await loadCrud();
                                    })}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </IconActionButton>
                                  <IconActionButton label="Cancel editing" onClick={stopEdit}>
                                    <X className="h-3.5 w-3.5" />
                                  </IconActionButton>
                                </div>
                              </div>
                            </td>
                            <td className="py-2 pr-3"><span className="line-clamp-2 text-xs text-slate-600" title={row.description ?? ""}>{row.description ?? ""}</span></td>
                            <td className="py-2 pr-3"><span className="line-clamp-2 text-xs text-slate-600" title={row.question_guidelines ?? ""}>{row.question_guidelines ?? ""}</span></td>
                            <td className="py-2 pr-3" />
                          </>
                        ) : (
                          <>
                            <td className="py-2 pr-3">
                              <div className="flex min-w-0 items-start gap-2">
                                <span className="cursor-grab select-none rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500" title="Drag to reorder">::</span>
                                <div className="min-w-0 flex-1">
                                  <p className="truncate font-medium text-slate-900" title={row.name}>{row.name}</p>
                                  <p className="truncate text-xs text-slate-500" title={row.code}>{row.code}</p>
                                </div>
                                <IconEditButton label="Edit axis name and code" onClick={() => startEdit(row.id, { code: row.code, name: row.name })} />
                              </div>
                            </td>
                            <td className="py-2 pr-3">
                              <div className="flex items-start gap-2">
                                <span className="line-clamp-2 flex-1" title={row.description ?? ""}>{row.description ?? ""}</span>
                                <IconEditButton
                                  label={uiMetadata.axes.fields.description?.button_label ?? "Edit definition"}
                                  onClick={() => {
                                    setTextEditModal({
                                      kind: "axis_description",
                                      id: row.id,
                                      title: uiMetadata.axes.fields.description?.modal_title ?? "Edit axis definition",
                                      subtitle: row.name,
                                      helperText: uiMetadata.axes.fields.description?.description ?? undefined,
                                      placeholder: uiMetadata.axes.fields.description?.placeholder ?? undefined,
                                      value: row.description ?? "",
                                    });
                                    setTextEditDraft(row.description ?? "");
                                  }}
                                />
                              </div>
                            </td>
                            <td className="py-2 pr-3">
                              <div className="flex items-start gap-2">
                                <span className="line-clamp-2 flex-1" title={row.question_guidelines ?? ""}>{row.question_guidelines ?? ""}</span>
                                <IconEditButton
                                  label={uiMetadata.axes.fields.question_guidelines?.button_label ?? "Edit strategy"}
                                  onClick={() => {
                                    setTextEditModal({
                                      kind: "axis_guideline",
                                      id: row.id,
                                      title: uiMetadata.axes.fields.question_guidelines?.modal_title ?? "Edit axis question strategy",
                                      subtitle: row.name,
                                      helperText: uiMetadata.axes.fields.question_guidelines?.description ?? undefined,
                                      placeholder: uiMetadata.axes.fields.question_guidelines?.placeholder ?? undefined,
                                      value: row.question_guidelines ?? "",
                                    });
                                    setTextEditDraft(row.question_guidelines ?? "");
                                  }}
                                />
                              </div>
                            </td>
                            <td className="py-2 pr-3">
                              <DangerButton
                                onClick={() => {
                                  if (!window.confirm(`Delete axis "${row.name}"?`)) return;
                                  run(async () => { await remove(`/admin/reference/axes/${row.id}`); await loadCrud(); });
                                }}
                              >
                                Delete
                              </DangerButton>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {view === "levels" && (
            <Card title="Maturity levels">
              <div className="mb-4 flex items-center justify-between gap-3">
                <p className="text-sm text-slate-600">Drag rows to adjust maturity order.</p>
                <PrimaryActionButton onClick={() => setCreateModal("level")}>Add maturity level</PrimaryActionButton>
              </div>
              <div className="overflow-auto">
                <table className="w-full min-w-[760px] table-fixed text-left text-sm">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="w-[16%] py-2 pr-3">Level</th>
                      <th className="w-[24%] py-2 pr-3">Label</th>
                      <th className="w-[42%] py-2 pr-3">Description</th>
                      <th className="w-[18%] py-2 pr-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {levels
                      .slice()
                      .sort((a, b) => a.level_number - b.level_number || a.id - b.id)
                      .map((row) => (
                        <tr
                          key={row.id}
                          draggable={editId !== row.id}
                          onDragStart={() => setDraggingLevelId(row.id)}
                          onDragOver={(event) => event.preventDefault()}
                          onDragEnd={() => setDraggingLevelId(null)}
                          onDrop={(event) => {
                            event.preventDefault();
                            const draggedId = draggingLevelId;
                            setDraggingLevelId(null);
                            if (draggedId) {
                              run(async () => {
                                await reorderMaturityLevels(draggedId, row.id);
                              });
                            }
                          }}
                          className={`border-t border-slate-100 align-top ${draggingLevelId === row.id ? "bg-indigo-50" : ""}`}
                        >
                          {editId === row.id ? (
                            <>
                              <td className="py-2 pr-3">
                                <div className="flex items-center gap-2">
                                  <span className="cursor-grab select-none rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500">::</span>
                                  <input value={editDraft.level_number ?? String(row.level_number)} onChange={(e) => setEditDraft((d) => ({ ...d, level_number: e.target.value }))} className="w-16 rounded border px-2 py-1 text-xs" />
                                </div>
                              </td>
                              <td className="py-2 pr-3">
                                <input value={editDraft.label ?? row.label} onChange={(e) => setEditDraft((d) => ({ ...d, label: e.target.value }))} className="w-full rounded border px-2 py-1 text-xs" />
                              </td>
                              <td className="py-2 pr-3"><span className="line-clamp-2 text-xs text-slate-600">{row.description ?? ""}</span></td>
                              <td className="py-2 pr-3">
                                <div className="flex gap-1">
                                  <IconActionButton label="Save level" tone="confirm" onClick={() => run(async () => { await patch(`/admin/reference/maturity-levels/${row.id}`, { level_number: Number(editDraft.level_number), label: editDraft.label, description: row.description || null }); stopEdit(); await loadCrud(); })}><Check className="h-3.5 w-3.5" /></IconActionButton>
                                  <IconActionButton label="Cancel editing" onClick={stopEdit}><X className="h-3.5 w-3.5" /></IconActionButton>
                                </div>
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="py-2 pr-3">
                                <div className="flex items-center gap-2">
                                  <span className="cursor-grab select-none rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500">::</span>
                                  <span>{row.level_number}</span>
                                  <IconEditButton label="Edit level number and label" onClick={() => startEdit(row.id, { level_number: String(row.level_number), label: row.label })} />
                                </div>
                              </td>
                              <td className="py-2 pr-3">{row.label}</td>
                              <td className="py-2 pr-3">
                                <div className="flex items-start gap-2">
                                  <span className="line-clamp-2 flex-1" title={row.description ?? ""}>{row.description ?? ""}</span>
                                  <IconEditButton
                                    label="Edit maturity level description"
                                    onClick={() => {
                                      setTextEditModal({ kind: "level_description", id: row.id, title: "Edit maturity level description", subtitle: row.label, value: row.description ?? "" });
                                      setTextEditDraft(row.description ?? "");
                                    }}
                                  />
                                </div>
                              </td>
                              <td className="py-2 pr-3">
                                <DangerButton
                                  onClick={() => {
                                    if (!window.confirm(`Delete maturity level "${row.label}"?`)) return;
                                    run(async () => { await remove(`/admin/reference/maturity-levels/${row.id}`); await loadCrud(); });
                                  }}
                                >
                                  Delete
                                </DangerButton>
                              </td>
                            </>
                          )}
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {view === "capabilities" && (
            <Card title={uiMetadata.capabilities.title}>
              {axes
                .slice()
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((axis) => {
                  const axisRows = capabilityRows.filter((c) => c.axis_id === axis.id);
                  const isOpen = openAxes[axis.id] ?? true;
                  return (
                    <div key={axis.id} className="mb-3 rounded-lg border border-slate-200">
                      <div className="flex items-center justify-between gap-3 bg-slate-50 px-3 py-2">
                        <button
                          className="flex min-w-0 flex-1 items-center justify-between text-left text-sm font-semibold"
                          onClick={() => setOpenAxes((prev) => ({ ...prev, [axis.id]: !isOpen }))}
                        >
                          <span className="truncate">{axis.name}</span>
                        <span>{isOpen ? "−" : "+"}</span>
                        </button>
                        <PrimaryActionButton onClick={() => openCapabilityCreateModal(axis.id)}>Add capability</PrimaryActionButton>
                      </div>
                      {isOpen ? (
                        <div className="p-2">
                          <div className="overflow-auto">
                            <table className="w-full min-w-[980px] table-fixed text-left text-sm">
                              <thead className="text-slate-500">
                                <tr>
                                  <th className="w-[22%] py-2 pr-3">Capability</th>
                                  <th className="w-[23%] py-2 pr-3">{uiMetadata.capabilities.fields.description?.label ?? "Capability definition"}</th>
                                  <th className="w-[20%] py-2 pr-3">{uiMetadata.capabilities.fields.evidence_required?.label ?? "Evidence signals"}</th>
                                  <th className="w-[25%] py-2 pr-3">{uiMetadata.capabilities.fields.question_guidelines?.label ?? "Question strategy"}</th>
                                  <th className="w-[10%] py-2 pr-3">Action</th>
                                </tr>
                              </thead>
                              <tbody>
                                {axisRows.map((row) => (
                                  <tr
                                    key={row.id}
                                    draggable={editId !== row.id}
                                    onDragStart={() => setDraggingCapabilityId(row.id)}
                                    onDragOver={(event) => event.preventDefault()}
                                    onDragEnd={() => setDraggingCapabilityId(null)}
                                    onDrop={(event) => {
                                      event.preventDefault();
                                      const draggedId = draggingCapabilityId;
                                      setDraggingCapabilityId(null);
                                      if (draggedId) {
                                        run(async () => {
                                          await reorderCapabilities(axis.id, draggedId, row.id);
                                        });
                                      }
                                    }}
                                    className={`border-t border-slate-100 align-top ${draggingCapabilityId === row.id ? "bg-indigo-50" : ""}`}
                                  >
                                    {editId === row.id ? (
                                      <>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="space-y-1">
                                            <input value={editDraft.name ?? row.name} onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))} className="w-full rounded border px-2 py-1 text-xs" />
                                            <input value={editDraft.code ?? row.code} onChange={(e) => setEditDraft((d) => ({ ...d, code: e.target.value }))} className="w-full rounded border px-2 py-1 text-xs text-slate-500" />
                                            <div className="flex gap-1 pt-1">
                                              <IconActionButton
                                                label="Save name and code"
                                                tone="confirm"
                                                onClick={() => run(async () => { await patch(`/admin/capabilities/${row.id}`, { code: editDraft.code, name: editDraft.name, axis_id: row.axis_id, description: row.description || null, evidence_required: row.evidence_required || null, question_guidelines: row.question_guidelines || null }); stopEdit(); await loadCrud(); })}
                                              >
                                                <Check className="h-3.5 w-3.5" />
                                              </IconActionButton>
                                              <IconActionButton label="Cancel editing" onClick={stopEdit}>
                                                <X className="h-3.5 w-3.5" />
                                              </IconActionButton>
                                            </div>
                                          </div>
                                        </td>
                                        <td className="py-2 pr-3 text-slate-800"><span className="line-clamp-2 text-xs text-slate-600" title={row.description ?? ""}>{row.description ?? ""}</span></td>
                                        <td className="py-2 pr-3 text-slate-800"><span className="line-clamp-2 text-xs text-slate-600" title={row.evidence_required ?? ""}>{row.evidence_required ?? ""}</span></td>
                                        <td className="py-2 pr-3 text-slate-800"><span className="line-clamp-2 text-xs text-slate-600" title={row.question_guidelines ?? ""}>{row.question_guidelines ?? ""}</span></td>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex flex-wrap gap-2">
                                          </div>
                                        </td>
                                      </>
                                    ) : (
                                      <>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex min-w-0 items-start gap-2">
                                            <span className="cursor-grab select-none rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500" title="Drag to reorder">::</span>
                                            <div className="min-w-0 flex-1">
                                              <p className="truncate font-medium text-slate-900" title={row.name}>{row.name}</p>
                                              <p className="truncate text-xs text-slate-500" title={row.code}>{row.code}</p>
                                            </div>
                                            <IconEditButton
                                              label="Edit name and code"
                                              onClick={() => startEdit(row.id, { code: row.code, name: row.name })}
                                            />
                                          </div>
                                        </td>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex items-start gap-2">
                                            <span className="line-clamp-2 flex-1" title={row.description ?? ""}>{row.description ?? ""}</span>
                                            <IconEditButton
                                              label={uiMetadata.capabilities.fields.description?.button_label ?? "Edit definition"}
                                              onClick={() => {
                                                setTextEditModal({
                                                  kind: "capability_description",
                                                  id: row.id,
                                                  title: uiMetadata.capabilities.fields.description?.modal_title ?? "Edit capability definition",
                                                  subtitle: row.name,
                                                  helperText: uiMetadata.capabilities.fields.description?.description ?? undefined,
                                                  placeholder: uiMetadata.capabilities.fields.description?.placeholder ?? undefined,
                                                  value: row.description ?? "",
                                                });
                                                setTextEditDraft(row.description ?? "");
                                              }}
                                            />
                                          </div>
                                        </td>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex items-start gap-2">
                                            <span className="line-clamp-2 flex-1" title={row.evidence_required ?? ""}>{row.evidence_required ?? ""}</span>
                                            <IconEditButton
                                              label={uiMetadata.capabilities.fields.evidence_required?.button_label ?? "Edit signals"}
                                              onClick={() => {
                                                setTextEditModal({
                                                  kind: "capability_evidence",
                                                  id: row.id,
                                                  title: uiMetadata.capabilities.fields.evidence_required?.modal_title ?? "Edit evidence signals",
                                                  subtitle: row.name,
                                                  helperText: uiMetadata.capabilities.fields.evidence_required?.description ?? undefined,
                                                  placeholder: uiMetadata.capabilities.fields.evidence_required?.placeholder ?? undefined,
                                                  value: row.evidence_required ?? "",
                                                });
                                                setTextEditDraft(row.evidence_required ?? "");
                                              }}
                                            />
                                          </div>
                                        </td>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex items-start gap-2">
                                            <span className="line-clamp-2 flex-1" title={row.question_guidelines ?? ""}>{row.question_guidelines ?? ""}</span>
                                            <IconEditButton
                                              label={uiMetadata.capabilities.fields.question_guidelines?.button_label ?? "Edit strategy"}
                                              onClick={() => {
                                                setTextEditModal({
                                                  kind: "capability_guideline",
                                                  id: row.id,
                                                  title: uiMetadata.capabilities.fields.question_guidelines?.modal_title ?? "Edit question guidance",
                                                  subtitle: row.name,
                                                  helperText: uiMetadata.capabilities.fields.question_guidelines?.description ?? undefined,
                                                  placeholder: uiMetadata.capabilities.fields.question_guidelines?.placeholder ?? undefined,
                                                  value: row.question_guidelines ?? "",
                                                });
                                                setTextEditDraft(row.question_guidelines ?? "");
                                              }}
                                            />
                                          </div>
                                        </td>
                                        <td className="py-2 pr-3 text-slate-800">
                                          <div className="flex flex-wrap gap-2">
                                            <DangerButton
                                              onClick={() => {
                                                if (!window.confirm(`Delete capability "${row.name}"?`)) return;
                                                run(async () => {
                                                  await remove(`/admin/capabilities/${row.id}`);
                                                  await loadCrud();
                                                });
                                              }}
                                            >
                                              Delete
                                            </DangerButton>
                                          </div>
                                        </td>
                                      </>
                                    )}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
            </Card>
          )}

          {view === "rubrics" && (
            <Card title="Maturity rubrics">
              {capabilityRows.map((capability) => {
                const capabilityId = capability.id;
                const capName = capability.name;
                const capabilityRubrics = rubricRows.filter((r) => r.capability_id === capabilityId);
                const isOpen = openAxes[capabilityId] ?? true;
                return (
                  <div key={`rubric-cap-${capabilityId}`} className="mb-3 rounded-lg border border-slate-200">
                    <button
                      className="flex w-full items-center justify-between bg-slate-50 px-3 py-2 text-left text-sm font-semibold"
                      onClick={() => setOpenAxes((prev) => ({ ...prev, [capabilityId]: !isOpen }))}
                    >
                      <span>{capName}</span>
                      <span>{isOpen ? "−" : "+"}</span>
                    </button>
                    {isOpen ? (
                      <div className="p-2">
                        <div className="mb-3 flex justify-end">
                          <PrimaryActionButton onClick={() => openRubricCreateModal(capabilityId)}>Add rubric</PrimaryActionButton>
                        </div>
                        <SimpleTable
                          headers={sortable(["Maturity level", "Description", "Action"], sortKey, sortDir)}
                          onSort={(idx) => setSort(["maturity_level_id", "description", ""][idx] || "maturity_level_id")}
                          rows={capabilityRubrics.map((row) =>
                            editId === row.id
                              ? [
                                  <div key="m" className="flex items-center gap-2">
                                    <select value={editDraft.maturity_level_id ?? String(row.maturity_level_id)} onChange={(e) => setEditDraft((d) => ({ ...d, maturity_level_id: e.target.value }))} className="rounded border px-2 py-1 text-xs">{levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</select>
                                    <IconActionButton label="Save rubric maturity level" tone="confirm" onClick={() => run(async () => { await patch(`/admin/capability-maturity-rubrics/${row.id}`, { capability_id: row.capability_id, maturity_level_id: Number(editDraft.maturity_level_id), description: row.description }); stopEdit(); await loadCrud(); })}><Check className="h-3.5 w-3.5" /></IconActionButton>
                                    <IconActionButton label="Cancel maturity level edit" onClick={stopEdit}><X className="h-3.5 w-3.5" /></IconActionButton>
                                  </div>,
                                  <div key="d" className="flex items-start gap-2">
                                    <span className="line-clamp-2 flex-1 text-xs text-slate-600" title={row.description}>{row.description}</span>
                                    <IconEditButton
                                      label="Edit rubric description"
                                      onClick={() => {
                                        setTextEditModal({ kind: "rubric_description", id: row.id, title: "Edit rubric description", subtitle: capName, value: row.description });
                                        setTextEditDraft(row.description);
                                      }}
                                    />
                                  </div>,
                                  <DangerButton
                                    key="a"
                                    onClick={() => {
                                      if (!window.confirm("Delete this maturity rubric?")) return;
                                      run(async () => { await remove(`/admin/capability-maturity-rubrics/${row.id}`); await loadCrud(); });
                                    }}
                                  >
                                    Delete
                                  </DangerButton>,
                                ]
                              : [
                                  <div key="m" className="flex items-center gap-2">
                                    <span>{levelLabelById.get(row.maturity_level_id) ?? `Level ${row.maturity_level_id}`}</span>
                                    <IconEditButton label="Edit maturity level" onClick={() => startEdit(row.id, { maturity_level_id: String(row.maturity_level_id) })} />
                                  </div>,
                                  <div key="d" className="flex items-start gap-2">
                                    <span className="line-clamp-2 flex-1" title={row.description}>{row.description}</span>
                                    <IconEditButton
                                      label="Edit rubric description"
                                      onClick={() => {
                                        setTextEditModal({ kind: "rubric_description", id: row.id, title: "Edit rubric description", subtitle: capName, value: row.description });
                                        setTextEditDraft(row.description);
                                      }}
                                    />
                                  </div>,
                                  <DangerButton
                                    key={row.id}
                                    onClick={() => {
                                      if (!window.confirm("Delete this maturity rubric?")) return;
                                      run(async () => { await remove(`/admin/capability-maturity-rubrics/${row.id}`); await loadCrud(); });
                                    }}
                                  >
                                    Delete
                                  </DangerButton>,
                                ]
                          )}
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </Card>
          )}

          {view === "recommendations" && (
            <Card title={uiMetadata.recommendations.title}>
              {capabilityRows.map((capability) => {
                const capabilityId = capability.id;
                const capName = capability.name;
                const capTemplates = quickWinTemplateRows.filter((r) => r.capability_id === capabilityId);
                const isOpen = openAxes[100000 + capabilityId] ?? true;
                return (
                  <div key={`rec-cap-${capabilityId}`} className="mb-3 rounded-lg border border-slate-200">
                    <button
                      className="flex w-full items-center justify-between bg-slate-50 px-3 py-2 text-left text-sm font-semibold"
                      onClick={() => setOpenAxes((prev) => ({ ...prev, [100000 + capabilityId]: !isOpen }))}
                    >
                      <span>{capName}</span>
                      <span>{isOpen ? "−" : "+"}</span>
                    </button>
                    {isOpen ? (
                        <div className="p-2">
                        <div className="mb-3 flex justify-end">
                          <PrimaryActionButton onClick={() => openQuickWinCreateModal(capabilityId)}>Add quick win</PrimaryActionButton>
                        </div>
                        <SimpleTable
                          headers={sortable([
                            "Maturity level",
                            uiMetadata.recommendations.fields.quick_win_guideline?.label ?? "Quick win action",
                            uiMetadata.recommendations.fields.after_text?.label ?? "Expected outcome",
                            uiMetadata.recommendations.fields.owner_hint?.label ?? "Suggested owner",
                            uiMetadata.recommendations.fields.timeline_hint?.label ?? "Timing",
                            "Action",
                          ], sortKey, sortDir)}
                          onSort={(idx) => setSort(["maturity_level_id", "quick_win_guideline", "after_text", "owner_hint", "timeline_hint", ""][idx] || "maturity_level_id")}
                            rows={capTemplates.map((row) =>
                              editId === row.id
                                ? [
                                  <div key="m" className="flex items-center gap-2">
                                    <select value={editDraft.maturity_level_id ?? String(row.maturity_level_id)} onChange={(e) => setEditDraft((d) => ({ ...d, maturity_level_id: e.target.value }))} className="rounded border px-2 py-1 text-xs">{levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</select>
                                    <IconActionButton label="Save quick win settings" tone="confirm" onClick={() => run(async () => { await patch(`/admin/capability-quick-win-templates/${row.id}`, { capability_id: row.capability_id, maturity_level_id: Number(editDraft.maturity_level_id), quick_win_guideline: row.quick_win_guideline, after_text: row.after_text || null, owner_hint: row.owner_hint || null, timeline_hint: row.timeline_hint || null, active: row.active }); stopEdit(); await loadCrud(); })}><Check className="h-3.5 w-3.5" /></IconActionButton>
                                    <IconActionButton label="Cancel editing" onClick={stopEdit}><X className="h-3.5 w-3.5" /></IconActionButton>
                                  </div>,
                                  <QuickWinTextCell key="g" value={row.quick_win_guideline} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_guideline", id: row.id, title: uiMetadata.recommendations.fields.quick_win_guideline?.modal_title ?? "Edit quick win action", subtitle: capName, helperText: uiMetadata.recommendations.fields.quick_win_guideline?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.quick_win_guideline?.placeholder ?? undefined, value: row.quick_win_guideline });
                                    setTextEditDraft(row.quick_win_guideline);
                                  }} label={uiMetadata.recommendations.fields.quick_win_guideline?.button_label ?? "Edit action"} muted />,
                                  <QuickWinTextCell key="at" value={row.after_text ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_after_text", id: row.id, title: uiMetadata.recommendations.fields.after_text?.modal_title ?? "Edit expected outcome", subtitle: capName, helperText: uiMetadata.recommendations.fields.after_text?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.after_text?.placeholder ?? undefined, value: row.after_text ?? "" });
                                    setTextEditDraft(row.after_text ?? "");
                                  }} label={uiMetadata.recommendations.fields.after_text?.button_label ?? "Edit outcome"} muted />,
                                  <QuickWinTextCell key="o" value={row.owner_hint ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_owner_hint", id: row.id, title: uiMetadata.recommendations.fields.owner_hint?.modal_title ?? "Edit suggested owner", subtitle: capName, helperText: uiMetadata.recommendations.fields.owner_hint?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.owner_hint?.placeholder ?? undefined, value: row.owner_hint ?? "" });
                                    setTextEditDraft(row.owner_hint ?? "");
                                  }} label={uiMetadata.recommendations.fields.owner_hint?.button_label ?? "Edit owner"} muted />,
                                  <QuickWinTextCell key="t" value={row.timeline_hint ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_timeline_hint", id: row.id, title: uiMetadata.recommendations.fields.timeline_hint?.modal_title ?? "Edit timing", subtitle: capName, helperText: uiMetadata.recommendations.fields.timeline_hint?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.timeline_hint?.placeholder ?? undefined, value: row.timeline_hint ?? "" });
                                    setTextEditDraft(row.timeline_hint ?? "");
                                  }} label={uiMetadata.recommendations.fields.timeline_hint?.button_label ?? "Edit timing"} muted />,
                                  <DangerButton key="a" onClick={() => {
                                    if (!window.confirm("Delete this quick win template?")) return;
                                    run(async () => { await remove(`/admin/capability-quick-win-templates/${row.id}`); await loadCrud(); });
                                  }}>Delete</DangerButton>,
                                ]
                              : [
                                  <div key="m" className="flex items-center gap-2">
                                    <span>{levelLabelById.get(row.maturity_level_id) ?? `Level ${row.maturity_level_id}`}</span>
                                    <IconEditButton label="Edit quick win settings" onClick={() => startEdit(row.id, { maturity_level_id: String(row.maturity_level_id) })} />
                                  </div>,
                                  <QuickWinTextCell key="g" value={row.quick_win_guideline} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_guideline", id: row.id, title: uiMetadata.recommendations.fields.quick_win_guideline?.modal_title ?? "Edit quick win action", subtitle: capName, helperText: uiMetadata.recommendations.fields.quick_win_guideline?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.quick_win_guideline?.placeholder ?? undefined, value: row.quick_win_guideline });
                                    setTextEditDraft(row.quick_win_guideline);
                                  }} label={uiMetadata.recommendations.fields.quick_win_guideline?.button_label ?? "Edit action"} />,
                                  <QuickWinTextCell key="at" value={row.after_text ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_after_text", id: row.id, title: uiMetadata.recommendations.fields.after_text?.modal_title ?? "Edit expected outcome", subtitle: capName, helperText: uiMetadata.recommendations.fields.after_text?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.after_text?.placeholder ?? undefined, value: row.after_text ?? "" });
                                    setTextEditDraft(row.after_text ?? "");
                                  }} label={uiMetadata.recommendations.fields.after_text?.button_label ?? "Edit outcome"} />,
                                  <QuickWinTextCell key="o" value={row.owner_hint ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_owner_hint", id: row.id, title: uiMetadata.recommendations.fields.owner_hint?.modal_title ?? "Edit suggested owner", subtitle: capName, helperText: uiMetadata.recommendations.fields.owner_hint?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.owner_hint?.placeholder ?? undefined, value: row.owner_hint ?? "" });
                                    setTextEditDraft(row.owner_hint ?? "");
                                  }} label={uiMetadata.recommendations.fields.owner_hint?.button_label ?? "Edit owner"} />,
                                  <QuickWinTextCell key="t" value={row.timeline_hint ?? ""} onEdit={() => {
                                    setTextEditModal({ kind: "quick_win_timeline_hint", id: row.id, title: uiMetadata.recommendations.fields.timeline_hint?.modal_title ?? "Edit timing", subtitle: capName, helperText: uiMetadata.recommendations.fields.timeline_hint?.description ?? undefined, placeholder: uiMetadata.recommendations.fields.timeline_hint?.placeholder ?? undefined, value: row.timeline_hint ?? "" });
                                    setTextEditDraft(row.timeline_hint ?? "");
                                  }} label={uiMetadata.recommendations.fields.timeline_hint?.button_label ?? "Edit timing"} />,
                                  <DangerButton key={row.id} onClick={() => {
                                    if (!window.confirm("Delete this quick win template?")) return;
                                    run(async () => { await remove(`/admin/capability-quick-win-templates/${row.id}`); await loadCrud(); });
                                  }}>Delete</DangerButton>,
                                ]
                          )}
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </Card>
          )}
        </main>
      </div>

      {newCapabilityAxisId !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">Add capability</h3>
            <p className="mt-1 text-sm text-slate-600">
              {axes.find((axis) => axis.id === newCapabilityAxisId)?.name ?? "Selected axis"}
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <input
                value={newCapabilityName}
                onChange={(event) => setNewCapabilityName(event.target.value)}
                placeholder="Capability name"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newCapabilityCode}
                onChange={(event) => setNewCapabilityCode(event.target.value)}
                placeholder="capability_code"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="mt-3 grid gap-3">
              <textarea
                value={newCapabilityDescription}
                onChange={(event) => setNewCapabilityDescription(event.target.value)}
                placeholder={uiMetadata.capabilities.fields.description?.placeholder ?? "Capability definition"}
                className="min-h-[90px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
              <textarea
                value={newCapabilityEvidence}
                onChange={(event) => setNewCapabilityEvidence(event.target.value)}
                placeholder={uiMetadata.capabilities.fields.evidence_required?.placeholder ?? "Evidence signals"}
                className="min-h-[90px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
              <textarea
                value={newCapabilityGuidelines}
                onChange={(event) => setNewCapabilityGuidelines(event.target.value)}
                placeholder={uiMetadata.capabilities.fields.question_guidelines?.placeholder ?? "Question strategy"}
                className="min-h-[110px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setNewCapabilityAxisId(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">Cancel</button>
              <button
                onClick={() => run(createCapability)}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
              >
                Save capability
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {newRubricCapabilityId !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">Add maturity rubric</h3>
            <p className="mt-1 text-sm text-slate-600">
              {capabilityNameById.get(newRubricCapabilityId) ?? "Selected capability"}
            </p>
            <div className="mt-4 grid gap-3">
              <select
                value={newRubricMaturityLevelId}
                onChange={(event) => setNewRubricMaturityLevelId(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {levels.map((level) => (
                  <option key={level.id} value={level.id}>{level.label}</option>
                ))}
              </select>
              <textarea
                value={newRubricDescription}
                onChange={(event) => setNewRubricDescription(event.target.value)}
                placeholder="Describe what this maturity level looks like for this capability..."
                className="min-h-[180px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setNewRubricCapabilityId(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">Cancel</button>
              <button
                onClick={() => run(createRubric)}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
              >
                Save rubric
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {newQuickWinCapabilityId !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">Add quick win template</h3>
            <p className="mt-1 text-sm text-slate-600">
              {capabilityNameById.get(newQuickWinCapabilityId) ?? "Selected capability"}
            </p>
            <div className="mt-4 grid gap-3">
              <select
                value={newQuickWinMaturityLevelId}
                onChange={(event) => setNewQuickWinMaturityLevelId(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {levels.map((level) => (
                  <option key={level.id} value={level.id}>{level.label}</option>
                ))}
              </select>
            </div>
            <div className="mt-3 grid gap-3">
              <textarea
                value={newQuickWinGuideline}
                onChange={(event) => setNewQuickWinGuideline(event.target.value)}
                placeholder={uiMetadata.recommendations.fields.quick_win_guideline?.placeholder ?? "Quick win action"}
                className="min-h-[130px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
              <textarea
                value={newQuickWinAfterText}
                onChange={(event) => setNewQuickWinAfterText(event.target.value)}
                placeholder={uiMetadata.recommendations.fields.after_text?.placeholder ?? "Expected outcome"}
                className="min-h-[90px] rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              />
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={newQuickWinOwnerHint}
                  onChange={(event) => setNewQuickWinOwnerHint(event.target.value)}
                  placeholder={uiMetadata.recommendations.fields.owner_hint?.placeholder ?? "Suggested owner"}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={newQuickWinTimelineHint}
                  onChange={(event) => setNewQuickWinTimelineHint(event.target.value)}
                  placeholder={uiMetadata.recommendations.fields.timeline_hint?.placeholder ?? "Timing"}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setNewQuickWinCapabilityId(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">Cancel</button>
              <button
                onClick={() => run(createQuickWinTemplate)}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
              >
                Save quick win
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {createModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">
              {createModal === "sector" ? "Add sector" : createModal === "size" ? "Add company size" : createModal === "region" ? "Add region" : createModal === "axis" ? "Add axis" : "Add maturity level"}
            </h3>
            <div className="mt-3 space-y-3">
              {createModal === "level" ? (
                <>
                  <input value={newLevelNumber} onChange={(e) => setNewLevelNumber(e.target.value)} placeholder="level number" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                  <input value={newLevelLabel} onChange={(e) => setNewLevelLabel(e.target.value)} placeholder="label" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                  <input value={newLevelDescription} onChange={(e) => setNewLevelDescription(e.target.value)} placeholder="description (optional)" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </>
              ) : createModal === "region" ? (
                <input value={newRegionName} onChange={(e) => setNewRegionName(e.target.value)} placeholder="Region name" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              ) : createModal === "axis" ? (
                <>
                  <input value={newAxisCode} onChange={(e) => setNewAxisCode(e.target.value)} placeholder="axis_code" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                  <input value={newAxisName} onChange={(e) => setNewAxisName(e.target.value)} placeholder="Axis name" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                  <textarea
                    value={newAxisDescription}
                    onChange={(e) => setNewAxisDescription(e.target.value)}
                    placeholder={uiMetadata.axes.fields.description?.placeholder ?? "Axis definition"}
                    className="min-h-[120px] w-full rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
                  />
                  <textarea
                    value={newAxisGuidelines}
                    onChange={(e) => setNewAxisGuidelines(e.target.value)}
                    placeholder={uiMetadata.axes.fields.question_guidelines?.placeholder ?? "Axis question strategy"}
                    className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
                  />
                </>
              ) : (
                <>
                  <input
                    value={createModal === "sector" ? newSectorCode : newSizeCode}
                    onChange={(e) => (createModal === "sector" ? setNewSectorCode(e.target.value) : setNewSizeCode(e.target.value))}
                    placeholder="code"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={createModal === "sector" ? newSectorName : newSizeName}
                    onChange={(e) => (createModal === "sector" ? setNewSectorName(e.target.value) : setNewSizeName(e.target.value))}
                    placeholder="name"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </>
              )}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setCreateModal(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">Cancel</button>
              <button
                onClick={() =>
                  run(async () => {
                    if (createModal === "sector") {
                      await post("/admin/reference/sectors", { code: newSectorCode, name: newSectorName });
                      setNewSectorCode("");
                      setNewSectorName("");
                    } else if (createModal === "size") {
                      await post("/admin/reference/company-sizes", { code: newSizeCode, name: newSizeName });
                      setNewSizeCode("");
                      setNewSizeName("");
                    } else if (createModal === "region") {
                      await post("/admin/reference/regions", { name: newRegionName });
                      setNewRegionName("");
                    } else if (createModal === "axis") {
                      await createAxis();
                      return;
                    } else {
                      await post("/admin/reference/maturity-levels", {
                        level_number: Number(newLevelNumber),
                        label: newLevelLabel,
                        description: newLevelDescription || null,
                      });
                      setNewLevelNumber("1");
                      setNewLevelLabel("");
                      setNewLevelDescription("");
                    }
                    setCreateModal(null);
                    await loadCrud();
                  })
                }
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {textEditModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">{textEditModal.title}</h3>
            <p className="mt-1 text-sm text-slate-600">{textEditModal.subtitle ?? ""}</p>
            {textEditModal.helperText ? (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                {textEditModal.helperText}
              </div>
            ) : null}
            <textarea
              value={textEditDraft}
              onChange={(e) => setTextEditDraft(e.target.value)}
              className="mt-4 min-h-[260px] w-full rounded-lg border border-slate-300 px-3 py-3 text-sm leading-6"
              placeholder={textEditModal.placeholder ?? "Write the text used by the LLM..."}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setTextEditModal(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">Cancel</button>
              <button
                onClick={() =>
                  run(async () => {
                    if (
                      textEditModal.kind === "axis_description" ||
                      textEditModal.kind === "axis_guideline"
                    ) {
                      const row = axes.find((item) => item.id === textEditModal.id);
                      if (!row) throw new Error("Axis not found");
                      await patch(`/admin/reference/axes/${row.id}`, {
                        code: row.code,
                        name: row.name,
                        sort_order: row.sort_order,
                        description: textEditModal.kind === "axis_description" ? textEditDraft || null : row.description || null,
                        question_guidelines: textEditModal.kind === "axis_guideline" ? textEditDraft || null : row.question_guidelines || null,
                      });
                    } else if (
                      textEditModal.kind === "capability_description" ||
                      textEditModal.kind === "capability_evidence" ||
                      textEditModal.kind === "capability_guideline"
                    ) {
                      const row = capabilities.find((item) => item.id === textEditModal.id);
                      if (!row) throw new Error("Capability not found");
                      await patch(`/admin/capabilities/${row.id}`, {
                        code: row.code,
                        name: row.name,
                        axis_id: row.axis_id,
                        sort_order: row.sort_order,
                        description: textEditModal.kind === "capability_description" ? textEditDraft || null : row.description || null,
                        evidence_required: textEditModal.kind === "capability_evidence" ? textEditDraft || null : row.evidence_required || null,
                        question_guidelines: textEditModal.kind === "capability_guideline" ? textEditDraft || null : row.question_guidelines || null,
                      });
                    } else if (textEditModal.kind === "level_description") {
                      const row = levels.find((item) => item.id === textEditModal.id);
                      if (!row) throw new Error("Maturity level not found");
                      await patch(`/admin/reference/maturity-levels/${row.id}`, {
                        level_number: row.level_number,
                        label: row.label,
                        description: textEditDraft || null,
                      });
                    } else if (textEditModal.kind === "rubric_description") {
                      const row = rubrics.find((item) => item.id === textEditModal.id);
                      if (!row) throw new Error("Rubric not found");
                      await patch(`/admin/capability-maturity-rubrics/${row.id}`, {
                        capability_id: row.capability_id,
                        maturity_level_id: row.maturity_level_id,
                        description: textEditDraft,
                      });
                    } else {
                      const row = quickWinTemplates.find((item) => item.id === textEditModal.id);
                      if (!row) throw new Error("Quick win template not found");
                      await patch(`/admin/capability-quick-win-templates/${row.id}`, {
                        capability_id: row.capability_id,
                        maturity_level_id: row.maturity_level_id,
                        quick_win_guideline: textEditModal.kind === "quick_win_guideline" ? textEditDraft : row.quick_win_guideline,
                        after_text: textEditModal.kind === "quick_win_after_text" ? textEditDraft || null : row.after_text || null,
                        owner_hint: textEditModal.kind === "quick_win_owner_hint" ? textEditDraft || null : row.owner_hint || null,
                        timeline_hint: textEditModal.kind === "quick_win_timeline_hint" ? textEditDraft || null : row.timeline_hint || null,
                        active: row.active,
                      });
                    }
                    setTextEditModal(null);
                    await loadCrud();
                  })
                }
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

