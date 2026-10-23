"""Turn a module's saved output into the chunks the issue generator reads.

Two source types, because they need opposite handling. Both rules are measured, not assumed:

DOCUMENT (desk research)
    Split per document. Identical material sent as ONE call produced 45 issues; the same text
    split per document produced 141. Given everything at once the model curates; given one
    document it extracts. The reference workbook works the same way -- its "Inspection Point"
    column names an individual file, not a session.

VOICE (social listening: reviews, comments, complaints)
    Never split. Six chunks of the same review set each independently rediscovered "slow branch
    service", giving 40% redundancy; the whole set in one call gave 0-9%. The model needs to see
    every report at once to know which problem has 42 people behind it and which has one.

Also excluded: the desk report's Part 1 synthesis. It restates the per-document deep-dives, so
feeding both builds duplication into the input -- it put four versions of one issue in a log.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

Mode = Literal["document", "voice"]

# Deliberately pessimistic: over-estimating length makes the throttle reserve a little too much,
# which is safer than under-reserving and hitting a rate limit mid-run.
_CHARS_PER_TOKEN = 3.6

# A source thinner than this has nothing to diagnose; generating from it invites invention.
MIN_USEFUL_TOKENS = 400


def est_tokens(text: str) -> int:
    return int(len(text or "") / _CHARS_PER_TOKEN)


@dataclass
class SourceChunk:
    """One unit of material for one LLM call, and the label that becomes 'Inspection Point'."""

    label: str                 # the individual document or report, shown in the workbook
    body: str
    mode: Mode
    client: str
    artifact_kind: str         # desk_session | social_report | interview_guide | assessment
    artifact_ref: str          # the id, so every issue traces back to its origin

    @property
    def tokens(self) -> int:
        return est_tokens(self.body)

    def render(self) -> str:
        return f"### SOURCE: {self.label}\n{self.body.strip()}"


@dataclass
class SourceBundle:
    """Everything selected for one run, plus what was skipped and why."""

    chunks: list[SourceChunk] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return sum(c.tokens for c in self.chunks)

    def by_client(self) -> dict[str, list[SourceChunk]]:
        out: dict[str, list[SourceChunk]] = {}
        for c in self.chunks:
            out.setdefault(c.client, []).append(c)
        return out


# --------------------------------------------------------------------------------------------
# Desk research
# --------------------------------------------------------------------------------------------

_DEEP_DIVE_SPLIT = re.compile(r"\n(?=### )")
# Desk reports carry per-axis sections (Manage / Analyze / Improve) alongside the per-document
# deep-dives. They are cross-cutting summaries, not documents, and naming one as an Inspection
# Point produces issues whose stated source is meaningless.
_NOT_A_DOCUMENT = {"manage", "analyze", "analyse", "improve", "recommendations",
                   "executive summary", "risks & data gaps", "how the documents relate",
                   "the document set at a glance", "key findings across the set"}


def chunks_from_desk(session_info, ref: str, client: str | None = None) -> list[SourceChunk]:
    """One chunk per analysed document.

    Reads ``document_analyses`` -- the per-document deep-dives, stored apart from the report
    since they are analysis input rather than reading material. Sessions generated before that
    split keep working: their deep-dives still live inside ``report_markdown`` under Part 2, and
    are recovered by splitting on the per-document headings.
    """
    label_client = (client or getattr(session_info, "title", None) or "Desk research").strip()

    analyses = [a for a in (getattr(session_info, "document_analyses", None) or []) if a.strip()]
    if analyses:
        out: list[SourceChunk] = []
        for block in analyses:
            block = block.strip()
            first = block.splitlines()[0] if block else ""
            title = first.lstrip("# ").strip() if first.startswith("#") else ""
            if not title:
                title = f"Document {len(out) + 1}"
            out.append(SourceChunk(label=title, body=block, mode="document",
                                   client=label_client, artifact_kind="desk_session",
                                   artifact_ref=ref))
        return out

    markdown = (getattr(session_info, "report_markdown", None) or "").strip()
    if not markdown:
        return []

    split_at = markdown.find("## Part 2")
    deep_dives = markdown[split_at:] if split_at > 0 else markdown

    out: list[SourceChunk] = []
    for block in _DEEP_DIVE_SPLIT.split(deep_dives):
        block = block.strip()
        if not block.startswith("### "):
            continue
        title = block.splitlines()[0].lstrip("# ").strip()
        if title.strip().lower() in _NOT_A_DOCUMENT:
            continue
        if est_tokens(block) < 60:          # a heading with no content beneath it
            continue
        out.append(SourceChunk(label=title, body=block, mode="document", client=label_client,
                               artifact_kind="desk_session", artifact_ref=ref))
    return out


# --------------------------------------------------------------------------------------------
# Social listening
# --------------------------------------------------------------------------------------------

def _raw_reviews(result: dict) -> str:
    """Every collected review as one block: platform, rating, date, text."""
    platforms = result.get("platforms") or []
    if isinstance(platforms, dict):
        platforms = list(platforms.values())

    lines: list[str] = []
    for entry in platforms:
        if not isinstance(entry, dict):
            continue
        name = entry.get("platform") or "platform"
        for review in entry.get("reviews") or []:
            if isinstance(review, str):
                if review.strip():
                    lines.append(f"[{name}] {review.strip()}")
                continue
            if not isinstance(review, dict):
                continue
            text = review.get("text") or review.get("content") or review.get("snippet") or ""
            if not str(text).strip():
                continue
            meta = " ".join(str(x) for x in (review.get("rating") or review.get("stars") or "",
                                             str(review.get("date") or "")[:10]) if x)
            lines.append(f"[{name}{' ' + meta if meta else ''}] {str(text).strip()}")
    return "\n".join(lines)


def _friction_themes(result: dict) -> str:
    """The module's own tally of recurring themes, with mention counts.

    This is a deterministic aggregate the scraping module already computed over the same reviews:
    each theme carries how many reviews raised it and what share of negative sentiment it holds.
    That maps almost directly onto an issue plus its ``reports`` count, so it is passed alongside
    the raw reviews rather than instead of them -- the themes say which problems are real and how
    big, the reviews supply the verbatim quote and the texture.
    """
    detailed = result.get("detailed_report") or {}
    themes = detailed.get("top_friction_points") or []
    if not themes:
        return ""

    lines: list[str] = []
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        name = str(theme.get("theme") or theme.get("label") or "").strip()
        if not name:
            continue
        bits = [f"- {name}"]
        count = theme.get("mention_count") or theme.get("count")
        share = theme.get("share_pct")
        if count:
            bits.append(f"raised in {count} reviews")
        if share:
            bits.append(f"{share}% of negative sentiment")
        head = "  (" + ", ".join(bits[1:]) + ")" if len(bits) > 1 else ""
        lines.append(bits[0] + head)
        description = str(theme.get("description") or "").strip()
        if description:
            lines.append(f"    {description}")
        for quote in (theme.get("supporting_evidence") or [])[:3]:
            if str(quote).strip():
                lines.append(f"    evidence: {str(quote).strip()}")
    return "\n".join(lines)


def _computed_layer(result: dict) -> str:
    """Everything the module computed, for reports with too few raw reviews to reason over.

    Nothing is truncated: an earlier build sliced these at fixed character counts and cut through
    the middle of JSON objects, handing the model malformed input.
    """
    detailed = result.get("detailed_report") or {}
    parts: list[str] = []
    for key in ("executive_summary", "overall_sentiment", "top_friction_points",
                "evidence", "channel_breakdown", "website_assessment"):
        value = detailed.get(key)
        if not value:
            continue
        rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=1)
        parts.append(f"## {key}\n{rendered}")
    return "\n\n".join(parts)


def chunks_from_social(result: dict, ref: str, client: str | None = None) -> list[SourceChunk]:
    """One chunk for the whole report -- never split (see the module docstring).

    When there are enough raw reviews, the chunk carries the computed friction themes first and
    the individual reports second. The themes are the aggregate view the model would otherwise
    have to reconstruct by counting; the reviews are what it quotes from. When a report has too
    few reviews, the computed layer stands alone.
    """
    brand = (client or result.get("brand_name") or "Social listening").strip()
    detailed = result.get("detailed_report") or {}

    raw = _raw_reviews(result)
    sections: list[str] = []

    if est_tokens(raw) >= MIN_USEFUL_TOKENS:
        themes = _friction_themes(result)
        if themes:
            sections.append(
                "## Recurring friction themes, computed from the reviews below\n"
                "Each theme is an aggregate of the individual reports that follow. Use the counts "
                "for `reports`; do not record a theme and its underlying reviews as two issues.\n"
                + themes)
        website = str(detailed.get("website_assessment") or "").strip()
        if website:
            sections.append("## Website assessment\n" + website)
        sections.append("## Individual customer reports\n" + raw)
        label = f"{brand} — customer reviews"
    else:
        sections.append(_computed_layer(result))
        label = f"{brand} — social listening report"

    body = "\n\n".join(s for s in sections if s.strip())
    if est_tokens(body) < MIN_USEFUL_TOKENS:
        return []
    return [SourceChunk(label=label, body=body, mode="voice", client=brand,
                        artifact_kind="social_report", artifact_ref=ref)]


# --------------------------------------------------------------------------------------------
# Interviews
# --------------------------------------------------------------------------------------------

# Interview insights are a distilled reading, not a transcript, so they are legitimately short --
# a full one runs ~350 tokens. The general floor would reject every one of them.
MIN_INTERVIEW_TOKENS = 150


def chunks_from_interview(insights_markdown: str | None, findings: list[dict] | None,
                          ref: str, label: str, client: str | None = None,
                          payload: dict | None = None) -> list[SourceChunk]:
    """One chunk per guide: the insights, any cached findings, and the gaps the guide flagged.

    A guide's payload is mostly the QUESTIONS to ask, which are not deficiencies. What carries
    issues is the analyst's reading of the answers (the insights), plus ``unanswered_areas`` --
    the topics the source assessment could not cover, which are gaps in their own right.

    Note for whoever reads this next: where no interview has actually been conducted, the
    insights are derived from the source assessment rather than from stakeholder answers. They
    are still useful, but they overlap with the assessment artifact, so selecting both double-
    counts. Once real interviews are recorded this becomes the richest source in the pipeline --
    it supplied 51% of the issues in the reference engagement.
    """
    payload = payload or {}
    parts: list[str] = []

    if findings:
        parts.append(f"Structured findings from the interview ({len(findings)}):")
        for f in findings:
            bits = [str(f.get("title") or ""), str(f.get("description") or "")]
            line = " — ".join(b for b in bits if b)
            if f.get("evidence"):
                line += f"\n    evidence: {str(f['evidence'])[:400]}"
            parts.append(f"- {line}")

    if insights_markdown and insights_markdown.strip():
        parts.append("\nInterview insights:\n" + insights_markdown.strip())

    summary = str(payload.get("executive_summary") or "").strip()
    if summary:
        parts.append("\nWhy this interview was scheduled:\n" + summary)

    gaps = payload.get("unanswered_areas") or []
    if isinstance(gaps, list) and gaps:
        rendered = []
        for gap in gaps:
            if isinstance(gap, dict):
                text = " — ".join(str(v).strip() for v in gap.values() if str(v).strip())
            else:
                text = str(gap).strip()
            if text:
                rendered.append(f"- {text}")
        if rendered:
            parts.append("\nAreas the assessment could not cover (gaps in what the client could "
                         "answer):\n" + "\n".join(rendered))

    body = "\n".join(parts)
    if est_tokens(body) < MIN_INTERVIEW_TOKENS:
        return []
    return [SourceChunk(label=label or "Interview", body=body, mode="voice",
                        client=(client or label or "Interview").strip(),
                        artifact_kind="interview_guide", artifact_ref=ref)]


# --------------------------------------------------------------------------------------------
# Maturity assessment
# --------------------------------------------------------------------------------------------

def chunks_from_assessment(rows: list[dict], ref: str, label: str,
                           client: str | None = None) -> list[SourceChunk]:
    """One chunk per axis, built around what the client actually SAID.

    The scored level is a conclusion; the answer behind it is the evidence. Raw material has
    beaten processed summaries at every other point in this pipeline, so the answer text leads
    and the scoring follows as supporting context.
    """
    by_axis: dict[str, list[dict]] = {}
    for row in rows or []:
        by_axis.setdefault(str(row.get("axis") or "Assessment").strip() or "Assessment", []).append(row)

    out: list[SourceChunk] = []
    for axis, items in by_axis.items():
        lines = [f"CX maturity assessment — {axis} axis.",
                 "Each entry is a question put to the client, their answer in their own words, "
                 "and the analyst's scoring of it.", ""]
        for r in items:
            capability = str(r.get("capability") or "").replace("_", " ").strip() or "capability"
            lines.append(f"— Capability: {capability}")
            if r.get("question"):
                lines.append(f"  Question asked: {str(r['question']).strip()}")
            if r.get("answer"):
                lines.append(f"  Client's answer: {str(r['answer']).strip()}")
            if r.get("level") not in (None, ""):
                lines.append(f"  Scored maturity level: {r['level']} (1 = lowest)")
            for key, prefix in (("justification", "Scoring rationale"),
                                ("recommendation", "Recommendation guideline"),
                                ("priority_hint", "Priority hint")):
                value = str(r.get(key) or "").strip()
                if value:
                    lines.append(f"  {prefix}: {value}")
            lines.append("")

        body = "\n".join(lines)
        if est_tokens(body) < MIN_USEFUL_TOKENS:
            continue
        out.append(SourceChunk(label=f"{label or 'CX maturity assessment'} — {axis}", body=body,
                               mode="document", client=(client or label or "Assessment").strip(),
                               artifact_kind="assessment", artifact_ref=ref))
    return out
