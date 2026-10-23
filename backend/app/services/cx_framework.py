"""The EY CX capability framework (3 axes / 9 capabilities), loaded once from the DB and cached.

This is the SAME framework the maturity assessment scores against and the interview guide is built
around (the ``axes`` + ``capabilities`` tables — Manage / Analyze / Improve). Mapping desk-research
and interview findings onto it means the consolidated issue log speaks one taxonomy across modules,
the same one the assessment scores.

Reference data that changes rarely, so it's cached for the process lifetime. Loaded via a short
sync connection so it works from anywhere (the desk synthesizer has no async session). A hardcoded
fallback keeps the mapping usable even if the read fails.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class _Axis:
    __slots__ = ("name", "description", "capabilities")

    def __init__(self, name: str, description: str, capabilities: list[tuple[str, str]]):
        self.name = name
        self.description = description
        self.capabilities = capabilities  # [(code, name), ...]


# Canonical axis descriptions (mirrors the seeded ``axes`` rows); used only if the DB read fails.
_FALLBACK: list[_Axis] = [
    _Axis("Manage",
          "The organizational mechanisms that make customer experience accountable: leadership "
          "attention, ownership, governance routines, decision rights, culture, and how customer "
          "impact is reinforced in everyday management.",
          [("manage_cx_culture", "CX culture"),
           ("manage_ownership_governance", "Ownership and governance"),
           ("manage_decision_making", "Decision-making")]),
    _Axis("Analyze",
          "How the organization listens to customers and turns feedback into usable understanding: "
          "feedback capture, journey visibility, cross-channel consistency, pattern recognition, "
          "root-cause analysis, and prioritization of customer issues.",
          [("analyze_feedback_collection", "Feedback collection"),
           ("analyze_use_of_insights", "Use of insights"),
           ("analyze_channel_consistency", "Channel consistency"),
           ("analyze_journey_visibility", "Journey visibility")]),
    _Axis("Improve",
          "How the organization acts on customer pain points and measures improvement over time: "
          "execution discipline, action ownership, metric review, follow-through, validation of "
          "fixes, and continuous improvement loops.",
          [("improve_measurement_continuous_improvement", "Measurement and continuous improvement"),
           ("improve_acting_on_pain_points", "Acting on pain points")]),
]

_framework: list[_Axis] | None = None


def _load_from_db() -> list[_Axis] | None:
    try:
        url = get_settings().database_url.replace("+asyncpg", "")  # async URL -> sync psycopg2
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            axes = conn.execute(text(
                "SELECT id, name, description FROM axes ORDER BY sort_order"
            )).fetchall()
            caps = conn.execute(text(
                "SELECT axis_id, code, name FROM capabilities ORDER BY sort_order"
            )).fetchall()
        engine.dispose()
        if not axes or not caps:
            return None
        by_axis: dict[int, list[tuple[str, str]]] = {}
        for axis_id, code, name in caps:
            by_axis.setdefault(axis_id, []).append((code, name))
        return [_Axis(name, " ".join((description or "").split()), by_axis.get(axis_id, []))
                for axis_id, name, description in axes]
    except Exception:
        logger.warning("cx_framework: DB load failed, using fallback", exc_info=True)
        return None


def get_framework() -> list[_Axis]:
    """The axes (name + description) + their capabilities, ordered. Cached for the process life."""
    global _framework
    if _framework is None:
        _framework = _load_from_db() or _FALLBACK
    return _framework


def axis_order() -> list[str]:
    return [a.name for a in get_framework()]


def _by_code() -> dict[str, tuple[str, str]]:
    """capability_code -> (capability_name, axis_name)."""
    return {code: (name, a.name) for a in get_framework() for code, name in a.capabilities}


def _by_name() -> dict[str, tuple[str, str]]:
    """lowercased capability_name -> (capability_name, axis_name)."""
    return {name.lower(): (name, a.name) for a in get_framework() for _, name in a.capabilities}


def resolve_capability(value: str | None) -> tuple[str | None, str | None]:
    """Map an LLM-provided capability code OR name to (capability_name, axis_name).
    Returns (None, None) for the escape hatch ('', 'none', 'general', or anything unrecognised)."""
    v = (value or "").strip()
    if not v or v.lower() in {"none", "n/a", "general", "other"}:
        return None, None
    hit = _by_code().get(v) or _by_name().get(v.lower())
    return hit if hit else (None, None)


def framework_card() -> str:
    """Compact framework text for a mapping prompt: each axis, what it means, and its capabilities."""
    lines: list[str] = []
    for a in get_framework():
        lines.append(f"{a.name} — {a.description}")
        for code, name in a.capabilities:
            lines.append(f"  - [{code}] {name}")
        lines.append("")
    return "\n".join(lines).strip()
