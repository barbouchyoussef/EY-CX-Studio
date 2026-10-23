"""Write the issue log to an .xlsx workbook.

Follows the client's reference structure (Issue # / Findings / Issue investigation / Strategic
dimension / Issue Sub-Category / Inspection Point / Channel / Comment) and adds the columns their
hand-built version could not carry:

    Evidence   the verbatim source quote, so any row can be challenged and defended
    Verified   whether that quote was found in the source, checked without a model
    Reports    how many customers or sources raised it -- evidence weight
    Severity   graded against a written rubric, with the reason beside it
    Source     document analysis / interview / web scraping, from their own ReferenceLists sheet

Five sheets: Issue List, Conflicts (where two sources disagree and a consultant must decide),
Recommendations, Summary (the distribution their Pivot sheet computed by hand), and Category
Definitions so the log travels with the rubric it was classified against.
"""

from __future__ import annotations

import io
from typing import Sequence

import xlsxwriter

from app.services.issue_log import taxonomy

SOURCE_LABELS = {
    "desk_session": "Document analysis",
    "interview_guide": "Interview",
    "social_report": "Web scraping",
    "assessment": "Maturity assessment",
}

ISSUE_COLUMNS = [
    ("Issue #", "issue_no", 8),
    ("Findings", "finding", 38),
    ("Issue investigation", "investigation", 70),
    ("Strategic dimension", "strategic_dimension", 22),
    ("Issue Sub-Category", "sub_category", 20),
    ("Inspection Point", "inspection_point", 32),
    ("Page", "page", 7),
    ("Source", "_source_label", 16),
    ("Channel", "channel", 14),
    ("Reports", "reports", 9),
    ("Severity", "severity", 10),
    ("Severity reason", "severity_reason", 44),
    ("Reported by", "_corroboration", 30),
    ("Evidence", "evidence", 54),
    ("Verified", "evidence_status", 10),
    # Two review aids, both decided without a model. "Grounding" says whether the quote states a
    # fact or repeats an opinion; "Possible fragment of" names a row that evidences figures this
    # one only asserts, which is what a single finding split across two rows looks like.
    ("Grounding", "_grounding", 12),
    ("Possible fragment of", "_fragment_of", 34),
    ("Comment", "comment", 24),
]

REC_COLUMNS = [
    ("Ref", "ref", 7),
    ("Recommendation", "action", 56),
    ("Rationale", "rationale", 66),
    ("Addresses issues", "_addresses", 20),
    ("Issues", "issues_addressed", 8),
    ("Effort", "effort", 16),
    ("Impact", "impact", 10),
    ("Client", "client", 18),
]

CONFLICT_COLUMNS = [
    ("Ref", "ref", 7),
    ("Issue A", "issue_a", 9),
    ("Source A", "source_a", 30),
    ("A claims", "a_claims", 52),
    ("Issue B", "issue_b", 9),
    ("Source B", "source_b", 30),
    ("B claims", "b_claims", 52),
    ("Why it matters", "why_it_matters", 50),
]

_SEVERITY_TINT = {
    "critical": "#F8CBAD",
    "high": "#FCE4D6",
    "medium": "#FFF2CC",
    "low": "#E2EFDA",
}


def _formats(book: xlsxwriter.Workbook) -> dict:
    return {
        "title": book.add_format({"bold": True, "font_size": 14}),
        "header": book.add_format({"bold": True, "bg_color": "#2E2E38", "font_color": "white",
                                   "border": 1, "text_wrap": True, "valign": "vcenter"}),
        "cell": book.add_format({"text_wrap": True, "valign": "top", "border": 1}),
        "num": book.add_format({"valign": "top", "border": 1, "align": "center"}),
        "note": book.add_format({"italic": True, "font_color": "#666666"}),
        "pct": book.add_format({"num_format": "0%", "border": 1, "align": "center"}),
        "sev": {k: book.add_format({"text_wrap": True, "valign": "top", "border": 1,
                                    "bg_color": v, "align": "center"})
                for k, v in _SEVERITY_TINT.items()},
        "bold": book.add_format({"bold": True, "border": 1}),
    }


def _write_issues(book, fmt, issues: Sequence[dict]) -> None:
    sheet = book.add_worksheet("Issue List")
    sheet.freeze_panes(1, 0)
    for col, (title, _, width) in enumerate(ISSUE_COLUMNS):
        sheet.set_column(col, col, width)
        sheet.write(0, col, title, fmt["header"])

    for row, issue in enumerate(issues, start=1):
        prepared = dict(issue)
        prepared["_source_label"] = SOURCE_LABELS.get(str(issue.get("source_kind")), "")
        # Corroboration is the strongest thing this log can say about an issue: not one person's
        # opinion but several sources independently reporting the same gap.
        count = int(issue.get("corroboration_count") or 0)
        prepared["_corroboration"] = (f"{count} sources agree" if count > 1 else "")
        if issue.get("has_conflict"):
            others = ", ".join(str(x) for x in (issue.get("conflicts_with") or []))
            prepared["_corroboration"] = (
                f"CONFLICTS with {others}" if others else "CONFLICTS with another source")
        words = issue.get("judgement_evidence") or []
        prepared["_grounding"] = ("opinion (" + ", ".join(words[:3]) + ")") if words else "fact"
        frag = list(issue.get("fragment_of") or [])
        merged = list(issue.get("merged_from") or [])
        if merged:
            frag = [f"merged in: {m}" for m in merged] + frag
        prepared["_fragment_of"] = "; ".join(frag)
        prepared.setdefault("comment", "")
        for col, (_, key, _) in enumerate(ISSUE_COLUMNS):
            value = prepared.get(key)
            if key == "severity":
                sheet.write(row, col, value or "", fmt["sev"].get(str(value), fmt["cell"]))
            elif key == "reports":
                sheet.write_number(row, col, int(value or 1), fmt["num"])
            else:
                sheet.write(row, col, "" if value is None else str(value), fmt["cell"])

    if issues:
        sheet.autofilter(0, 0, len(issues), len(ISSUE_COLUMNS) - 1)


def _write_recommendations(book, fmt, recs: Sequence[dict]) -> None:
    sheet = book.add_worksheet("Recommendations")
    sheet.freeze_panes(1, 0)
    for col, (title, _, width) in enumerate(REC_COLUMNS):
        sheet.set_column(col, col, width)
        sheet.write(0, col, title, fmt["header"])

    for row, rec in enumerate(recs, start=1):
        prepared = dict(rec)
        prepared["_addresses"] = ", ".join(rec.get("addresses") or [])
        for col, (_, key, _) in enumerate(REC_COLUMNS):
            value = prepared.get(key)
            if key == "issues_addressed":
                sheet.write_number(row, col, int(value or 0), fmt["num"])
            else:
                sheet.write(row, col, "" if value is None else str(value), fmt["cell"])

    if recs:
        sheet.autofilter(0, 0, len(recs), len(REC_COLUMNS) - 1)


def _write_conflicts(book, fmt, conflicts) -> None:
    """Where two sources make claims that cannot both be true.

    Deliberately its own sheet rather than a note on a row: this is a reviewer's to-do list, and
    publishing an issue log that contradicts itself is the failure a client notices first.
    """
    sheet = book.add_worksheet("Conflicts")
    sheet.freeze_panes(1, 0)
    for col, (title, _, width) in enumerate(CONFLICT_COLUMNS):
        sheet.set_column(col, col, width)
        sheet.write(0, col, title, fmt["header"])

    if not conflicts:
        sheet.write(1, 0, "No conflicting claims were found between sources.", fmt["note"])
        return

    for row, conflict in enumerate(conflicts, start=1):
        for col, (_, key, _) in enumerate(CONFLICT_COLUMNS):
            value = conflict.get(key)
            sheet.write(row, col, "" if value is None else str(value), fmt["cell"])
    sheet.autofilter(0, 0, len(conflicts), len(CONFLICT_COLUMNS) - 1)


def _write_summary(book, fmt, issues: Sequence[dict], run: dict | None) -> None:
    """The distribution the reference computed by hand as a pivot, plus run quality figures.

    Two denominators, as in theirs: a dimension's share of all issues, and a sub-category's share
    of ITS OWN dimension.
    """
    sheet = book.add_worksheet("Summary")
    sheet.set_column(0, 0, 34)
    sheet.set_column(1, 4, 14)
    total = len(issues) or 1

    sheet.write(0, 0, "Issue distribution", fmt["title"])
    row = 2
    for header, col in (("Dimension / sub-category", 0), ("Issues", 1),
                        ("Share of all", 2), ("Share of dimension", 3)):
        sheet.write(row, col, header, fmt["header"])
    row += 1

    by_dimension: dict[str, list[dict]] = {}
    for issue in issues:
        by_dimension.setdefault(str(issue.get("strategic_dimension")), []).append(issue)

    for dimension in taxonomy.DIMENSIONS:
        rows = by_dimension.get(dimension, [])
        if not rows:
            continue
        sheet.write(row, 0, dimension, fmt["bold"])
        sheet.write_number(row, 1, len(rows), fmt["num"])
        sheet.write_number(row, 2, len(rows) / total, fmt["pct"])
        sheet.write(row, 3, "", fmt["cell"])
        row += 1
        counts: dict[str, int] = {}
        for issue in rows:
            counts[str(issue.get("sub_category") or "(unclassified)")] = \
                counts.get(str(issue.get("sub_category") or "(unclassified)"), 0) + 1
        for sub, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            sheet.write(row, 0, f"    {sub}", fmt["cell"])
            sheet.write_number(row, 1, n, fmt["num"])
            sheet.write_number(row, 2, n / total, fmt["pct"])
            sheet.write_number(row, 3, n / len(rows), fmt["pct"])
            row += 1

    sheet.write(row, 0, "Total", fmt["bold"])
    sheet.write_number(row, 1, len(issues), fmt["num"])
    row += 2

    severities = {s: sum(1 for i in issues if i.get("severity") == s)
                  for s in ("critical", "high", "medium", "low")}
    sheet.write(row, 0, "By severity", fmt["title"]); row += 1
    for name, count in severities.items():
        sheet.write(row, 0, name.title(), fmt["cell"])
        sheet.write_number(row, 1, count, fmt["num"])
        sheet.write_number(row, 2, count / total, fmt["pct"])
        row += 1
    row += 1

    sheet.write(row, 0, "Evidence quality", fmt["title"]); row += 1
    verified = sum(1 for i in issues if i.get("evidence_status") in ("exact", "partial"))
    reports = sum(int(i.get("reports") or 1) for i in issues)
    corroborated = sum(1 for i in issues if int(i.get("corroboration_count") or 0) > 1)
    conflicted = sum(1 for i in issues if i.get("has_conflict"))
    facts = [("Issues", len(issues)),
             ("Quotes verified against the source", verified),
             ("Customer/source reports behind them", reports),
             ("Issues corroborated by 2+ sources", corroborated),
             ("Issues flagged as conflicting", conflicted)]
    if run:
        facts += [("Source chunks analysed", run.get("calls", 0)),
                  ("Rows dropped off-taxonomy", run.get("dropped_off_taxonomy", 0)),
                  ("Rows citing an unsourced figure", run.get("fabricated_numbers", 0))]
    for name, value in facts:
        sheet.write(row, 0, name, fmt["cell"])
        sheet.write_number(row, 1, value, fmt["num"])
        row += 1

    if run and run.get("warnings"):
        row += 1
        sheet.write(row, 0, "Warnings from this run", fmt["title"]); row += 1
        for warning in run["warnings"][:12]:
            sheet.write(row, 0, str(warning), fmt["note"]); row += 1


def _write_definitions(book, fmt) -> None:
    sheet = book.add_worksheet("Category Definitions")
    sheet.set_column(0, 0, 34)
    sheet.set_column(1, 1, 96)
    sheet.write(0, 0, "Main category", fmt["header"])
    sheet.write(0, 1, "Definition", fmt["header"])
    row = 1
    for dimension, subs in taxonomy.TAXONOMY.items():
        sheet.write(row, 0, dimension, fmt["bold"])
        sheet.write(row, 1, taxonomy.DIMENSION_DEFS.get(dimension, ""), fmt["cell"])
        row += 1
        for sub in subs:
            sheet.write(row, 0, f"    {sub}", fmt["cell"])
            sheet.write(row, 1, taxonomy.SUB_CATEGORY_DEFS.get(sub, ""), fmt["cell"])
            row += 1


def build_workbook(issues: Sequence[dict], recommendations: Sequence[dict] = (),
                   run: dict | None = None, title: str = "Issue Log",
                   conflicts: Sequence[dict] = ()) -> bytes:
    """Render the workbook and return the bytes, ready to stream or store."""
    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {"in_memory": True, "constant_memory": False})
    book.set_properties({"title": title, "comments": "Generated by CX Studio"})
    fmt = _formats(book)

    _write_issues(book, fmt, issues)
    _write_conflicts(book, fmt, conflicts)
    _write_recommendations(book, fmt, recommendations)
    _write_summary(book, fmt, issues, run)
    _write_definitions(book, fmt)

    book.close()
    return buffer.getvalue()
