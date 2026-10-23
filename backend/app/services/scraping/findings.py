"""Extract structured issue-log findings from a social-listening report.

Deterministic: the social report is ALREADY structured (friction points, strengths, and computed
complaint/theme analytics), so findings come straight from those fields -- no LLM, no prose
parsing. Emits the shared Finding shape (see app/services/cx_findings.py)."""

from __future__ import annotations

from typing import Any

from app.services.cx_findings import finding, severity_from, to_cx_dimension


def _evidence(mention_count: Any, share_pct: Any, ev_list: list) -> str:
    parts: list[str] = []
    if mention_count:
        parts.append(f"{int(mention_count)} mentions")
    if share_pct:
        s = float(share_pct)
        parts.append(f"{s:.0f}% of negative reviews" if s > 1 else f"{s * 100:.0f}% of mentions")
    if ev_list:
        parts.append('"' + str(ev_list[0]).replace("\n", " ")[:140] + '"')
    return " · ".join(parts) or "Recurring in social feedback"


def extract_social_findings(report: Any, source_label: str = "Social listening") -> list[dict]:
    """Map a DetailedSocialReport's friction points + strengths onto CX Findings for the issue log."""
    out: list[dict] = []

    def _emit(item: Any, ftype: str, sev_from_metrics: bool) -> None:
        theme = (getattr(item, "theme", "") or "").strip()
        desc = (getattr(item, "description", "") or "").strip()
        if not theme and not desc:
            return
        mc = getattr(item, "mention_count", None)
        sp = getattr(item, "share_pct", None)
        ev = _evidence(mc, sp, getattr(item, "supporting_evidence", None) or [])
        out.append(finding(
            dimension=to_cx_dimension(f"{theme} {desc}"),
            type=ftype,
            severity=severity_from(sp, mc) if sev_from_metrics else None,
            title=theme or desc[:80],
            description=desc,
            evidence=ev,
            source_document=source_label,
        ))

    for fp in getattr(report, "top_friction_points", None) or []:
        _emit(fp, "friction", sev_from_metrics=True)
    for st in getattr(report, "top_strengths", None) or []:
        _emit(st, "strength", sev_from_metrics=False)

    ev = getattr(report, "evidence", None)
    if ev is not None:
        # Momentum: complaint categories whose share is RISING = emerging friction / worsening trend.
        mom = getattr(ev, "momentum", None)
        for it in (getattr(mom, "items", None) or []) if mom else []:
            if getattr(it, "direction", "") != "rising":
                continue
            label = getattr(it, "label", "") or ""
            delta = getattr(it, "delta", 0)
            recent = getattr(it, "recent_share", 0)
            out.append(finding(
                dimension=to_cx_dimension(label),
                type="friction",
                severity=severity_from(recent, getattr(it, "recent_count", None)),
                title=f"Rising complaints: {label}",
                description=(f"Share of feedback about {label} rose from {getattr(it,'earlier_share',0)}% "
                             f"to {recent}% (+{delta} pts) between {getattr(mom,'earlier_label','')} and "
                             f"{getattr(mom,'recent_label','')}."),
                evidence=f"{getattr(it,'earlier_count',0)} → {getattr(it,'recent_count',0)} mentions (+{delta} pts share)",
                source_document=source_label,
            ))

        # Area of conflict: star ratings and written sentiment disagree.
        rsc = getattr(ev, "rating_sentiment", None)
        if rsc is not None and getattr(rsc, "mismatch_count", 0):
            out.append(finding(
                dimension="Customer Experience",
                type="conflict",
                severity="medium",
                title="Star ratings and written sentiment disagree",
                description=(f"{getattr(rsc,'mismatch_pct',0)}% of rated reviews carry a star rating that "
                             "contradicts their written sentiment -- a sign the score alone is misleading."),
                evidence=(f"{getattr(rsc,'mismatch_count',0)} of {getattr(rsc,'both_count',0)} rated reviews "
                          f"conflict ({getattr(rsc,'high_rating_negative',0)} high-star-but-negative, "
                          f"{getattr(rsc,'low_rating_positive',0)} low-star-but-positive)"),
                source_document=source_label,
            ))
    return out


def extract_social_kpis(report: Any) -> dict:
    """Headline metrics for the source's context block (NOT issue-log rows): sentiment split,
    ratings, reply rate, volume, and the worst-performing channel."""
    ev = getattr(report, "evidence", None)
    kpis: dict = {}

    os_ = getattr(report, "overall_sentiment", None) or (getattr(ev, "overall_sentiment", None) if ev else None)
    if os_ is not None:
        kpis["sentiment"] = {
            "positive_pct": getattr(os_, "positive_pct", None),
            "neutral_pct": getattr(os_, "neutral_pct", None),
            "negative_pct": getattr(os_, "negative_pct", None),
            "classified": getattr(os_, "classified_count", None),
        }
    if ev is not None:
        rd = getattr(ev, "rating_distribution", None)
        if rd is not None:
            kpis["rating"] = {"average": getattr(rd, "average", None), "total": getattr(rd, "total", None),
                              "stars": {str(i): getattr(rd, n, None) for i, n in
                                        enumerate(("one", "two", "three", "four", "five"), 1)}}
        kpis["reviews_collected"] = getattr(ev, "reviews_collected", None)
        kpis["reviews_classified"] = getattr(ev, "reviews_classified", None)
        rr = getattr(ev, "reply_rate_pct", None)
        if rr is not None:
            kpis["reply_rate_pct"] = rr
            kpis["reply_rate_base"] = getattr(ev, "reply_rate_base", None)
        ps = getattr(ev, "platform_sentiment", None) or []  # sorted worst-first in analytics
        if ps:
            kpis["worst_channel"] = {"platform": getattr(ps[0], "platform", None),
                                     "negative_pct": getattr(ps[0], "negative_pct", None)}
    return kpis
