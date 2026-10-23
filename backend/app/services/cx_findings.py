"""Shared CX **Finding** contract for the consolidated issue log.

Every module (desk research, social listening, interviews, assessment) maps its output onto this
one structured shape, so the issue log can aggregate them uniformly -- no prose re-parsing, no
Excel-as-transport. A Finding is a plain dict:

    {
        "dimension":       one of CX_DIMENSIONS,
        "type":            "friction" | "strength" | "gap" | "opportunity",
        "severity":        "low" | "medium" | "high" | "critical" | None,
        "title":           short label,
        "description":     one sentence: the finding + its implication,
        "evidence":        the metric / verbatim behind it,
        "source_document": human label of the origin (a document title, a channel, "Social listening"),
    }

The consolidator adds ``source_kind`` (desk_research / social / interview / assessment) and
``source_ref`` (the artifact id) when it collects these into the issue log.
"""

from __future__ import annotations

CX_DIMENSIONS = [
    "Customer Experience",
    "Product",
    "Marketing & Communication",
    "Customer Service",
    "HR",
    "Digital Experience",
]

# First keyword group that matches wins; otherwise "Customer Experience". Order matters.
_KEYWORD_DIM: list[tuple[tuple[str, ...], str]] = [
    (("network", "outage", "coverage", "signal", "connection", "internet", "speed",
      "4g", "5g", "reliab", "downtime"), "Digital Experience"),
    (("app", "application", "website", "site", "portal", "self-service", "self service",
      "ui", "ux", "login", "online", "digital"), "Digital Experience"),
    (("bill", "billing", "price", "pricing", "charge", "fee", "cost", "refund", "payment",
      "tariff", "expensive", "offer", "bundle", "package", "plan", "product"), "Product"),
    (("training", "turnover", "hiring", "staffing", "employee", "workforce", "agent shortage"), "HR"),
    # Customer Service before Marketing so operational themes (delivery/stock/wait) win over the
    # generic "communication" keyword when a theme mentions both.
    (("staff", "agent", "support", "service", "response", "reply", "wait", "queue",
      "call center", "call centre", "rude", "helpline", "hotline", "resolution", "complaint",
      "delivery", "shipping", "store", "branch", "shop", "access", "availability", "stock",
      "admin", "sav", "after-sales"), "Customer Service"),
    (("promo", "campaign", "communication", "information", "awareness", "advert", "marketing",
      "announce", "notif"), "Marketing & Communication"),
]


def to_cx_dimension(text: str | None) -> str:
    """Best-effort map of a free-text theme onto a CX dimension (heuristic; tune the map above)."""
    t = (text or "").lower()
    for keywords, dim in _KEYWORD_DIM:
        if any(k in t for k in keywords):
            return dim
    return "Customer Experience"


def severity_from(share_pct: float | None, mention_count: int | None) -> str:
    """Severity from how widespread an issue is (share of mentions and/or raw volume)."""
    s = float(share_pct or 0.0)
    if 0 < s <= 1:  # a fraction (0.28) -> percentage (28)
        s *= 100
    n = int(mention_count or 0)
    if s >= 40 or n >= 50:
        return "critical"
    if s >= 20 or n >= 20:
        return "high"
    if s >= 8 or n >= 8:
        return "medium"
    return "low"


_VALID_TYPES = {"friction", "strength", "gap", "opportunity", "conflict"}
_VALID_SEV = {"low", "medium", "high", "critical"}


def finding(*, dimension, type, severity, title, description, evidence, source_document) -> dict:
    """Build one normalised Finding dict (validates the enums, trims the label)."""
    return {
        "dimension": dimension if dimension in CX_DIMENSIONS else "Customer Experience",
        "type": type if type in _VALID_TYPES else "friction",
        "severity": severity if severity in _VALID_SEV else None,
        "title": (title or "").strip()[:120],
        "description": (description or "").strip(),
        "evidence": (evidence or "").strip(),
        "source_document": (source_document or "").strip(),
    }
