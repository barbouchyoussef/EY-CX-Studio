/**
 * Printing the report: the same markdown, rendered to a standalone HTML document.
 *
 * Printing happens in a detached window, so the document has to carry its own styles -- nothing
 * from the app's stylesheet reaches it. That is why the CSS is inline here rather than in a
 * class name.
 *
 * NOTE: this parses the same grammar as `markdown.tsx`, which renders it to React for the screen.
 * Keep the two in step: syntax added there and not here prints as literal markdown.
 */

const _escapeHtml = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Inline markdown → HTML string: `code`, **bold**, *italic* (text is escaped first). */
function _inlineHtml(text: string): string {
  let t = _escapeHtml(text);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  return t;
}

/** Convert the report markdown to a clean, self-contained HTML body for printing.
    Mirrors MarkdownRenderer's block handling but emits semantic HTML the print CSS styles. */
function reportMarkdownToHtml(md: string): string {
  const lines = md.split("\n");
  const out: string[] = [];
  let listItems: string[] = [];
  let tableHeader: string[] = [];
  let tableRows: string[][] = [];
  let inTable = false;

  const flushList = () => {
    if (listItems.length === 0) return;
    out.push("<ul>" + listItems.map((it) => `<li>${_inlineHtml(it)}</li>`).join("") + "</ul>");
    listItems = [];
  };
  const flushTable = () => {
    if (tableHeader.length === 0 && tableRows.length === 0) return;
    const head = "<tr>" + tableHeader.map((h) => `<th>${_inlineHtml(h.trim())}</th>`).join("") + "</tr>";
    const body = tableRows
      .map((r) => "<tr>" + r.map((c) => `<td>${_inlineHtml(c.trim())}</td>`).join("") + "</tr>")
      .join("");
    out.push(`<table><thead>${head}</thead><tbody>${body}</tbody></table>`);
    tableHeader = [];
    tableRows = [];
    inTable = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushList();
      if (/^[|\s:-]+$/.test(trimmed)) continue; // separator row
      const cells = trimmed.slice(1, -1).split("|");
      if (!inTable) {
        inTable = true;
        tableHeader = cells;
      } else {
        tableRows.push(cells);
      }
      continue;
    } else if (inTable) {
      flushTable();
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
      continue;
    } else if (listItems.length > 0) {
      flushList();
    }

    if (trimmed.startsWith("> ")) {
      const quote = trimmed.replace(/^>\s*\[![A-Za-z]+\]\s*/, "").replace(/^>\s*/, "");
      out.push(`<blockquote>${_inlineHtml(quote)}</blockquote>`);
    } else if (trimmed.startsWith("# ")) {
      out.push(`<h1>${_inlineHtml(trimmed.slice(2))}</h1>`);
    } else if (trimmed.startsWith("## ")) {
      out.push(`<h2>${_inlineHtml(trimmed.slice(3))}</h2>`);
    } else if (trimmed.startsWith("### ")) {
      out.push(`<h3>${_inlineHtml(trimmed.slice(4))}</h3>`);
    } else if (trimmed === "---" || trimmed === "***") {
      // section headings already carry a divider; skip stray rules
    } else if (trimmed.length > 0) {
      out.push(`<p>${_inlineHtml(trimmed)}</p>`);
    }
  }
  flushList();
  flushTable();
  return out.join("\n");
}

const PDF_PRINT_CSS = `
  @page { size: A4; margin: 18mm 16mm 20mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #24263a; line-height: 1.6; font-size: 11pt; margin: 0;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .ey-cover { border-bottom: 3px solid #C5A04F; padding-bottom: 14px; margin-bottom: 28px; }
  .ey-mark { font-weight: 800; letter-spacing: -0.5px; font-size: 22pt; color: #1A1F36; }
  .ey-mark span { color: #C5A04F; }
  .ey-sub { margin-top: 4px; font-size: 9pt; letter-spacing: 2px; text-transform: uppercase; color: #8a8f9c; }
  h1 { font-size: 19pt; color: #1A1F36; margin: 4px 0 14px; font-weight: 800; letter-spacing: -0.4px; }
  h2 { font-size: 14pt; color: #1A1F36; margin: 26px 0 10px; padding-bottom: 6px;
       border-bottom: 1px solid #e5e7eb; font-weight: 700; page-break-after: avoid; }
  h3 { font-size: 11.5pt; color: #2f3244; margin: 18px 0 6px; font-weight: 700; page-break-after: avoid; }
  p { margin: 8px 0; }
  strong { color: #1A1F36; font-weight: 700; }
  code { background: #f1f2f6; padding: 1px 5px; border-radius: 4px; font-family: "Consolas", monospace; font-size: 0.9em; }
  ul { margin: 10px 0; padding-left: 20px; }
  li { margin: 4px 0; }
  li::marker { color: #C5A04F; }
  blockquote { border-left: 4px solid #C5A04F; background: #faf6ec; margin: 14px 0;
               padding: 8px 14px; border-radius: 0 6px 6px 0; page-break-inside: avoid; }
  table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 9.5pt; page-break-inside: avoid; }
  thead th { background: #1A1F36; color: #fff; text-align: left; padding: 7px 9px;
             font-size: 8.5pt; text-transform: uppercase; letter-spacing: 0.4px; }
  tbody td { padding: 6px 9px; border-bottom: 1px solid #eceef2; vertical-align: top; }
  tbody tr:nth-child(even) { background: #f8f9fb; }
  hr { border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }
`;

/** Open a print-optimized window and trigger the browser's Save-as-PDF. */
export function exportReportPdf(markdown: string, sessionTitle: string) {
  const body = reportMarkdownToHtml(markdown);
  // NOTE: do NOT pass noopener/noreferrer here -- window.open() returns null when noopener is set,
  // and we need the window reference to write the report into it and call print().
  const win = window.open("", "_blank", "width=900,height=1200");
  if (!win) {
    alert("Please allow pop-ups for this site to export the report as PDF.");
    return;
  }
  const cover = `
    <div class="ey-cover">
      <div class="ey-mark">EY<span>.</span></div>
      <div class="ey-sub">CX Assessment Hub · Desk Research</div>
    </div>`;
  win.document.write(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"/>` +
      `<title>${_escapeHtml(sessionTitle)} — Executive Report</title>` +
      `<style>${PDF_PRINT_CSS}</style></head><body>${cover}${body}</body></html>`,
  );
  win.document.close();
  win.focus();
  // Give the new document a beat to lay out before invoking the print dialog.
  setTimeout(() => {
    win.print();
  }, 350);
}

