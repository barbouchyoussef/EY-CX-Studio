/**
 * The small markdown subset the desk-research report is written in, rendered to React.
 *
 * Hand-rolled rather than a library because the report only ever uses headings, bold, italic,
 * inline code, bullet lists and pipe tables -- and because every element carries the report's own
 * typography, which a general renderer would have to be configured out of.
 *
 * NOTE: `pdf-export.ts` parses the SAME grammar to produce an HTML string for printing. The two
 * are separate because one emits React nodes and the other a string, and an abstraction over both
 * would cost more than it saves -- but they will drift. Adding syntax here without adding it there
 * means the PDF quietly renders it as literal asterisks.
 */

import React from "react";

function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(<strong key={key++} className="font-semibold text-ey-navy">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      parts.push(
        <code key={key++} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-slate-800">
          {tok.slice(1, -1)}
        </code>,
      );
    } else {
      parts.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function MarkdownRenderer({ content }: { content: string }) {
  if (!content) return null;

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let tableHeader: string[] = [];
  let tableRows: string[][] = [];
  let inTable = false;
  let listItems: string[] = [];

  const flushList = (key: string) => {
    if (listItems.length === 0) return;
    const items = listItems;
    listItems = [];
    elements.push(
      <ul key={key} className="my-3 ml-5 list-disc space-y-1.5 text-[13.5px] leading-relaxed text-slate-700 marker:text-ey-gold">
        {items.map((it, i) => (
          <li key={i}>{renderInline(it)}</li>
        ))}
      </ul>,
    );
  };

  const flushTable = (key: string) => {
    if (tableRows.length === 0 && tableHeader.length === 0) return;
    const header = tableHeader;
    const rows = tableRows;
    tableHeader = [];
    tableRows = [];
    inTable = false;
    elements.push(
      <div key={key} className="my-4 overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <tr>
              {header.map((h, i) => (
                <th key={i} className="border-b border-slate-200 px-4 py-2.5 align-top">{renderInline(h.trim())}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r, ri) => (
              <tr key={ri} className="align-top">
                {r.map((c, ci) => (
                  <td key={ci} className="px-4 py-2.5 text-slate-700">{renderInline(c.trim())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    // Tables
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushList(`l-${idx}`);
      if (/^[|\s:-]+$/.test(trimmed)) return; // separator row
      const cells = trimmed.slice(1, -1).split("|");
      if (!inTable) {
        inTable = true;
        tableHeader = cells;
      } else {
        tableRows.push(cells);
      }
      return;
    } else if (inTable) {
      flushTable(`t-${idx}`);
    }

    // List items — grouped into a single <ul>
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
      return;
    } else if (listItems.length > 0) {
      flushList(`l-${idx}`);
    }

    // Blockquotes
    if (trimmed.startsWith(">")) {
      const quote = trimmed.replace(/^>\s*\[![A-Za-z]+\]\s*/, "").replace(/^>\s*/, "");
      elements.push(
        <blockquote
          key={idx}
          className="my-4 rounded-r-lg border-l-4 border-ey-gold bg-ey-gold/[0.06] py-3 pl-4 pr-4 text-[13.5px] leading-relaxed text-slate-700"
        >
          {renderInline(quote)}
        </blockquote>,
      );
      return;
    }

    // Headings
    const heading = trimmed.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      if (level === 1) {
        elements.push(<h1 key={idx} className="mb-4 mt-1 text-2xl font-bold tracking-tight text-ey-navy">{renderInline(text)}</h1>);
      } else if (level === 2) {
        elements.push(<h2 key={idx} className="mb-3 mt-8 border-b border-slate-200 pb-2 text-lg font-bold text-ey-navy">{renderInline(text)}</h2>);
      } else if (level === 3) {
        elements.push(<h3 key={idx} className="mb-2 mt-6 text-[15px] font-bold text-slate-800">{renderInline(text)}</h3>);
      } else {
        elements.push(<h4 key={idx} className="mb-1.5 mt-4 text-[13.5px] font-semibold uppercase tracking-wide text-slate-500">{renderInline(text)}</h4>);
      }
    } else if (trimmed === "---" || trimmed === "***") {
      // Section headings already carry a divider; skip stray horizontal rules to reduce clutter.
    } else if (trimmed.length > 0) {
      elements.push(<p key={idx} className="my-2.5 text-[13.5px] leading-[1.7] text-slate-700">{renderInline(trimmed)}</p>);
    }
  });

  flushList("l-end");
  flushTable("t-end");

  return <div className="max-w-none">{elements}</div>;
}

/* ------------------------------------------------------------------ */
/*  PDF export (browser-native print, no dependency)                   */
/* ------------------------------------------------------------------ */

