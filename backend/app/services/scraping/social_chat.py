"""Social-listening chatbot: same shared agentic engine, a different context source.

Where desk research *retrieves* text chunks, social *injects* its already-computed KPIs. The
metrics in ``DetailedSocialReport.evidence`` are exact numbers calculated in Python, so the right
move is to hand them to the model directly -- not to vector-search prose that merely mentions
them. This module provides that injection context source plus the social analyst role prompt; the
plan → gather → answer loop, history handling, and the <ModuleChat> front-end are all shared.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.core.config import get_settings
from app.core.text_normalization import repair_encoding
from app.schemas.scraping import DetailedSocialReport
from app.services.llm.core.gateway import build_mistral_gateway
from app.services.rag import engine

logger = logging.getLogger(__name__)

REPORT_SOURCE = "Social Report"

SOCIAL_CHAT_SYSTEM_PROMPT = """You are the EY CX Social Insights Assistant — a senior customer-experience
analyst answering questions about a brand's social-listening report.

You are given the report's STRUCTURED FINDINGS: sentiment splits, per-channel breakdowns, rating
distribution, top complaints and themes, friction points, strengths, recommendations, momentum,
trends, and sample verbatims. These numbers are computed deterministically from classified
reviews — they are exact. Treat them as ground truth.

How to answer:
- Greetings/thanks/small talk → respond briefly; no citation needed.
- Questions about the numbers → answer directly from the structured findings; quote the exact
  figures (percentages, counts, shares) rather than paraphrasing vaguely. Cite as [Social Report].
- "What are people saying about X?" → use the sample verbatims and complaint/theme labels.
- Analytical asks (compare channels, what's the biggest problem, what should we fix first) →
  reason over the findings; rank by the mention counts / shares provided.
- If a specific figure isn't in the findings, say so plainly — do NOT invent a number. Offer the
  closest thing the report does measure.
- Be concise and analytical in a professional EY tone. Bold key numbers. Answer in the user's language.
"""


# A single serialized report of this many characters or fewer is injected whole -- the reliable
# path (no retrieval miss, every report question answerable). Beyond it (a pathologically large
# report), we chunk and RAG over the report instead so the prompt stays bounded.
_MAX_INJECT_CHARS = 40_000


def _f(value: object, fmt: str = "{:.0f}") -> str:
    return fmt.format(value) if isinstance(value, (int, float)) else "n/a"


def report_to_context(report: DetailedSocialReport) -> str:
    """Serialize the ENTIRE report (every field, no caps) into a block for injection.

    Injecting the whole thing is what guarantees that any question about the report can be
    answered -- there is no retrieval step to miss a section. A report is small (a few KB), so
    this fits comfortably in context.
    """
    lines: list[str] = []
    ev = report.evidence

    if report.executive_summary:
        lines.append(f"EXECUTIVE SUMMARY:\n{report.executive_summary}")

    sent = report.overall_sentiment or (ev.overall_sentiment if ev else None)
    if sent:
        lines.append(
            f"OVERALL SENTIMENT: {_f(sent.positive_pct)}% positive, {_f(sent.neutral_pct)}% neutral, "
            f"{_f(sent.negative_pct)}% negative (n={sent.classified_count})."
        )

    if ev:
        lines.append(
            f"VOLUME: {ev.reviews_collected} reviews collected, {ev.reviews_with_text} with text, "
            f"{ev.reviews_classified} classified."
        )
        if ev.platform_sentiment:
            ch = "; ".join(
                f"{p.platform}: {_f(p.negative_pct)}% neg / {_f(p.positive_pct)}% pos of {p.review_count} reviews"
                + (f", avg {_f(p.avg_rating, '{:.1f}')}★" if p.avg_rating is not None else "")
                for p in ev.platform_sentiment
            )
            lines.append(f"PER-CHANNEL SENTIMENT: {ch}")
        if ev.rating_distribution:
            rd = ev.rating_distribution
            lines.append(
                f"RATING DISTRIBUTION: avg {_f(rd.average, '{:.2f}')}★ — "
                f"1★:{rd.one} 2★:{rd.two} 3★:{rd.three} 4★:{rd.four} 5★:{rd.five} (total {rd.total})."
            )
        if ev.top_complaints:
            tc = "; ".join(f"{t.label} ({t.count} mentions, {_f(t.share_pct)}%)" for t in ev.top_complaints)
            lines.append(f"TOP COMPLAINTS: {tc}")
        if ev.top_themes:
            tt = "; ".join(f"{t.label} ({t.count})" for t in ev.top_themes)
            lines.append(f"TOP THEMES: {tt}")
        if ev.reply_rate_pct is not None:
            lines.append(f"REPLY RATE: {_f(ev.reply_rate_pct)}% of {ev.reply_rate_base} reviews the brand replied to.")
        if ev.momentum and ev.momentum.items:
            mv = "; ".join(
                f"{i.label} {i.direction} ({_f(i.earlier_share)}%→{_f(i.recent_share)}%)"
                for i in ev.momentum.items
            )
            lines.append(f"MOMENTUM ({ev.momentum.earlier_label} → {ev.momentum.recent_label}): {mv}")
        if ev.trend and ev.trend.points:
            tp = ", ".join(
                f"{p.label}: {_f(p.negative_pct)}% neg" for p in ev.trend.points if p.negative_pct is not None
            )
            if tp:
                lines.append(f"TREND (negative % by {ev.trend.granularity}): {tp}")
        if ev.rating_sentiment and ev.rating_sentiment.both_count:
            rs = ev.rating_sentiment
            lines.append(
                f"RATING/SENTIMENT MISMATCH: {_f(rs.mismatch_pct)}% ({rs.mismatch_count} of {rs.both_count}); "
                f"{rs.high_rating_negative} rated high but wrote negative."
            )
        if ev.verbatims:
            vb = "\n".join(
                f'- "{v.text}" ({v.platform}, {v.sentiment or "?"}'
                + (f", {v.label}" if v.label else "") + ")"
                for v in ev.verbatims
            )
            lines.append(f"VERBATIMS:\n{vb}")

    if report.top_friction_points:
        fp_lines = []
        for p in report.top_friction_points:
            head = p.theme
            if p.mention_count:
                head += f" ({p.mention_count} mentions, {_f(p.share_pct)}%)"
            detail = f" — {p.description}" if p.description else ""
            evid = ("  Evidence: " + "; ".join(p.supporting_evidence)) if p.supporting_evidence else ""
            fp_lines.append(f"- {head}{detail}{evid}")
        lines.append("FRICTION POINTS:\n" + "\n".join(fp_lines))
    if report.top_strengths:
        st = "; ".join(f"{p.text} ({p.mention_count})" if p.mention_count else p.text for p in report.top_strengths)
        lines.append(f"STRENGTHS: {st}")
    if report.recommendations:
        rc = "\n".join(
            f"- {r.text}" + (f" [addresses {r.addresses}, {r.mention_count} mentions]" if r.mention_count else "")
            for r in report.recommendations
        )
        lines.append(f"RECOMMENDATIONS:\n{rc}")

    if report.channel_breakdown:
        ch_lines = []
        for c in report.channel_breakdown:
            seg = [f"[{c.channel}] {c.summary}"]
            if c.key_stats:
                seg.append("Stats: " + "; ".join(c.key_stats))
            if c.strengths:
                seg.append("Strengths: " + "; ".join(c.strengths))
            if c.friction_points:
                seg.append("Frictions: " + "; ".join(c.friction_points))
            ch_lines.append("\n".join(seg))
        lines.append("CHANNEL BREAKDOWN:\n" + "\n\n".join(ch_lines))

    if report.website_assessment:
        lines.append(f"WEBSITE ASSESSMENT: {report.website_assessment}")
    if report.methodology_note:
        lines.append(f"METHODOLOGY: {report.methodology_note}")

    return "\n\n".join(lines)


def make_report_context_source(
    report: DetailedSocialReport,
    *,
    report_id: str | None = None,
) -> engine.ContextSource:
    """Context source over one report.

    Default: inject the whole report (reliable -- no retrieval miss). Safety valve: if the
    report is pathologically large *and* a ``report_id`` is available to key an index, chunk it
    and RAG over the report instead so the prompt stays bounded.
    """
    context = report_to_context(report)

    if context and len(context) > _MAX_INJECT_CHARS and report_id:
        from app.services.rag.chunker import chunk_markdown

        namespace = f"social:{report_id}"
        if not engine.has_index(namespace):
            chunks = chunk_markdown(context, namespace, source_id="__social_report__", source_name=REPORT_SOURCE)
            engine.build_index(namespace, chunks)
        logger.info("Social report %s is large (%d chars); using RAG over the report.", report_id, len(context))
        return engine.rag_context_source(namespace, k=12, header="Relevant excerpts from the social report:")

    async def _inject(query: str, planned_queries: list[str]) -> tuple[str, list[str]]:
        if not context:
            return "", []
        return f"Full social report:\n\n{context}", [REPORT_SOURCE]

    return _inject


def _default_chat_llm() -> Callable[[str, str], Awaitable[str]]:
    gateway = build_mistral_gateway(get_settings())

    async def _llm(system_prompt: str, user_prompt: str) -> str:
        return await gateway.chat_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )

    return _llm


async def chat_with_report(
    report: DetailedSocialReport,
    query: str,
    *,
    report_id: str | None = None,
    history: list[dict] | None = None,
    llm_fn: Callable[[str, str], Awaitable[str]] | None = None,
) -> dict:
    """Answer a question about a social report via the shared agentic loop (report injection)."""
    llm = llm_fn or _default_chat_llm()
    result = await engine.agentic_answer(
        query,
        llm,
        answer_system_prompt=SOCIAL_CHAT_SYSTEM_PROMPT,
        context_source=make_report_context_source(report, report_id=report_id),
        history=history,
    )
    return {
        "answer": repair_encoding(result["answer"]),
        "sources": list(dict.fromkeys(repair_encoding(s) for s in result["sources"])),
        "used_context": result["used_context"],
    }
