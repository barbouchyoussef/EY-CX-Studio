"""The desk-research executive overview: a structured object the UI can lay out.

Why this exists. The overview used to be one markdown blob the model wrote end to end. A
consultant reading it had to parse prose to find the problems, and every number in it was a
number the model had chosen to repeat. Neither is what the module is for.

The split here follows the rule the rest of the platform already works to: **the model writes
prose, Python computes figures.** So

    the model supplies   -- the headline, the scannable takeaways, what each document is, and
                            recommendations phrased against the CX framework;
    Python supplies      -- every count, the problem list, the strengths, and axis coverage,
                            all derived from `cx_findings`, which is already validated against
                            the framework and is what the issue log consumes.

That means a KPI on this page cannot be wrong unless the findings themselves are.

WHICH TAXONOMY THIS USES, because there are two and they are not the same. Everything here is
grouped by the CX capability framework -- Manage / Analyze / Improve and their nine capabilities
-- which is what `cx_findings` carries and what the maturity assessment scores. The issue log
classifies by a different axis entirely: the analyst workbook's strategic dimensions (Customer
Service, Systems and Technology, Processes & Policies and so on), which say where in the business
a problem sits rather than which CX capability it is evidence about.

Which of the issue log's two paths this lines up with is worth being exact about:

  collector.collect_findings   reads `cx_findings` directly, so it shares this page's grouping;
  pipeline.generate_issues     the one behind the Excel export, generates its own issues from
                               the deep-dives and classifies them by strategic dimension.

So this page agrees with the consolidation path and will NOT line up with an exported issue log,
in grouping or in count. That is deliberate rather than a defect: the report answers "what do
these documents say about how this client runs customer experience", the export answers "what is
broken and whose problem is it".

`render_markdown` exists because `report_markdown` still has three consumers that must keep
working: the RAG index the session chatbot answers from, the PDF export, and the legacy issue-log
path that splits an old report on its Part 2 heading. The structured object is the source of
truth; the markdown is a rendering of it.
"""

from __future__ import annotations

from typing import Any, Iterable

# Worst first: this is the order a consultant wants to read problems in, and the order the
# markdown rendering and the UI both present them.
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# The three things a finding can be, kept apart because the report labels them differently.
#
# An opportunity is NOT a strength. Grouping the two put "Low digital sales channel utilization"
# and "Investigate the unknown web traffic" under a heading reading "What is working", which
# says the opposite of what the finding says. They get their own section instead.
PROBLEM_TYPES = {"friction", "gap"}
STRENGTH_TYPES = {"strength"}
OPPORTUNITY_TYPES = {"opportunity"}

AXES = ("Manage", "Analyze", "Improve")


def _sev_rank(finding: dict) -> tuple[int, str]:
    """Sort key: severity worst-first, then title so the order is stable between runs."""
    sev = (finding.get("severity") or "").lower()
    return SEVERITY_ORDER.get(sev, 4), str(finding.get("title") or "")


def _problems(findings: Iterable[dict]) -> list[dict]:
    return sorted((f for f in findings if f.get("type") in PROBLEM_TYPES), key=_sev_rank)


def _strengths(findings: Iterable[dict]) -> list[dict]:
    return [f for f in findings if f.get("type") in STRENGTH_TYPES]


def _opportunities(findings: Iterable[dict]) -> list[dict]:
    return [f for f in findings if f.get("type") in OPPORTUNITY_TYPES]


def _coverage(findings: list[dict]) -> list[dict]:
    """Findings per axis, with the capabilities each one touched.

    An axis with nothing against it is kept and shown as zero. That absence is a finding in
    itself -- a document set that says nothing about how the client acts on pain points is worth
    seeing, and dropping the empty row would hide it.
    """
    out = []
    for axis in AXES:
        hits = [f for f in findings if f.get("axis") == axis]
        capabilities = sorted({str(f.get("capability")) for f in hits if f.get("capability")})
        out.append({
            "axis": axis,
            "findings": len(hits),
            "problems": len([f for f in hits if f.get("type") in PROBLEM_TYPES]),
            "capabilities": capabilities,
        })
    return out


def _kpis(findings: list[dict], document_count: int) -> list[dict]:
    """The tiles across the top. Every one is a count of something real."""
    problems = _problems(findings)
    severe = [f for f in problems if (f.get("severity") or "").lower() in ("critical", "high")]
    axes_hit = len({f.get("axis") for f in findings if f.get("axis")})
    return [
        {"label": "Documents analysed", "value": document_count, "tone": "neutral"},
        {"label": "CX findings", "value": len(findings), "tone": "neutral"},
        {"label": "Problems identified", "value": len(problems), "tone": "warn" if problems else "good"},
        {"label": "High or critical", "value": len(severe), "tone": "bad" if severe else "good"},
        {"label": "Axes covered", "value": f"{axes_hit} of {len(AXES)}", "tone": "neutral"},
    ]


def _takeaways(raw: list) -> list[dict]:
    """Normalise to {point, source}.

    The prompt asks for objects so a point can carry the document it came from, but a model that
    answers with plain strings should still produce a readable report rather than a blank section.
    """
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            point = str(item.get("point") or "").strip()
            source = str(item.get("source") or "").strip()
        else:
            point, source = str(item).strip(), ""
        if point:
            out.append({"point": point, "source": source or None})
    return out


def _recommendation(raw: dict) -> dict:
    """Show the capability's real name, whatever form the model named it in.

    Asked for "the capability name", a model often answers with the bracketed code it was shown
    instead -- `analyze_journey_visibility`. The problems list resolves those, so leaving these
    raw put slugs and proper names side by side on the same page.
    """
    from app.services.cx_framework import resolve_capability

    out = dict(raw)
    name, _axis = resolve_capability(out.get("capability"))
    if name:
        out["capability"] = name
    return out


def build_overview(
    part1: dict[str, Any],
    findings: list[dict],
    document_count: int,
) -> dict[str, Any]:
    """Combine what the model wrote with what Python counted.

    `part1` is the model's JSON. Anything missing from it degrades to empty rather than raising:
    a report with no recommendations is worth showing, and a 500 because one key was absent is
    not.
    """
    part1 = part1 if isinstance(part1, dict) else {}

    def _list(key: str) -> list:
        value = part1.get(key)
        return [v for v in value if v] if isinstance(value, list) else []

    return {
        "headline": str(part1.get("headline") or "").strip(),
        "period": str(part1.get("period") or "").strip() or None,
        "kpis": _kpis(findings, document_count),
        "takeaways": _takeaways(_list("takeaways")),
        "documents": [d for d in _list("documents") if isinstance(d, dict)],
        "connections": [str(c).strip() for c in _list("connections") if str(c).strip()],
        "problems": _problems(findings),
        "strengths": _strengths(findings),
        "opportunities": _opportunities(findings),
        "coverage": _coverage(findings),
        "recommendations": [_recommendation(r) for r in _list("recommendations") if isinstance(r, dict)],
    }


# ------------------------------------------------------------------------------------------
# Markdown rendering
#
# `report_markdown` still feeds the session chatbot's index, the PDF export and the legacy
# issue-log split, so the structured overview is rendered back into the same small markdown
# grammar those three already understand: `#`/`##` headings, `-` bullets, pipe tables, **bold**.
# Nothing new is introduced, because the renderer and the PDF exporter parse this grammar
# separately and adding syntax to one without the other prints literal asterisks.
# ------------------------------------------------------------------------------------------

def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def _cell(value: Any) -> str:
    """A pipe inside a cell ends the cell, so it cannot survive in the text.

    Only None is empty. `value or ""` would blank a zero, and a zero is the most interesting
    number in the coverage table: an axis the documents said nothing about.
    """
    if value is None:
        return ""
    return str(value).replace("|", "/").replace(chr(10), " ").strip()


def _severity_label(finding: dict) -> str:
    sev = (finding.get("severity") or "").strip()
    return sev.capitalize() if sev else "-"


def render_markdown(overview: dict[str, Any], title: str) -> str:
    """The structured overview as the markdown the rest of the pipeline expects."""
    lines: list[str] = [f"# {title}"]

    if overview.get("period"):
        lines += ["", f"*{overview['period']}*"]

    if overview.get("headline"):
        lines += ["", f"**{overview['headline']}**"]

    kpi_bits = [f"{k['label']}: **{k['value']}**" for k in overview.get("kpis") or []]
    if kpi_bits:
        lines += ["", " · ".join(kpi_bits)]

    if overview.get("takeaways"):
        lines += ["", "## What this set shows", ""]
        for t in overview["takeaways"]:
            source = f"  *{t['source']}*" if t.get("source") else ""
            lines.append(f"- {t['point']}{source}")

    documents = overview.get("documents") or []
    if documents:
        lines += ["", "## What each document contains", ""]
        lines += _table(
            ["Document", "What it is", "Period", "What it tells you"],
            [[d.get("name"), d.get("what_it_is"), d.get("period"), d.get("key_point")]
             for d in documents],
        )

    if overview.get("connections"):
        lines += ["", "## How they connect", ""]
        lines += [f"- {c}" for c in overview["connections"]]

    problems = overview.get("problems") or []
    if problems:
        lines += ["", "## Problems found", ""]
        lines += _table(
            ["Severity", "Problem", "CX capability", "Source"],
            [[_severity_label(p), p.get("title") or p.get("description"),
              p.get("capability"), p.get("source_document")] for p in problems],
        )

    strengths = overview.get("strengths") or []
    if strengths:
        lines += ["", "## What is working", ""]
        lines += [f"- **{s.get('title') or 'Strength'}** — {s.get('description')}"
                  for s in strengths]

    opportunities = overview.get("opportunities") or []
    if opportunities:
        lines += ["", "## Opportunities", ""]
        lines += [f"- **{o.get('title') or 'Opportunity'}** — {o.get('description')}"
                  for o in opportunities]

    coverage = [c for c in (overview.get("coverage") or [])]
    if coverage:
        lines += ["", "## Coverage across the CX framework", ""]
        lines += _table(
            ["Axis", "Findings", "Problems", "Capabilities touched"],
            [[c["axis"], c["findings"], c["problems"], ", ".join(c["capabilities"]) or "-"]
             for c in coverage],
        )

    recommendations = overview.get("recommendations") or []
    if recommendations:
        lines += ["", "## What to do next", ""]
        for i, r in enumerate(recommendations, 1):
            action = str(r.get("action") or "").strip()
            why = str(r.get("why") or "").strip()
            capability = str(r.get("capability") or "").strip()
            source = str(r.get("source") or "").strip()
            lines.append(f"{i}. **{action}**" if action else f"{i}.")
            if why:
                lines.append(f"   {why}")
            if capability:
                lines.append(f"   *Capability: {capability}*")
            if source:
                lines.append(f"   *Source: {source}*")
            lines.append("")

    return "\n".join(lines).strip() + "\n"
