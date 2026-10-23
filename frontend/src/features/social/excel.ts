/**
 * The social report as an Excel workbook.
 *
 * A client deliverable, so it is styled rather than dumped: EY charcoal and gold, a header block,
 * one sheet per concern. That styling is most of the length here — the data it writes was all
 * computed on the backend and is carried through untouched.
 *
 * Kept out of the module's page for the same reason as the interview module's export: it is a
 * pure function of a report with no React in it, and three hundred lines of column widths and
 * cell fills should not sit between the page's state and its markup.
 */

import ExcelJS from "exceljs";
import type { ScrapingResponse } from "../../types/scraping";
import { sourceLabel } from "../../types/scraping";

/* ------------------------------------------------------------------ */
/*  Excel Export                                                       */
/* ------------------------------------------------------------------ */
export async function exportToExcel(data: ScrapingResponse) {
  const wb = new ExcelJS.Workbook();
  wb.creator = "EY CX Studio";
  wb.created = new Date();

  const EY_CHARCOAL = "FF2E2E38";
  const EY_GOLD = "FFC5A04F";

  const formatExcelDate = (dateStr: string | null): string => {
    if (!dateStr) return "—";
    try {
      const d = new Date(dateStr);
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
      }
    } catch {
      // Unparseable dates are written through as the platform supplied them.
    }
    return dateStr;
  };

  /* ---- Shared styling helpers ---- */
  const styleHeader = (row: ExcelJS.Row) => {
    row.height = 26;
    row.eachCell((cell) => {
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: EY_CHARCOAL } };
      cell.font = { color: { argb: "FFFFFFFF" }, bold: true, size: 11 };
      cell.alignment = { vertical: "middle", horizontal: "left" };
      cell.border = { bottom: { style: "medium", color: { argb: EY_GOLD } } };
    });
  };
  const titleRow = (sheet: ExcelJS.Worksheet, text: string) => {
    const row = sheet.addRow([text]);
    row.font = { bold: true, size: 14, color: { argb: EY_CHARCOAL } };
    row.height = 24;
    sheet.addRow([]);
    return row;
  };

  const report = data.detailed_report;

  /* ---- Sheet 1: Executive summary (only when a report exists) ---- */
  if (report) {
    const s = wb.addWorksheet("Summary", { properties: { defaultColWidth: 20 } });
    s.getColumn(1).width = 26;
    s.getColumn(2).width = 96;

    titleRow(s, `Social & Web CX Analysis — ${data.brand_name}`);

    const meta: [string, string][] = [
      ["Generated", new Date(data.scraped_at).toLocaleString()],
      ["Reviews analysed", String(data.total_reviews)],
      ["Channels covered", String(report.channel_breakdown.length)],
    ];
    if (report.overall_sentiment) {
      const os = report.overall_sentiment;
      meta.push(["Sentiment (positive)", `${os.positive_pct}%`]);
      meta.push(["Sentiment (neutral)", `${os.neutral_pct}%`]);
      meta.push(["Sentiment (negative)", `${os.negative_pct}%`]);
      meta.push(["Reviews classified", String(os.classified_count)]);
    }
    for (const [k, v] of meta) {
      const r = s.addRow([k, v]);
      r.getCell(1).font = { bold: true, size: 10, color: { argb: "FF6B6B76" } };
      r.getCell(2).alignment = { vertical: "middle" };
    }

    s.addRow([]);
    const execHead = s.addRow(["Executive summary", ""]);
    styleHeader(execHead);
    const execRow = s.addRow(["", report.executive_summary]);
    execRow.getCell(2).alignment = { wrapText: true, vertical: "top" };
    execRow.height = 110;

    s.addRow([]);
    const methodHead = s.addRow(["Methodology", ""]);
    styleHeader(methodHead);
    const methodRow = s.addRow(["", report.methodology_note]);
    methodRow.getCell(2).alignment = { wrapText: true, vertical: "top" };
    methodRow.height = 46;

    if (report.website_assessment) {
      s.addRow([]);
      const webHead = s.addRow(["Website assessment", ""]);
      styleHeader(webHead);
      const webRow = s.addRow(["", report.website_assessment]);
      webRow.getCell(2).alignment = { wrapText: true, vertical: "top" };
      webRow.height = 70;
    }

    /* ---- Sheet 2: Friction points ---- */
    const f = wb.addWorksheet("Friction Points", { properties: { defaultColWidth: 20 } });
    const fHead = f.addRow(["#", "Theme", "Source", "Mentions", "Share", "Description", "Supporting evidence"]);
    styleHeader(fHead);
    f.getColumn(1).width = 6;
    f.getColumn(2).width = 34;
    f.getColumn(3).width = 18;
    f.getColumn(4).width = 11;
    f.getColumn(5).width = 10;
    f.getColumn(6).width = 62;
    f.getColumn(7).width = 62;
    report.top_friction_points.forEach((fp, i) => {
      const row = f.addRow([
        i + 1,
        fp.theme,
        sourceLabel(fp.source),
        fp.mention_count ?? "—",
        fp.share_pct != null ? `${fp.share_pct}%` : "—",
        fp.description,
        (fp.supporting_evidence || []).join("\n"),
      ]);
      row.height = 62;
      row.getCell(1).alignment = { vertical: "top", horizontal: "center" };
      row.getCell(2).alignment = { wrapText: true, vertical: "top" };
      row.getCell(2).font = { bold: true };
      row.getCell(3).alignment = { vertical: "top" };
      row.getCell(4).alignment = { vertical: "top", horizontal: "center" };
      row.getCell(5).alignment = { vertical: "top", horizontal: "center" };
      row.getCell(6).alignment = { wrapText: true, vertical: "top" };
      row.getCell(7).alignment = { wrapText: true, vertical: "top" };
    });
    f.views = [{ state: "frozen", ySplit: 1 }];

    /* ---- Sheet: Evidence (computed figures, so the deck can cite them directly) ---- */
    const ev = report.evidence;
    if (ev && ev.reviews_classified > 0) {
      const e = wb.addWorksheet("Evidence", { properties: { defaultColWidth: 18 } });
      e.getColumn(1).width = 34;
      e.getColumn(2).width = 14;
      e.getColumn(3).width = 14;
      e.getColumn(4).width = 14;
      e.getColumn(5).width = 14;
      e.getColumn(6).width = 16;

      titleRow(e, "Computed evidence");
      const cov = e.addRow([`${ev.reviews_classified} of ${ev.reviews_collected} collected reviews classified`]);
      cov.getCell(1).font = { italic: true, size: 10, color: { argb: "FF6B6B76" } };
      e.addRow([]);

      if (ev.platform_sentiment.length > 0) {
        styleHeader(e.addRow(["Channel", "Analysed", "Avg rating", "Positive", "Neutral", "Negative"]));
        ev.platform_sentiment.forEach((p) => {
          e.addRow([
            p.platform,
            p.classified_count,
            p.avg_rating ?? "—",
            `${p.positive_pct}%`,
            `${p.neutral_pct}%`,
            `${p.negative_pct}%`,
          ]).getCell(1).font = { bold: true };
        });
        e.addRow([]);
      }

      if (ev.rating_distribution) {
        const d = ev.rating_distribution;
        styleHeader(e.addRow(["Rating spread", "1★", "2★", "3★", "4★", "5★"]));
        e.addRow([`Average ${d.average ?? "—"}/5 · ${d.total} rated`, d.one, d.two, d.three, d.four, d.five]);
        e.addRow([]);
      }

      if (ev.top_complaints.length > 0) {
        styleHeader(e.addRow(["Complaint category", "Mentions", "% of negative reviews"]));
        ev.top_complaints.forEach((c) => e.addRow([c.label, c.count, `${c.share_pct}%`]));
        e.addRow([]);
      }

      if (ev.top_themes.length > 0) {
        styleHeader(e.addRow(["Theme", "Mentions", "% of reviews", "% negative"]));
        ev.top_themes.forEach((t) => e.addRow([t.label, t.count, `${t.share_pct}%`, `${t.negative_pct}%`]));
        e.addRow([]);
      }

      if (ev.verbatims.length > 0) {
        styleHeader(e.addRow(["Label", "Channel", "Rating", "Sentiment", "Verbatim"]));
        e.getColumn(5).width = 90;
        ev.verbatims.forEach((v) => {
          const row = e.addRow([v.label, v.platform, v.rating ?? "—", v.sentiment ?? "—", v.text]);
          row.getCell(5).alignment = { wrapText: true, vertical: "top" };
          row.height = 44;
        });
      }
    }

    /* ---- Sheet 3: Strengths & recommendations ---- */
    const a = wb.addWorksheet("Strengths & Actions", { properties: { defaultColWidth: 20 } });
    a.getColumn(1).width = 12;
    a.getColumn(2).width = 100;
    a.getColumn(3).width = 34;
    a.getColumn(4).width = 12;
    const aHead = a.addRow(["Type", "Item", "Addresses / evidence", "Mentions"]);
    styleHeader(aHead);
    report.top_strengths.forEach((sItem) => {
      const row = a.addRow([
        "Strength",
        sItem.text,
        sItem.related_label ?? "",
        sItem.mention_count ?? "",
      ]);
      row.getCell(2).alignment = { wrapText: true, vertical: "top" };
      row.height = 30;
    });
    report.recommendations.forEach((rItem, i) => {
      const row = a.addRow([
        `Action ${i + 1}`,
        rItem.text,
        rItem.addresses ?? "",
        rItem.mention_count ?? "",
      ]);
      row.getCell(2).alignment = { wrapText: true, vertical: "top" };
      row.height = 38;
    });
    a.views = [{ state: "frozen", ySplit: 1 }];

    /* ---- Sheet 4: Channel breakdown ---- */
    const c = wb.addWorksheet("Channels", { properties: { defaultColWidth: 20 } });
    const cHead = c.addRow(["Channel", "Summary", "Key stats", "Strengths", "Friction points"]);
    styleHeader(cHead);
    c.getColumn(1).width = 20;
    c.getColumn(2).width = 62;
    c.getColumn(3).width = 40;
    c.getColumn(4).width = 40;
    c.getColumn(5).width = 40;
    report.channel_breakdown.forEach((sec) => {
      const row = c.addRow([
        sec.channel,
        sec.summary,
        (sec.key_stats || []).join("\n"),
        (sec.strengths || []).join("\n"),
        (sec.friction_points || []).join("\n"),
      ]);
      row.height = 76;
      row.getCell(1).font = { bold: true };
      row.getCell(1).alignment = { vertical: "top" };
      for (let i = 2; i <= 5; i++) row.getCell(i).alignment = { wrapText: true, vertical: "top" };
    });
    c.views = [{ state: "frozen", ySplit: 1 }];
  }

  // Raw review log for all platforms
  const ws = wb.addWorksheet("All Feedback", {
    properties: { defaultColWidth: 20 },
  });

  // Header row (with Platform column)
  const headerRow = ws.addRow([
    "Platform",
    "Review Content", 
    "Date", 
    "Stars / Rating", 
    "Sentiment", 
    "Themes", 
    "Complaint Category"
  ]);
  headerRow.height = 28;
  headerRow.eachCell((cell) => {
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: EY_CHARCOAL } };
    cell.font = { color: { argb: "FFFFFFFF" }, bold: true, size: 11 };
    cell.alignment = { vertical: "middle", horizontal: "center" };
    cell.border = {
      bottom: { style: "medium", color: { argb: EY_GOLD } },
    };
  });

  // Column widths
  ws.getColumn(1).width = 18;  // Platform
  ws.getColumn(2).width = 70;  // Review Content
  ws.getColumn(3).width = 22;  // Date
  ws.getColumn(4).width = 15;  // Stars
  ws.getColumn(5).width = 15;  // Sentiment
  ws.getColumn(6).width = 25;  // Themes
  ws.getColumn(7).width = 25;  // Complaint Category

  // Data rows
  for (const platform of data.platforms) {
    const reviewsList = platform.reviews || [];
    for (const r of reviewsList) {
      const ratingText = r.rating != null ? `${r.rating} / 5` : "—";
      const sentimentText = r.classification?.sentiment ?? "—";
      const themesText = r.classification?.themes?.join(", ") ?? "—";
      const complaintText = r.classification?.complaint_category ?? "—";

      const row = ws.addRow([
        platform.platform,
        r.text,
        formatExcelDate(r.date),
        ratingText,
        sentimentText,
        themesText,
        complaintText,
      ]);
      row.height = 52;
      row.getCell(1).alignment = { vertical: "middle", horizontal: "center" };
      row.getCell(2).alignment = { wrapText: true, vertical: "top", horizontal: "left" };
      row.getCell(3).alignment = { vertical: "middle", horizontal: "center" };
      row.getCell(4).alignment = { vertical: "middle", horizontal: "center" };
      row.getCell(5).alignment = { vertical: "middle", horizontal: "center" };
      row.getCell(6).alignment = { wrapText: true, vertical: "middle", horizontal: "left" };
      row.getCell(7).alignment = { wrapText: true, vertical: "middle", horizontal: "left" };
    }
  }

  // Freeze header
  ws.views = [{ state: "frozen", ySplit: 1 }];

  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${data.brand_name.replace(/\s+/g, "_")}_social_cx_report_${new Date().toISOString().slice(0, 10)}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
