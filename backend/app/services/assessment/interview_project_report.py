"""The project-level interview report: every interview in a project, read together.

Why this exists. `interview_insights` already cross-references ONE interview against the Orion
self-assessment it came from. That is the right unit while you are running interviews, and the
wrong unit once you have several: a project's value is in what the interviews say *collectively*,
and above all in where they disagree -- with each other, and with what the client claimed when
they scored themselves.

The split follows the rule the rest of the platform works to: **the model writes prose, Python
computes figures.**

    the model supplies   -- the headline, the read on CX culture, the themes running across the
                            interviews, the contradictions, and what to do next;
    Python supplies      -- every count, the coverage table, the maturity picture from the Orion
                            scores, and the rolled-up findings, all read from the database.

So a number on this page cannot be wrong unless the underlying records are.

WHICH TAXONOMY. Maturity levels and capability names come from the CX framework the assessment
scores against (Manage / Analyze / Improve, nine capabilities) -- the same one the desk-research
report groups by. The issue log's Excel export classifies by strategic dimension instead, so this
page will not line up with an exported issue log, by design.

ON THE SAME ASSESSMENT TWICE. Several interviews in a project are usually generated from the SAME
Orion assessment, so the assessments are deduplicated before anything is counted or sent to the
model: two interviews off one assessment is one self-assessment to contradict, not two.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from app.core.text_normalization import repair_encoding

logger = logging.getLogger(__name__)

# Worst first, matching the desk-research report so the two read the same way.
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# How much interview transcript to send. Answers are long-form and there can be several
# interviews; past this the model starts losing the early ones rather than reading them all.
_TRANSCRIPT_BUDGET = 60_000


# --------------------------------------------------------------------------- #
#  Gathering                                                                    #
# --------------------------------------------------------------------------- #

def _transcript(interviews: list[dict]) -> str:
    """The interviews as one document the model reads, labelled so it can attribute a quote.

    Truncation is per-interview rather than off the end of the whole string: cutting the tail
    would drop the last interview entirely and the model would never know it existed.
    """
    if not interviews:
        return "(no interviews)"
    budget = max(_TRANSCRIPT_BUDGET // max(len(interviews), 1), 4_000)
    blocks: list[str] = []
    for iv in interviews:
        lines = [
            f"=== INTERVIEW #{iv['id']}: {iv['company_name']} -- {iv['profile']} "
            f"({iv['answered']} of {iv['total']} questions answered) ==="
        ]
        for row in iv["answers"]:
            lines.append(f"- Q: {row['question']}\n  A: {row['answer']}")
        block = "\n".join(lines)
        if len(block) > budget:
            block = block[:budget] + "\n[... this interview truncated ...]"
        blocks.append(block)
    return "\n\n".join(blocks)


def _self_assessments(assessments: list[dict]) -> str:
    """The Orion conversations and the levels they produced -- what the report argues against."""
    if not assessments:
        return "(no self-assessment was used for these interviews)"
    blocks: list[str] = []
    for a in assessments:
        lines = [f"=== ORION SELF-ASSESSMENT #{a['id']} ==="]
        for qa in a["conversation"]:
            lines.append(f"Orion: {qa['question']}\nClient: {qa['answer']}")
        if a["scores"]:
            lines.append("\nLevels the client's own answers produced:")
            for s in a["scores"]:
                lines.append(
                    f"- {s['axis']} / {s['capability']}: Level {s['level']}"
                    f"{' (' + s['level_label'] + ')' if s.get('level_label') else ''}"
                    f" -- {s['justification']}"
                )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
#  The computed half                                                            #
# --------------------------------------------------------------------------- #


def _sev_rank(finding: dict) -> tuple[int, str]:
    sev = str(finding.get("severity") or "").lower()
    return SEVERITY_ORDER.get(sev, 4), str(finding.get("title") or "")


def _findings(interviews: list[dict]) -> list[dict]:
    """Every interview's stored cx_findings, worst first, each carrying the interview it came from.

    These were already extracted and persisted when the per-interview insights were generated, so
    rolling them up here costs nothing and cannot disagree with what the Issue Log will show.
    """
    out: list[dict] = []
    for iv in interviews:
        for f in iv.get("cx_findings") or []:
            if not isinstance(f, dict) or not str(f.get("title") or "").strip():
                continue
            out.append({**f, "interview_id": iv["id"], "interview_profile": iv["profile"]})
    return sorted(out, key=_sev_rank)


def _coverage(interviews: list[dict]) -> list[dict]:
    """One row per interview: who was spoken to and how much of the guide they actually answered.

    The interview number is shown rather than kept internal: two interviews of one client often
    do carry the same stated role, and two identical rows tell the reader nothing about which is
    which. It also survives a wrong label -- guides saved before the profile was returned on read
    could be relabelled "CEO" by their own autosave, so older rows may still say the wrong thing.
    """
    return [
        {
            "interview_id": iv["id"],
            "profile": iv["profile"] or "Unspecified",
            "answered": iv["answered"],
            "total": iv["total"],
            "findings": len(iv.get("cx_findings") or []),
            "has_insights": bool(iv.get("insights_markdown")),
            "assessment_id": iv.get("assessment_id"),
        }
        for iv in interviews
    ]


def _maturity(assessments: list[dict]) -> list[dict]:
    """The self-assessed level per capability, across the project's assessments.

    Where two assessments scored the same capability, the LOWEST level is kept and the count of
    sources noted. Taking the best of two would flatter the client, and this table exists to be
    argued with by the interviews.
    """
    by_capability: dict[str, dict] = {}
    for a in assessments:
        for s in a["scores"]:
            key = s["capability"]
            current = by_capability.get(key)
            if current is None:
                by_capability[key] = {
                    "axis": s["axis"], "capability": key, "level": s["level"],
                    "level_label": s.get("level_label"), "sources": 1,
                }
            else:
                current["sources"] += 1
                if s["level"] is not None and (
                    current["level"] is None or s["level"] < current["level"]
                ):
                    current["level"] = s["level"]
                    current["level_label"] = s.get("level_label")
    return sorted(by_capability.values(), key=lambda r: (r["axis"], r["capability"]))


def _kpis(interviews: list[dict], assessments: list[dict], findings: list[dict],
          contradictions: list[dict]) -> list[dict]:
    """The tiles across the top. Every one is a count of records, not a judgement.

    There is deliberately no "roles covered" tile. It would be counted from `profile`, and any
    guide saved before that field was returned on read could have been relabelled "CEO" by its
    own autosave -- so the tile would state a number the prose beside it contradicts. The
    coverage table names the roles instead, where a wrong one is visible rather than summed away.
    """
    answered = sum(iv["answered"] for iv in interviews)
    total = sum(iv["total"] for iv in interviews)
    severe = [f for f in findings
              if str(f.get("severity") or "").lower() in ("critical", "high")]
    return [
        {"label": "Interviews", "value": len(interviews), "tone": "neutral"},
        {"label": "Contradictions", "value": len(contradictions),
         "tone": "bad" if contradictions else "good"},
        {"label": "Questions answered", "value": f"{answered} of {total}",
         "tone": "good" if total and answered == total else "warn"},
        {"label": "Issues raised", "value": len(findings),
         "tone": "warn" if findings else "good"},
        {"label": "High or critical", "value": len(severe),
         "tone": "bad" if severe else "good"},
        {"label": "Self-assessments", "value": len(assessments), "tone": "neutral"},
    ]


# --------------------------------------------------------------------------- #
#  The prompt                                                                   #
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """You are a customer-experience consultant writing the interview chapter of a client report. Several interviews have been run for one client, and you are writing what they say TOGETHER -- for a colleague who will scan this before a client meeting.

WHAT MAKES THIS WORTH READING
Anyone can summarise one interview. The value here is in the seams:
- What more than one person independently described. Two people naming the same problem, unprompted, is the strongest evidence in the whole engagement.
- Where the interviews DISAGREE WITH EACH OTHER. Two people in the same company describing the same process differently is a finding about the company, not a mistake.
- Where the interviews DISAGREE WITH THE SELF-ASSESSMENT. Before these interviews, the client scored themselves through the Orion questionnaire and those answers produced a maturity level per capability. A client who scores themselves rarely describes their own gaps accurately. Where a person's account is plainly worse than the level they scored, say so and name both sides -- that is usually the single most useful thing on the page.

Take the levels seriously as claims: Level 1 is ad hoc, Level 2 means something exists but is inconsistent, Level 3 and above mean it is defined and followed. If someone scored Level 2 on ownership and the interview says nobody actually owns anything when it crosses a team boundary, that is a contradiction worth writing.

HOW TO WRITE
Write the way you would explain this to a colleague over coffee: professional, but easy.
- Short sentences. One idea each. If you would not say it aloud, rewrite it.
- Everyday words. "Use", not "utilise". "Start", not "initiate". "Problem", not "pain point".
- No consulting filler. Never "leverage", "synergies", "holistic", "landscape", "robust", "going forward", "at scale", "operational excellence".
- Quote the person when their own words land better than a summary. Keep quotes short and exact -- never adjust a quote to make a point.
- Every figure, name and date exactly as it appears. Never invent, never round.
- Say what something MEANS in the same breath as what it says.

ALWAYS NAME YOUR SOURCE
Every claim traces to an interview or to the self-assessment. Name the role you heard it from and the interview number, like "the Marketing Director (interview 13)". Never attribute something to a person who did not say it, and never merge two people into one voice.

Each interview is labelled with a stated role, but that label is metadata a consultant picked from a list and older interviews can carry the wrong one. The questions and answers are the truth. If an interview opens by asking about someone's role as Marketing Director, they are the Marketing Director whatever the label says, and you should call them that.

LANGUAGE -- write every string in ONE language, matching the interviews. Default to clear English.

OUTPUT -- return ONLY a JSON object in exactly this shape. No prose, no markdown, no code fence:

{{
  "headline": "One sentence a consultant could open the meeting with. What these interviews
               together say about this client, with the detail that carries it.",
  "cx_culture": {{"verdict": "Two or three sentences on how customer experience actually works
                    here day to day -- who cares, what happens when it matters, what the
                    interviews show about how decisions really get made. Not a score, a read.",
                  "evidence": ["2 to 4 short lines that back the verdict. A quote or a specific",
                               "each, with the role it came from."]}},
  "themes": [{{"theme": "What came up, in a few words. A statement, not a topic label.",
              "detail": "What was said and what it means. Two or three sentences.",
              "heard_from": "the roles this came from, e.g. 'CEO (interview 11 and 13)'",
              "quote": "a short exact quote if one makes the point, otherwise an empty string"}}],
  "contradictions": [{{"between": "who or what disagrees, e.g. 'The CEO vs the self-assessment'",
                      "claimed": "what the self-assessment said, or what one person said",
                      "heard": "what the interview actually said",
                      "so_what": "why this matters for the work. One sentence."}}],
  "recommendations": [{{"action": "What to do, concretely. Something startable on Monday.",
                       "why": "The interview finding it comes from and what it would change.",
                       "source": "the role or interview it traces to"}}]
}}

RULES
- "themes": 3 to 5, most important first. A theme only one person mentioned is still a theme, but say so in "heard_from" rather than implying agreement.
- "contradictions": this is the section the reader came for. Include every real one. If there are genuinely none, return an empty list -- never invent one to fill the space, and never soften a real one into a "nuance".
- "recommendations": 3 to 5. Each names a thing to do, a person who would do it, or a number to go and check. Never a bare verb: "improve governance" and "enhance the feedback loop" say nothing and are worse than silence.
- Do NOT write counts, the coverage table, the maturity table or the issue list. Those are computed from the records and would only disagree with themselves if you wrote them too.
"""


def _user_prompt(company: str, interviews: list[dict], assessments: list[dict],
                 maturity: list[dict], language: str) -> str:
    levels = "\n".join(
        f"- {m['axis']} / {m['capability']}: Level {m['level']}" for m in maturity
    ) or "(no maturity levels were scored)"
    return (
        f"CLIENT: {company}\nOutput language: {language}\n\n"
        f"There are {len(interviews)} interviews and "
        f"{len(assessments)} distinct Orion self-assessment(s) behind them.\n\n"
        f"=== WHAT THE CLIENT SCORED THEMSELVES ===\n{levels}\n\n"
        f"{_self_assessments(assessments)}\n\n"
        f"=== THE INTERVIEWS ===\n{_transcript(interviews)}\n\n"
        "Write the JSON now."
    )


# --------------------------------------------------------------------------- #
#  Assembly                                                                     #
# --------------------------------------------------------------------------- #


def _str_list(raw: Any) -> list[str]:
    return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []


def _dict_list(raw: Any) -> list[dict]:
    return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []


def build_overview(
    part: dict[str, Any],
    interviews: list[dict],
    assessments: list[dict],
    company: str,
) -> dict[str, Any]:
    """Combine what the model wrote with what Python counted.

    Anything missing from `part` degrades to empty rather than raising: a report showing the
    coverage and the issues is worth having even when the model's half came back malformed.
    """
    part = part if isinstance(part, dict) else {}
    culture = part.get("cx_culture")
    culture = culture if isinstance(culture, dict) else {}
    findings = _findings(interviews)
    contradictions = _dict_list(part.get("contradictions"))

    return {
        "company": company,
        "headline": str(part.get("headline") or "").strip(),
        "kpis": _kpis(interviews, assessments, findings, contradictions),
        "cx_culture": {
            "verdict": str(culture.get("verdict") or "").strip(),
            "evidence": _str_list(culture.get("evidence")),
        },
        "themes": _dict_list(part.get("themes")),
        "contradictions": contradictions,
        "issues": findings,
        "coverage": _coverage(interviews),
        "maturity": _maturity(assessments),
        "recommendations": _dict_list(part.get("recommendations")),
    }


# --------------------------------------------------------------------------- #
#  Markdown rendering                                                           #
# --------------------------------------------------------------------------- #
#
# The same small grammar the rest of the platform's reports use -- `#`/`##` headings, `-` bullets,
# pipe tables, **bold** -- because MarkdownRenderer and the PDF exporter parse it separately and
# anything beyond it prints as literal characters in the PDF.


def _cell(value: Any) -> str:
    """A pipe inside a cell ends the cell. Only None is empty: `value or ""` blanks a zero."""
    if value is None:
        return ""
    return str(value).replace("|", "/").replace(chr(10), " ").strip()


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return []
    return (
        ["| " + " | ".join(headers) + " |",
         "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    )


def render_markdown(overview: dict[str, Any]) -> str:
    lines: list[str] = [f"# {overview.get('company') or 'Interview report'}"]

    if overview.get("headline"):
        lines += ["", f"**{overview['headline']}**"]

    kpi_bits = [f"{k['label']}: **{k['value']}**" for k in overview.get("kpis") or []]
    if kpi_bits:
        lines += ["", " · ".join(kpi_bits)]

    culture = overview.get("cx_culture") or {}
    if culture.get("verdict") or culture.get("evidence"):
        lines += ["", "## How customer experience actually works here", ""]
        if culture.get("verdict"):
            lines.append(culture["verdict"])
        if culture.get("evidence"):
            lines.append("")
            lines += [f"- {e}" for e in culture["evidence"]]

    if overview.get("themes"):
        lines += ["", "## What came up across the interviews", ""]
        for t in overview["themes"]:
            lines.append(f"- **{_cell(t.get('theme'))}** — {_cell(t.get('detail'))}")
            if t.get("heard_from"):
                lines.append(f"  *Heard from: {_cell(t['heard_from'])}*")
            if t.get("quote"):
                lines.append(f"  “{_cell(t['quote'])}”")

    if overview.get("contradictions"):
        lines += ["", "## Where the accounts disagree", ""]
        lines += _table(
            ["Between", "What was claimed", "What the interview said", "Why it matters"],
            [[c.get("between"), c.get("claimed"), c.get("heard"), c.get("so_what")]
             for c in overview["contradictions"]],
        )

    if overview.get("issues"):
        lines += ["", "## Issues raised", ""]
        lines += _table(
            ["Severity", "Issue", "Dimension", "Raised in"],
            [[(str(i.get("severity") or "").capitalize() or "-"),
              i.get("title") or i.get("description"),
              i.get("dimension") or "-",
              f"interview {i.get('interview_id')}"]
             for i in overview["issues"]],
        )

    if overview.get("maturity"):
        lines += ["", "## What the client scored themselves", ""]
        lines += _table(
            ["Axis", "Capability", "Self-assessed level"],
            [[m["axis"], m["capability"],
              f"Level {m['level']}" if m.get("level") is not None else "not scored"]
             for m in overview["maturity"]],
        )

    if overview.get("coverage"):
        lines += ["", "## Who was interviewed", ""]
        lines += _table(
            ["Interview", "Stated role", "Questions answered", "Issues raised"],
            [[f"#{c['interview_id']}", c["profile"],
              f"{c['answered']} of {c['total']}", c["findings"]]
             for c in overview["coverage"]],
        )

    if overview.get("recommendations"):
        lines += ["", "## What to do next", ""]
        for i, r in enumerate(overview["recommendations"], 1):
            lines.append(f"{i}. **{_cell(r.get('action'))}**")
            if r.get("why"):
                lines.append(f"   {_cell(r['why'])}")
            if r.get("source"):
                lines.append(f"   *Source: {_cell(r['source'])}*")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------- #
#  Entry point                                                                  #
# --------------------------------------------------------------------------- #


def _default_llm() -> Callable[[str, str], Awaitable[str]]:
    """Mistral -> OpenAI -> Gemini, cycled with a backoff, the same loop the desk-research report
    uses.

    A single-provider call was not good enough here: this prompt is ~35k characters and Mistral
    rate-limits on it routinely, and a report the user pressed a button for must not fail because
    one provider was busy. Returns an "Error: ..." sentinel if every provider fails, which
    `generate` turns into an empty prose half rather than a crash.
    """
    from app.core.config import get_settings
    from app.services.llm.core.gateway import build_mistral_gateway
    from app.services.llm.failover import complete_with_failover

    gateway = build_mistral_gateway(get_settings())

    async def _mistral(system_prompt: str, user_prompt: str) -> str | None:
        return await gateway.chat_messages(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user_prompt}]
        )

    async def _llm(system_prompt: str, user_prompt: str) -> str:
        return await complete_with_failover(
            system_prompt, user_prompt, primary=_mistral, label="interview.project_report"
        )

    return _llm


async def generate(
    company: str,
    interviews: list[dict],
    assessments: list[dict],
    language: str = "en",
    *,
    llm_fn: Callable[[str, str], Awaitable[str]] | None = None,
) -> tuple[dict, str]:
    """Produce (overview, markdown) for a project's interviews.

    Raises ValueError when there is nothing to report on, so the route can answer 400 rather than
    persisting an empty report.
    """
    if not interviews:
        raise ValueError("This project has no interviews to report on.")
    if not any(iv["answered"] for iv in interviews):
        raise ValueError(
            "None of this project's interviews have recorded answers yet. "
            "Record some answers, then generate the report."
        )

    from app.services.llm.utils import extract_json
    from app.services.observability.llm_metrics import llm_context

    maturity = _maturity(assessments)
    llm = llm_fn or _default_llm()
    with llm_context(feature="interview.project_report", kind="run"):
        raw = await llm(
            SYSTEM_PROMPT,
            _user_prompt(company, interviews, assessments, maturity, language),
        )

    if not raw or raw.strip().startswith("Error:"):
        logger.warning("Project interview report: every provider failed (%s)",
                       (raw or "").strip()[:120])
        raw = ""

    try:
        part = extract_json(repair_encoding(raw))
    except Exception:
        # The computed half -- coverage, issues, maturity -- is unaffected and still worth
        # showing, so a parse failure degrades rather than losing the run.
        logger.warning("Project interview report: JSON parse failed; prose will be empty")
        part = {}

    overview = build_overview(part if isinstance(part, dict) else {},
                              interviews, assessments, company)
    return overview, render_markdown(overview)
