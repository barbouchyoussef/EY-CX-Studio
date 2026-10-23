"""The project-level interview report: the model writes prose, Python counts.

Every figure on this page is derived from the interview and assessment records, so a KPI here
cannot be wrong unless those records are. These tests hold that line, and hold the two decisions
that were made against real project data:

  * assessments are deduplicated, because several interviews in a project are usually generated
    from the SAME Orion assessment;
  * there is no "roles covered" tile, because an interview saved before the profile was returned
    on read could be relabelled "CEO" by its own autosave, so the label is not a safe thing to
    count. See test_interview_guide_parsing for the round trip that no longer loses it.
"""

from __future__ import annotations

import pytest

from app.services.assessment import interview_project_report as pr


def interview(**kw) -> dict:
    base = {
        "id": 11, "company_name": "Acme", "profile": "CEO", "language": "en",
        "assessment_id": 84, "answers": [{"section": "manage", "question": "Q?", "answer": "A."}],
        "answered": 1, "total": 1, "insights_markdown": "briefing", "cx_findings": [],
        "updated_at": None,
    }
    base.update(kw)
    return base


def finding(**kw) -> dict:
    base = {"type": "gap", "title": "A title", "description": "A description.",
            "severity": "high", "dimension": "Customer Service", "evidence": "e"}
    base.update(kw)
    return base


def assessment(aid: int = 84, scores: list | None = None) -> dict:
    return {
        "id": aid,
        "conversation": [{"question": "How do leaders reinforce it?", "answer": "Informally."}],
        "scores": scores if scores is not None else [
            {"axis": "Manage", "capability": "Ownership and governance", "level": 2,
             "level_label": "Emerging", "justification": "A central owner is named."},
        ],
    }


PART = {
    "headline": "Ownership exists on paper only.",
    "cx_culture": {"verdict": "Nobody owns it once it crosses a team.",
                   "evidence": ["“Ownership evaporates.” — CEO"]},
    "themes": [{"theme": "No cross-team accountability", "detail": "It stops at the boundary.",
                "heard_from": "CEO (interview 11)", "quote": "It sits."}],
    "contradictions": [{"between": "The CEO vs the self-assessment",
                        "claimed": "Level 2, a central owner is identified.",
                        "heard": "Ownership evaporates across teams.",
                        "so_what": "Governance has no teeth."}],
    "recommendations": [{"action": "Put CX on director scorecards.", "why": "Nothing measures it.",
                         "source": "CEO (interview 11)"}],
}


# ------------------------------------------------------------------ counts


def test_every_kpi_is_a_count_of_something_real():
    interviews = [interview(answered=21, total=21, cx_findings=[finding(severity="critical")]),
                  interview(id=13, answered=6, total=21, cx_findings=[finding(severity="low")])]
    overview = pr.build_overview(PART, interviews, [assessment()], "Acme")
    kpis = {k["label"]: k["value"] for k in overview["kpis"]}

    assert kpis["Interviews"] == 2
    assert kpis["Questions answered"] == "27 of 42"
    assert kpis["Issues raised"] == 2
    assert kpis["High or critical"] == 1        # the low one is not severe
    assert kpis["Self-assessments"] == 1
    assert kpis["Contradictions"] == 1


def test_partial_coverage_is_flagged_rather_than_reported_as_complete():
    """An interview where 6 of 21 questions came back is weaker evidence, and must look it."""
    full = pr.build_overview(PART, [interview(answered=21, total=21)], [], "Acme")
    partial = pr.build_overview(PART, [interview(answered=6, total=21)], [], "Acme")

    tone = {k["label"]: k["tone"] for k in full["kpis"]}["Questions answered"]
    assert tone == "good"
    assert {k["label"]: k["tone"] for k in partial["kpis"]}["Questions answered"] == "warn"


def test_no_contradictions_reads_as_good_rather_than_alarming():
    overview = pr.build_overview({**PART, "contradictions": []}, [interview()], [], "Acme")
    assert {k["label"]: k for k in overview["kpis"]}["Contradictions"]["tone"] == "good"


def test_there_is_no_roles_covered_tile():
    """A guide saved before the profile was returned on read could be relabelled "CEO" by its own
    autosave, so a count of distinct roles can state a number the prose beside it contradicts. It
    was removed rather than left to mislead; the coverage table names the roles instead."""
    overview = pr.build_overview(PART, [interview(), interview(id=13)], [], "Acme")
    assert "Roles covered" not in {k["label"] for k in overview["kpis"]}


# ------------------------------------------------------------------ the records


def test_issues_come_worst_first_and_carry_the_interview_they_came_from():
    interviews = [
        interview(id=11, cx_findings=[finding(title="low one", severity="low")]),
        interview(id=13, cx_findings=[finding(title="critical one", severity="critical"),
                                      finding(title="high one", severity="high")]),
    ]
    issues = pr.build_overview(PART, interviews, [], "Acme")["issues"]

    assert [i["title"] for i in issues] == ["critical one", "high one", "low one"]
    assert issues[0]["interview_id"] == 13


def test_an_issue_with_no_severity_sorts_last_rather_than_first():
    interviews = [interview(cx_findings=[finding(title="unrated", severity=None),
                                         finding(title="low", severity="low")])]
    issues = pr.build_overview(PART, interviews, [], "Acme")["issues"]
    assert [i["title"] for i in issues] == ["low", "unrated"]


def test_a_finding_with_no_title_is_dropped_rather_than_rendered_blank():
    interviews = [interview(cx_findings=[finding(title="  "), finding(title="Real"), "not a dict"])]
    assert [i["title"] for i in pr.build_overview(PART, interviews, [], "A")["issues"]] == ["Real"]


def test_coverage_has_one_row_per_interview_identified_by_number():
    """Two interviews of one client usually carry the same stated role, so the number is what
    tells the rows apart."""
    interviews = [interview(id=11, answered=21, total=21),
                  interview(id=13, answered=6, total=21)]
    coverage = pr.build_overview(PART, interviews, [], "Acme")["coverage"]

    assert [c["interview_id"] for c in coverage] == [11, 13]
    assert [c["answered"] for c in coverage] == [21, 6]


# ------------------------------------------------------------------ maturity


def test_the_lowest_level_wins_when_two_assessments_scored_one_capability():
    """Taking the best of two would flatter the client, and this table exists to be argued with."""
    a1 = assessment(84, [{"axis": "Manage", "capability": "CX culture", "level": 3,
                          "level_label": "Defined", "justification": "x"}])
    a2 = assessment(90, [{"axis": "Manage", "capability": "CX culture", "level": 1,
                          "level_label": "Ad hoc", "justification": "y"}])
    maturity = pr._maturity([a1, a2])

    assert len(maturity) == 1
    assert maturity[0]["level"] == 1
    assert maturity[0]["sources"] == 2


def test_an_unscored_capability_does_not_overwrite_a_scored_one():
    a1 = assessment(84, [{"axis": "Manage", "capability": "CX culture", "level": 2,
                          "level_label": "Emerging", "justification": "x"}])
    a2 = assessment(90, [{"axis": "Manage", "capability": "CX culture", "level": None,
                          "level_label": None, "justification": "y"}])
    assert pr._maturity([a1, a2])[0]["level"] == 2


# ------------------------------------------------------------------ the model's half


def test_the_model_supplies_only_prose():
    overview = pr.build_overview(PART, [interview()], [assessment()], "Acme")
    assert overview["headline"] == "Ownership exists on paper only."
    assert overview["cx_culture"]["verdict"].startswith("Nobody owns it")
    assert len(overview["themes"]) == 1
    assert len(overview["contradictions"]) == 1


@pytest.mark.parametrize("bad", [{}, None, {"themes": "not a list"},
                                 {"cx_culture": "not a dict"}, {"contradictions": [None, 1]}])
def test_a_malformed_part_degrades_instead_of_raising(bad):
    """A report showing coverage and the issues is worth having even when the prose half failed."""
    overview = pr.build_overview(bad, [interview(cx_findings=[finding()])], [assessment()], "Acme")

    assert overview["headline"] == ""
    assert overview["themes"] == []
    assert overview["contradictions"] == []
    assert overview["cx_culture"] == {"verdict": "", "evidence": []}
    # the computed half is untouched by whatever the model did
    assert overview["issues"] and overview["kpis"] and overview["maturity"]


# ------------------------------------------------------------------ markdown


def test_the_markdown_carries_every_section():
    overview = pr.build_overview(PART, [interview(cx_findings=[finding()])],
                                 [assessment()], "Acme")
    md = pr.render_markdown(overview)

    assert md.startswith("# Acme")
    for heading in ("## How customer experience actually works here",
                    "## What came up across the interviews",
                    "## Where the accounts disagree", "## Issues raised",
                    "## What the client scored themselves", "## Who was interviewed",
                    "## What to do next"):
        assert heading in md, heading


def test_a_pipe_in_the_text_cannot_break_a_table():
    part = {**PART, "contradictions": [{"between": "a | b", "claimed": "c | d",
                                        "heard": "e", "so_what": "f"}]}
    md = pr.render_markdown(pr.build_overview(part, [interview()], [], "T"))
    row = [line for line in md.splitlines() if "a / b" in line]
    assert row and row[0].count("|") == 5      # 4 columns, not split by the text


def test_the_markdown_stays_within_the_grammar_the_renderer_and_pdf_share():
    """MarkdownRenderer and pdf-export.ts parse this grammar separately; anything beyond headings,
    bullets, pipe tables and bold prints as literal characters in the PDF."""
    md = pr.render_markdown(pr.build_overview(PART, [interview(cx_findings=[finding()])],
                                              [assessment()], "T"))
    for banned in ("```", "---\n", "***", "> ", "<div"):
        assert banned not in md, banned


def test_a_zero_renders_as_zero_and_not_as_an_empty_cell():
    md = pr.render_markdown(pr.build_overview(PART, [interview(cx_findings=[])], [], "T"))
    assert "| 0 |" in md


# ------------------------------------------------------------------ refusals


@pytest.mark.anyio
async def test_a_project_with_no_interviews_refuses_rather_than_reporting_on_nothing():
    with pytest.raises(ValueError, match="no interviews"):
        await pr.generate("Acme", [], [])


@pytest.mark.anyio
async def test_interviews_with_no_recorded_answers_refuse():
    """A guide is a list of questions until someone records answers. Reporting on the questions
    would produce a confident write-up of a conversation that never happened."""
    with pytest.raises(ValueError, match="answers"):
        await pr.generate("Acme", [interview(answered=0, total=21, answers=[])], [])


@pytest.mark.anyio
async def test_a_model_failure_still_produces_the_computed_half():
    async def failing_llm(_system: str, _user: str) -> str:
        return "Error: every provider failed"

    overview, md = await pr.generate(
        "Acme", [interview(cx_findings=[finding()])], [assessment()], llm_fn=failing_llm)

    assert overview["headline"] == ""
    assert overview["issues"] and overview["maturity"]
    assert "## Issues raised" in md


@pytest.mark.anyio
async def test_prose_that_is_not_json_degrades_to_the_computed_half():
    async def chatty_llm(_system: str, _user: str) -> str:
        return "Sure! Here is the report you asked for, in prose."

    overview, _md = await pr.generate(
        "Acme", [interview(cx_findings=[finding()])], [], llm_fn=chatty_llm)
    assert overview["headline"] == ""
    assert overview["issues"]


# ------------------------------------------------------------------ the prompt


@pytest.mark.anyio
async def test_the_prompt_carries_the_answers_the_levels_and_the_interview_numbers():
    """Everything the report is asked to reason about has to actually reach the model."""
    seen: dict[str, str] = {}

    async def capturing_llm(system: str, user: str) -> str:
        seen["system"], seen["user"] = system, user
        return "{}"

    await pr.generate(
        "Acme",
        [interview(id=11, answers=[{"section": "manage", "question": "Who owns it?",
                                    "answer": "Nobody, once it crosses a team."}])],
        [assessment()],
        llm_fn=capturing_llm,
    )

    assert "Who owns it?" in seen["user"]
    assert "Nobody, once it crosses a team." in seen["user"]
    assert "INTERVIEW #11" in seen["user"]
    assert "Ownership and governance: Level 2" in seen["user"]
    assert "How do leaders reinforce it?" in seen["user"]   # the Orion conversation itself


@pytest.mark.anyio
async def test_a_long_interview_is_truncated_without_dropping_a_later_one():
    """Cutting off the end of the combined transcript would drop the last interview entirely and
    the model would never know it existed."""
    long_answers = [{"section": "manage", "question": "Q", "answer": "x" * 40_000}
                    for _ in range(4)]
    seen: dict[str, str] = {}

    async def capturing_llm(_system: str, user: str) -> str:
        seen["user"] = user
        return "{}"

    await pr.generate(
        "Acme",
        [interview(id=11, answers=long_answers), interview(id=13, answers=long_answers)],
        [],
        llm_fn=capturing_llm,
    )

    assert "INTERVIEW #11" in seen["user"]
    assert "INTERVIEW #13" in seen["user"]
    assert "truncated" in seen["user"]


# ------------------------------------------------------------------ the route layer

from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes.projects import _report_sources  # noqa: E402
from app.main import app  # noqa: E402


def test_the_stored_report_goes_stale_when_another_interview_is_attached():
    before = _report_sources([interview(id=11)], [assessment()])
    after = _report_sources([interview(id=11), interview(id=13)], [assessment()])
    assert before != after


def test_the_stored_report_goes_stale_when_more_answers_are_recorded():
    """The id list alone would not notice. Recording answers to an interview already in the report
    changes what the report should say, which is the common case: a consultant generates early,
    then finishes the interview."""
    before = _report_sources([interview(id=11, answered=6, total=21)], [])
    after = _report_sources([interview(id=11, answered=21, total=21)], [])
    assert before != after


def test_an_unchanged_project_is_not_stale():
    same = [interview(id=11, answered=21, total=21)]
    assert _report_sources(same, [assessment()]) == _report_sources(same, [assessment()])


def test_the_same_assessment_behind_two_interviews_is_counted_once():
    """Interviews in a project are usually generated from ONE Orion assessment. Counting it twice
    would inflate the tile and feed the model the same conversation over again."""
    sources = _report_sources([interview(id=11), interview(id=13)], [assessment(84)])
    assert sources["assessment_ids"] == [84]


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_the_interview_report_refuses_an_unauthenticated_request(method):
    with TestClient(app) as client:
        response = client.request(method, "/api/v1/projects/1/interview-report")
    assert response.status_code == 401, (
        f"{method} answered {response.status_code} without credentials"
    )
