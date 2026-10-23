/**
 * The pieces every admin screen is built from: table shells, row actions, and paging.
 *
 * The dashboard edits ten kinds of reference data through what is essentially the same screen --
 * a sortable table, an edit button per row, a delete confirm, a pager. These are that screen,
 * parameterised. CrudSimple and CrudNameOnly go further and are the whole editor for the tables
 * that have nothing but a code and a name.
 *
 * Nothing here knows what it is showing. Adding an eleventh reference table should mean adding
 * data, not another copy of this.
 */

import { useState, type ReactNode } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";

export type SortDir = "asc" | "desc";

/** Rows per page. Lives here because every admin table pages the same way. */
export const PAGE_SIZE = 10;

/** The shape CrudNameOnly edits: reference data whose only content is its name. */
export type NamedRow = { id: number; name: string };

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-lg font-semibold">{title}</h3>
      {children}
    </div>
  );
}

export function IconEditButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-300 text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
    >
      <Pencil className="h-3.5 w-3.5" />
    </button>
  );
}

export function IconActionButton({
  label,
  onClick,
  tone = "neutral",
  children,
}: {
  label: string;
  onClick: () => void;
  tone?: "neutral" | "confirm";
  children: ReactNode;
}) {
  const className =
    tone === "confirm"
      ? "inline-flex h-7 w-7 items-center justify-center rounded-md border border-emerald-300 bg-emerald-50 text-emerald-700 transition hover:bg-emerald-100"
      : "inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-300 text-slate-600 transition hover:bg-slate-50";
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className={className}>
      {children}
    </button>
  );
}

export function PrimaryActionButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex shrink-0 whitespace-nowrap items-center justify-center gap-1.5 rounded-lg bg-slate-950 px-3.5 py-2 text-sm font-semibold leading-none text-white shadow-sm transition hover:bg-slate-800"
    >
      <Plus className="h-4 w-4 shrink-0" />
      <span className="whitespace-nowrap">{children}</span>
    </button>
  );
}

export function DangerButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-md bg-rose-600 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700"
    >
      <Trash2 className="h-3.5 w-3.5" />
      {children}
    </button>
  );
}

export function QuickWinTextCell({
  value,
  onEdit,
  label,
  muted = false,
}: {
  value: string;
  onEdit: () => void;
  label: string;
  muted?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className={`line-clamp-2 flex-1 ${muted ? "text-xs text-slate-600" : ""}`} title={value}>{value}</span>
      <IconEditButton label={label} onClick={onEdit} />
    </div>
  );
}

export function CrudSimple({
  title,
  rows,
  onAdd,
  onDelete,
}: {
  title: string;
  rows: { id: number; code: string; name: string }[];
  onAdd: () => void;
  onDelete: (id: number) => void;
}) {
  return (
    <Card title={title}>
      <div className="mb-4">
        <PrimaryActionButton onClick={onAdd}>{title === "Sectors" ? "Add sector" : "Add company size"}</PrimaryActionButton>
      </div>
      <SimpleTable
        headers={["Code", "Name", "Action"]}
        rows={rows.map((item) => [
          item.code,
          item.name,
          <DangerButton key={item.id} onClick={() => onDelete(item.id)}>Delete</DangerButton>,
        ])}
      />
    </Card>
  );
}

export function CrudNameOnly({
  title,
  rows,
  onAdd,
  onRename,
  onDelete,
}: {
  title: string;
  rows: NamedRow[];
  onAdd: () => void;
  onRename: (id: number, name: string) => void;
  onDelete: (id: number) => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");

  return (
    <Card title={title}>
      <div className="mb-4">
        <PrimaryActionButton onClick={onAdd}>Add region</PrimaryActionButton>
      </div>
      <SimpleTable
        headers={["Name", "Action"]}
        rows={rows.map((item) => [
          editingId === item.id ? (
            <div key={`edit-${item.id}`} className="flex max-w-md items-center gap-2">
              <input
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
              <IconActionButton
                label="Save region"
                tone="confirm"
                onClick={() => {
                  onRename(item.id, draftName);
                  setEditingId(null);
                }}
              >
                <Check className="h-3.5 w-3.5" />
              </IconActionButton>
              <IconActionButton label="Cancel editing" onClick={() => setEditingId(null)}>
                <X className="h-3.5 w-3.5" />
              </IconActionButton>
            </div>
          ) : (
            <div key={`name-${item.id}`} className="flex max-w-md items-center gap-2">
              <span className="flex-1">{item.name}</span>
              <IconEditButton
                label="Edit region name"
                onClick={() => {
                  setEditingId(item.id);
                  setDraftName(item.name);
                }}
              />
            </div>
          ),
          <DangerButton key={`delete-${item.id}`} onClick={() => {
            if (!window.confirm(`Delete region "${item.name}"?`)) return;
            onDelete(item.id);
          }}>Delete</DangerButton>,
        ])}
      />
    </Card>
  );
}

export function SimpleTable({
  headers,
  rows,
  onSort,
}: {
  headers: string[];
  rows: (ReactNode[] | string[])[];
  onSort?: (index: number) => void;
}) {
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[820px] table-fixed text-left text-sm">
        <thead className="text-slate-500">
          <tr>
            {headers.map((header, index) => (
              <th key={header + index} className="py-2 pr-3">
                {onSort && !header.includes("↕") ? (
                  <button onClick={() => onSort(index)} className="text-left hover:text-slate-800">
                    {header}
                  </button>
                ) : (
                  header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className="border-t border-slate-100 align-top">
              {row.map((cell, i) => (
                <td key={i} className="py-2 pr-3 text-slate-800">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pager({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (page: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <div className="mt-3 flex items-center justify-end gap-2">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="rounded border px-3 py-1 text-xs disabled:opacity-40">Prev</button>
      <span className="text-xs text-slate-600">{page}/{totalPages}</span>
      <button disabled={page >= totalPages} onClick={() => onPage(page + 1)} className="rounded border px-3 py-1 text-xs disabled:opacity-40">Next</button>
    </div>
  );
}

export function paginate<T>(rows: T[], page: number): { items: T[]; totalPages: number } {
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  return { items: rows.slice(start, start + PAGE_SIZE), totalPages };
}

export function sortRows<T extends Record<string, unknown>>(rows: T[], key: string, dir: SortDir): T[] {
  return [...rows].sort((a, b) => {
    const rawA = a[key];
    const rawB = b[key];
    if (typeof rawA === "number" && typeof rawB === "number") {
      const result = rawA - rawB;
      return dir === "asc" ? result : -result;
    }
    const av = String(rawA ?? "").toLowerCase();
    const bv = String(rawB ?? "").toLowerCase();
    if (av === bv) return 0;
    const result = av > bv ? 1 : -1;
    return dir === "asc" ? result : -result;
  });
}

/** Pass-through: header sort indicators were never enabled.
 *
 * The body that appended a "↕" marker sat after an unconditional `return headers`, so it has
 * been unreachable since the first commit. Sorting itself is unaffected -- that runs through
 * `sortRows`, which does use `sortKey` and `sortDir`. The dead line is removed rather than
 * revived, because switching the indicator on now would be a visual change, not a cleanup.
 * Kept as a function so the three call sites still read as "these headers are sortable".
 */
export function sortable(headers: string[], _sortKey: string, _sortDir: SortDir) {
  return headers;
}

