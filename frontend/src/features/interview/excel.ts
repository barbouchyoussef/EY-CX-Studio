/**
 * The interview guide as a branded Excel workbook.
 *
 * Two sheets: the questions themselves, and a summary carrying the assessment's executive summary
 * and the gaps the interview is meant to close. Consultants send this file to clients and edit it
 * in front of them, which is why so much of this is formatting -- the output is a deliverable, not
 * a data dump.
 *
 * Lifted out of the hub unchanged. It is a pure function of a guide: no React,
 * no state, no network. Every colour and column width below is carried over exactly, so the file
 * consultants receive is byte-for-byte what it was.
 */

import ExcelJS from "exceljs";

import type { InterviewGuide, InterviewGuideQuestionItem } from "./guide";
import { interviewLabels } from "./copy";

export type InterviewGuideExcelOptions = {
  /** Drives every label in the workbook. The guide's own language decides this. */
  isFrench: boolean;
  /** The interviewee's role, shown in the subtitle. Held by the hub, not stored on the guide. */
  profile: string;
};

/**
 * Build the workbook for a guide and hand it to the browser as a download.
 *
 * Throws if ExcelJS cannot produce the file; the caller decides what to show the consultant.
 */
export async function exportInterviewGuideToExcel(
  guide: InterviewGuide,
  { isFrench, profile }: InterviewGuideExcelOptions,
): Promise<void> {
  const labels = interviewLabels(isFrench);
      const wb = new ExcelJS.Workbook();
      wb.creator = "EY CX Chat";
      wb.created = new Date();

      // ────────────────────────────────────────────────────────
      // SHEET 1: INTERVIEW GUIDE
      // ────────────────────────────────────────────────────────
      const ws = wb.addWorksheet(labels.guideHeading, {
        views: [{ showGridLines: true }]
      });

      // Title & Subtitle block
      ws.addRow([]); // Row 1: Spacer
      
      const titleRow = ws.addRow(["", "EY | CUSTOMER EXPERIENCE MATURITY ASSESSMENT"]);
      titleRow.height = 30;
      titleRow.getCell(2).font = { name: "Arial", size: 14, bold: true, color: { argb: "1F2937" } };
      
      const subtitleRow = ws.addRow(["", `Company: ${guide.company_name}   |   Language: ${guide.language.toUpperCase()}   |   Profile: ${profile}`]);
      subtitleRow.height = 20;
      subtitleRow.getCell(2).font = { name: "Arial", size: 9.5, italic: true, color: { argb: "4B5563" } };
      
      ws.addRow([]); // Row 4: Spacer

      // Define columns
      const headers = isFrench
        ? ["Axe / Section", "N°", "Question", "Pourquoi cette question ?", "Relances potentielles", "Notes / Réponse du client", "Statut"]
        : ["Section / Axis", "#", "Question", "Rationale", "Potential Follow-ups", "Client Answer / Notes", "Status"];

      const headerRow = ws.addRow(headers);
      headerRow.height = 28;

      // Header styling
      headerRow.eachCell((cell) => {
        cell.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: "2E2E38" } // Dark Charcoal
        };
        cell.font = {
          name: "Arial",
          size: 10,
          bold: true,
          color: { argb: "FFFFFF" }
        };
        cell.alignment = { vertical: "middle", horizontal: "center" };
        cell.border = {
          top: { style: "thin", color: { argb: "4B5563" } },
          bottom: { style: "medium", color: { argb: "111827" } },
          left: { style: "thin", color: { argb: "4B5563" } },
          right: { style: "thin", color: { argb: "4B5563" } }
        };
      });

      const sectionDefs = [
        { 
          label: labels.sheetIntroduction, 
          key: "introduction_questions" as const,
          bgColor: "F1F5F9", // Slate-100
          textColor: "475569"
        },
        { 
          label: labels.sheetManage, 
          key: "manage_questions" as const,
          bgColor: "FEF3C7", // Amber-100
          textColor: "B45309"
        },
        { 
          label: labels.sheetAnalyze, 
          key: "analyze_questions" as const,
          bgColor: "EFF6FF", // Blue-100
          textColor: "1D4ED8"
        },
        { 
          label: labels.sheetImprove, 
          key: "improve_questions" as const,
          bgColor: "ECFDF5", // Emerald-100
          textColor: "047857"
        },
        { 
          label: labels.sheetClosure, 
          key: "closure_questions" as const,
          bgColor: "FAF5FF", // Purple-100
          textColor: "6D28D9"
        },
      ];

      // Add data rows
      sectionDefs.forEach((sec) => {
        const qs = guide[sec.key] as InterviewGuideQuestionItem[];
        qs.forEach((q, idx) => {
          const statusText = q.isAnswered 
            ? (labels.answered) 
            : (labels.toAsk);
            
          const dataRow = ws.addRow([
            sec.label,
            idx + 1,
            q.question || "",
            q.rationale || "",
            q.follow_up || "",
            q.answerNote || "",
            statusText
          ]);

          dataRow.height = 68; // Safe height with nice breathing room!

          // Row borders
          const thinBorder = { style: "thin" as const, color: { argb: "E2E8F0" } };
          
          // Style individual cells in the row
          // Column 1 (Section Label)
          const cellSec = dataRow.getCell(1);
          cellSec.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: sec.bgColor }
          };
          cellSec.font = { name: "Arial", size: 9.5, bold: true, color: { argb: sec.textColor } };
          cellSec.alignment = { vertical: "middle", horizontal: "center", wrapText: true };
          cellSec.border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

          // Column 2 (Index)
          const cellIdx = dataRow.getCell(2);
          cellIdx.font = { name: "Arial", size: 9.5, bold: true, color: { argb: "6B7280" } };
          cellIdx.alignment = { vertical: "middle", horizontal: "center" };
          cellIdx.border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

          // Columns 3, 4, 5, 6 (Texts)
          for (let col = 3; col <= 6; col++) {
            const cell = dataRow.getCell(col);
            cell.font = { 
              name: "Arial", 
              size: 9.5, 
              color: { argb: col === 6 ? "1E3A8A" : "374151" } // Highlight user notes in soft blue
            };
            cell.alignment = { vertical: "middle", horizontal: "left", wrapText: true };
            cell.border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
            
            // Give a very soft tint to the Answer column to make it stand out as writable area
            if (col === 6) {
              cell.fill = {
                type: "pattern",
                pattern: "solid",
                fgColor: { argb: "F8FAFC" } // Slate-50 tint
              };
            }
          }

          // Column 7 (Status Badge)
          const cellStatus = dataRow.getCell(7);
          cellStatus.alignment = { vertical: "middle", horizontal: "center" };
          cellStatus.border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
          if (q.isAnswered) {
            cellStatus.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "D1FAE5" } }; // Light emerald
            cellStatus.font = { name: "Arial", size: 9, bold: true, color: { argb: "065F46" } };
          } else {
            cellStatus.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FEF3C7" } }; // Light amber
            cellStatus.font = { name: "Arial", size: 9, bold: true, color: { argb: "92400E" } };
          }
        });
      });

      // Set explicit column widths
      ws.getColumn(1).width = 22; // Section
      ws.getColumn(2).width = 6;  // #
      ws.getColumn(3).width = 50; // Question
      ws.getColumn(4).width = 40; // Rationale
      ws.getColumn(5).width = 40; // Follow-up
      ws.getColumn(6).width = 50; // Notes
      ws.getColumn(7).width = 14; // Status

      // ────────────────────────────────────────────────────────
      // SHEET 2: DIAGNOSTIC SUMMARY
      // ────────────────────────────────────────────────────────
      const wsSum = wb.addWorksheet(labels.sheetSummary, {
        views: [{ showGridLines: true }]
      });

      wsSum.addRow([]); // Spacer
      
      const sumTitleRow = wsSum.addRow(["", "DIAGNOSTIC SUMMARY & MATURITY FINDINGS"]);
      sumTitleRow.height = 30;
      sumTitleRow.getCell(2).font = { name: "Arial", size: 14, bold: true, color: { argb: "1F2937" } };
      
      wsSum.addRow([]); // Spacer

      // Info rows
      const addMetaRow = (key: string, val: string) => {
        const row = wsSum.addRow(["", key, val]);
        row.height = 22;
        row.getCell(2).font = { name: "Arial", size: 10, bold: true, color: { argb: "4B5563" } };
        row.getCell(2).alignment = { vertical: "middle", horizontal: "right" };
        row.getCell(3).font = { name: "Arial", size: 10, color: { argb: "111827" } };
        row.getCell(3).alignment = { vertical: "middle", horizontal: "left" };
        
        const thinBorder = { style: "thin" as const, color: { argb: "E2E8F0" } };
        row.getCell(2).border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
        row.getCell(3).border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
        
        row.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "F9FAFB" } };
      };

      addMetaRow(labels.company, guide.company_name);
      addMetaRow(labels.sheetLanguage, guide.language.toUpperCase());
      addMetaRow(labels.profile, profile);
      
      wsSum.addRow([]); // Spacer
      wsSum.addRow([]); // Spacer

      // Executive Summary Header
      const execHeader = wsSum.addRow(["", labels.sheetExecutiveSummary]);
      execHeader.height = 24;
      execHeader.getCell(2).font = { name: "Arial", size: 11, bold: true, color: { argb: "FFFFFF" } };
      execHeader.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "2E2E38" } };
      execHeader.getCell(2).alignment = { vertical: "middle", horizontal: "left" };
      wsSum.mergeCells(`B${execHeader.number}:F${execHeader.number}`);

      // Executive Summary Content
      const execContent = wsSum.addRow(["", guide.executive_summary || ""]);
      execContent.height = 80;
      execContent.getCell(2).font = { name: "Arial", size: 10, color: { argb: "374151" } };
      execContent.getCell(2).alignment = { vertical: "top", horizontal: "left", wrapText: true };
      
      const thinBorder = { style: "thin" as const, color: { argb: "CBD5E1" } };
      // Apply border around the merged text area manually
      wsSum.mergeCells(`B${execContent.number}:F${execContent.number}`);
      execContent.getCell(2).border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
      execContent.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FAFAFA" } };

      wsSum.addRow([]); // Spacer
      wsSum.addRow([]); // Spacer

      // Gaps Header
      if (guide.unanswered_areas && guide.unanswered_areas.length > 0) {
        const gapHeader = wsSum.addRow(["", labels.sheetKeyGaps]);
        gapHeader.height = 24;
        gapHeader.getCell(2).font = { name: "Arial", size: 11, bold: true, color: { argb: "FFFFFF" } };
        gapHeader.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "92400E" } }; // Amber-800
        gapHeader.getCell(2).alignment = { vertical: "middle", horizontal: "left" };
        wsSum.mergeCells(`B${gapHeader.number}:F${gapHeader.number}`);

        guide.unanswered_areas.forEach((gap, i) => {
          const gapRow = wsSum.addRow(["", `${i + 1}.`, gap]);
          gapRow.height = 24;
          gapRow.getCell(2).font = { name: "Arial", size: 9.5, bold: true, color: { argb: "B45309" } };
          gapRow.getCell(2).alignment = { vertical: "middle", horizontal: "center" };
          gapRow.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFFBEB" } };
          
          gapRow.getCell(3).font = { name: "Arial", size: 9.5, color: { argb: "374151" } };
          gapRow.getCell(3).alignment = { vertical: "middle", horizontal: "left" };
          
          const thinBorder = { style: "thin" as const, color: { argb: "FDE68A" } };
          gapRow.getCell(2).border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
          gapRow.getCell(3).border = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
          wsSum.mergeCells(`C${gapRow.number}:F${gapRow.number}`);
        });
      }

      // Column widths for sheet 2
      wsSum.getColumn(1).width = 4;
      wsSum.getColumn(2).width = 25;
      wsSum.getColumn(3).width = 20;
      wsSum.getColumn(4).width = 20;
      wsSum.getColumn(5).width = 20;
      wsSum.getColumn(6).width = 20;

      // Write and download
      const buffer = await wb.xlsx.writeBuffer();
      const blob = new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `Interview_Guide_${guide.company_name.replace(/\s+/g, "_")}_${new Date().toISOString().slice(0, 10)}.xlsx`;
      anchor.click();
      window.URL.revokeObjectURL(url);
}
