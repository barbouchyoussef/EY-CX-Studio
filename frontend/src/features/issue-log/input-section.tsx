/**
 * Choosing which analyses go into a run.
 *
 * Grouped by source kind and searchable, because a consultant with a year of work behind them is
 * picking four things out of a hundred.
 */

import { useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { KIND_META, type Input } from "./types";

export default function InputSection({
  kind, items, isOpen, onToggleOpen, selected, keyOf, onToggle, onSetSection,
}: {
  kind: string; items: Input[]; isOpen: boolean; onToggleOpen: () => void;
  selected: Set<string>; keyOf: (i: Input) => string;
  onToggle: (i: Input) => void; onSetSection: (items: Input[], on: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const meta = KIND_META[kind] ?? { label: kind, icon: <span />, tint: "bg-slate-50 text-slate-500" };
  const selCount = items.filter((i) => selected.has(keyOf(i))).length;
  const allOn = selCount === items.length;
  const showSearch = items.length > 10;
  const q = query.trim().toLowerCase();
  const visible = q ? items.filter((i) => i.title.toLowerCase().includes(q)) : items;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200">
      <button onClick={onToggleOpen} className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${meta.tint}`}>{meta.icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-800">{meta.label}</span>
          <span className="block text-xs text-slate-400">{items.length} {items.length === 1 ? "analysis" : "analyses"}</span>
        </span>
        {selCount > 0 && <span className="rounded-full bg-ey-navy px-2.5 py-0.5 text-[11px] font-bold text-white">{selCount} selected</span>}
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${isOpen ? "rotate-180" : ""}`} />
      </button>
      {isOpen && (
        <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3">
          <div className="mb-2 flex items-center gap-2">
            {showSearch && (
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input
                  value={query} onChange={(e) => setQuery(e.target.value)}
                  placeholder={`Search ${meta.label.toLowerCase()}…`}
                  className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm text-slate-700 outline-none focus:border-slate-400"
                />
              </div>
            )}
            <button onClick={() => onSetSection(visible, !allOn)}
              className="ml-auto shrink-0 text-[11px] font-semibold text-slate-500 hover:text-slate-800">
              {allOn ? "Clear all" : q ? "Select matches" : "Select all"}
            </button>
          </div>
          {visible.length === 0 ? (
            <p className="py-3 text-center text-xs text-slate-400">No matches.</p>
          ) : (
            <div className="grid max-h-72 gap-1.5 overflow-y-auto sm:grid-cols-2">
              {visible.map((i) => {
                const on = selected.has(keyOf(i));
                return (
                  <button key={keyOf(i)} onClick={() => onToggle(i)}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
                      on ? "border-ey-navy bg-white" : "border-slate-200 bg-white hover:border-slate-300"}`}>
                    <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                      on ? "border-ey-navy bg-ey-navy text-white" : "border-slate-300"}`}>
                      {on && <Check className="h-3 w-3" />}
                    </span>
                    <span className="truncate text-slate-700">{i.title}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── page ─────────────────────────── */

