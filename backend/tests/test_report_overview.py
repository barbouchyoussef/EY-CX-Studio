"""The desk-research overview: the model writes prose, Python counts.

Every figure on the overview is derived from `cx_findings` rather than repeated by a model, so a
KPI here cannot be wrong unless the findings themselves are.

Grouped by the CX capability framework, which is what `cx_findings` carries. The issue log's
Excel export classifies by strategic dimension instead and generates its own issues from the
deep-dives, so the two will not line up -- see the note in report_overview.py.

`render_markdown` is covered too, because `report_markdown` still feeds three things that must
keep working: the session chatbot's retrieval index, the PDF export, and the legacy issue-log
path that splits an old report on its Part 2 heading.
"""

from __future__ import annotations

import pytest

from app.services.desk_research import report_overview as ro


def finding(**kw) -> dict:
    base = {
        "axis": "Analyze", "capability": "Feedback collection", "type": "gap",
        "severity": "medium", "title": "A title", "description": "A description.",
        "evidence": "some evidence", "source_document": "Doc A",
    }
    base.update(kw)
    return base


PART1 = {
    "headline": "Billing complaints rose 34%.",
    "period": "2023 to 2025",
    "takeaways": [{"point": "Billing drives 34% of contacts.", "source": "Review, p. 4"},
                  {"point": "Resolution fell to 61%.", "source": "NPS deck"}],
    "documents": [{"name": "Review", "what_it_is": "Annual report",
                   "period": "2024", "key_point": "2.64M queries"}],
    "connections": ["The two decks disagree on volume: 2.64M vs 2.4M."],
    "recommendations": [{"action": "Rebuild the scoring sheet.", "why": "Weights total 50.",
                         "capability": "Measurement and continuous improvement"}],
}


# ------------------------------------------------------------------ counts


def test_every_kpi_is_a_count_of_something_real():
    findings = [finding(severity="critical"), finding(type="strength", severity=None),
                finding(axis="Improve", severity="low")]
    kpis = {k["label"]: k["value"] for k in ro.build_overview(PART1, findings, 4)["kpis"]}

    assert kpis["Documents analysed"] == 4
    assert kpis["CX findings"] == 3
    assert kpis["Problems identified"] == 2      # the strength is not a problem
    assert kpis["High or critical"] == 1
    assert kpis["Axes covered"] == "2 of 3"


def test_a_clean_set_reads_as_good_rather_than_alarming():
    kpis = {k["label"]: k for k in ro.build_overview(PART1, [finding(type="strength")], 1)["kpis"]}
    assert kpis["Problems identified"]["tone"] == "good"
    assert kpis["High or critical"]["tone"] == "good"


def test_problems_come_worst_first():
    findings = [finding(title="low one", severity="low"),
                finding(title="critical one", severity="critical"),
                finding(title="high one", severity="high")]
    problems = ro.build_overview(PART1, findings, 1)["problems"]
    assert [p["title"] for p in problems] == ["critical one", "high one", "low one"]


def test_a_finding_with_no_severity_sorts_last_rather_than_first():
    findings = [finding(title="unrated", severity=None), finding(title="low", severity="low")]
    assert [p["title"] for p in ro.build_overview(PART1, findings, 1)["problems"]] == ["low", "unrated"]


def test_each_finding_type_lands_in_its_own_section():
    """An opportunity is not a strength.

    Grouping them put "Low digital sales channel utilization" under a heading reading "What is
    working" -- the opposite of what the finding said. Three types, three sections.
    """
    findings = [finding(type="strength", title="works"), finding(type="opportunity", title="could"),
                finding(type="friction", title="broken"), finding(type="gap", title="missing")]
    overview = ro.build_overview(PART1, findings, 1)

    assert [s["title"] for s in overview["strengths"]] == ["works"]
    assert [o["title"] for o in overview["opportunities"]] == ["could"]
    assert {p["title"] for p in overview["problems"]} == {"broken", "missing"}


def test_an_opportunity_is_not_counted_as_a_problem():
    """It is neither wrong nor working, so it must not move the problem KPIs either way."""
    kpis = {k["label"]: k["value"]
            for k in ro.build_overview(PART1, [finding(type="opportunity")], 1)["kpis"]}
    assert kpis["Problems identified"] == 0
    assert kpis["CX findings"] == 1


def test_opportunities_render_under_their_own_heading():
    md = ro.render_markdown(
        ro.build_overview(PART1, [finding(type="opportunity", title="Worth doing")], 1), "T")
    assert "## Opportunities" in md
    assert "## What is working" not in md
    assert "Worth doing" in md


def test_an_axis_with_nothing_against_it_is_kept_and_shown_as_zero():
    """A document set silent on how the client acts on pain points is itself worth seeing.
    Dropping the empty row would hide it."""
    coverage = {c["axis"]: c for c in ro.build_overview(PART1, [finding(axis="Analyze")], 1)["coverage"]}

    assert set(coverage) == {"Manage", "Analyze", "Improve"}
    assert coverage["Manage"]["findings"] == 0
    assert coverage["Analyze"]["findings"] == 1


# ------------------------------------------------------------------ the model's half


def test_the_model_supplies_only_prose():
    overview = ro.build_overview(PART1, [finding()], 1)
    assert overview["headline"] == "Billing complaints rose 34%."
    points = [t["point"] for t in overview["takeaways"]]
    assert points == ["Billing drives 34% of contacts.", "Resolution fell to 61%."]
    assert overview["takeaways"][0]["source"] == "Review, p. 4"
    assert overview["recommendations"] == PART1["recommendations"]


@pytest.mark.parametrize("bad", [{}, {"takeaways": "not a list"}, {"documents": [None, "x"]}, None])
def test_a_malformed_or_missing_part1_degrades_instead_of_raising(bad):
    """A report with no recommendations is worth showing; a 500 because one key was absent is not."""
    overview = ro.build_overview(bad, [finding()], 1)
    assert overview["headline"] == ""
    assert overview["takeaways"] == []
    assert overview["documents"] == []
    # the computed half is unaffected by whatever the model did
    assert overview["problems"] and overview["kpis"]


# ------------------------------------------------------------------ markdown


def test_the_markdown_carries_every_section():
    md = ro.render_markdown(ro.build_overview(PART1, [finding(severity="critical")], 2), "Client X")

    assert md.startswith("# Client X")
    for heading in ("## What this set shows", "## What each document contains",
                    "## How they connect", "## Problems found",
                    "## Coverage across the CX framework", "## What to do next"):
        assert heading in md, heading


def test_a_zero_renders_as_zero_and_not_as_an_empty_cell():
    """`value or ""` blanks a zero, and a zero is the most interesting number in that table."""
    md = ro.render_markdown(ro.build_overview(PART1, [finding(axis="Analyze")], 1), "T")
    assert "| Manage | 0 | 0 |" in md


def test_a_pipe_in_the_text_cannot_break_a_table():
    md = ro.render_markdown(
        ro.build_overview(PART1, [finding(title="a | b", source_document="x | y")], 1), "T")
    problems = [l for l in md.splitlines() if "a / b" in l]
    assert problems and problems[0].count("|") == 5   # 4 columns, not split by the text


def test_the_markdown_stays_within_the_grammar_the_renderer_and_pdf_share():
    """MarkdownRenderer and pdf-export.ts parse this grammar separately. Anything beyond headings,
    bullets, pipe tables and bold prints as literal characters in the PDF."""
    md = ro.render_markdown(ro.build_overview(PART1, [finding()], 1), "T")
    for banned in ("```", "---\n", "***", "> ", "<div"):
        assert banned not in md, banned


def test_an_empty_run_still_produces_a_titled_document():
    md = ro.render_markdown(ro.build_overview({}, [], 0), "Empty Session")
    assert md.strip().startswith("# Empty Session")


def test_a_takeaway_that_arrives_as_a_bare_string_still_renders():
    """The prompt asks for objects so a point can name its document, but a model answering with
    plain strings should degrade to a readable report rather than a blank section."""
    overview = ro.build_overview(
        {"takeaways": ["just a sentence", {"point": "with a source", "source": "Doc A, p. 2"}]},
        [finding()], 1)
    assert [t["point"] for t in overview["takeaways"]] == ["just a sentence", "with a source"]
    assert overview["takeaways"][0]["source"] is None
    assert overview["takeaways"][1]["source"] == "Doc A, p. 2"


def test_sources_reach_the_markdown():
    part1 = dict(PART1)
    part1["recommendations"] = [{"action": "Do X.", "why": "Because Y.",
                                 "capability": "CX culture", "source": "Review, p. 2"}]
    md = ro.render_markdown(ro.build_overview(part1, [finding()], 1), "T")
    assert "*Review, p. 4*" in md
    assert "*Source: Review, p. 2*" in md
