"""Resolve a consultant's artifact selection into source chunks, access-checked.

The selection arrives as ``{kind, ref_id}`` pairs from the UI. Each one is loaded from wherever
that module keeps its output, checked against the caller's permissions, and converted into the
chunks the generator reads. Anything unreadable is reported rather than silently skipped -- a
social report that resolved to nothing once cost a whole module's contribution to the log.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interview_guide import InterviewGuide
from app.services.auth import access
from app.services.issue_log import sources

logger = logging.getLogger(__name__)

SUPPORTED_KINDS = ("desk_session", "social_report", "interview_guide", "assessment")


@dataclass
class Resolution:
    bundle: sources.SourceBundle
    statuses: list[dict]


async def _permitted(db: AsyncSession, user_id: int, kind: str, ref: str,
                     owner_id: int | None) -> bool:
    if owner_id is not None and owner_id == user_id:
        return True
    return await access.can_view_via_project_or_share(db, user_id, kind, ref)


async def _desk(db: AsyncSession, user_id: int, ref: str):
    from app.services.desk_research import session_manager

    info = session_manager.get_session(ref)
    if info is None:
        return None, "not found"
    if not await _permitted(db, user_id, "desk_session", ref, getattr(info, "owner_id", None)):
        return None, "no access"
    chunks = sources.chunks_from_desk(info, ref)
    if not chunks:
        return None, "no report generated yet"
    return chunks, "ok"


async def _social(db: AsyncSession, user_id: int, ref: str):
    """Reports live in ``scraping_jobs.result``; older runs may still be on disk."""
    from app.db.models.scraping_job import ScrapingJob

    safe = os.path.basename(ref)
    job = (await db.execute(
        select(ScrapingJob).where(ScrapingJob.result["report_filename"].astext == safe)
    )).scalars().first()

    if job is not None:
        data, owner_id = job.result or {}, job.owner_id
    else:
        path = os.path.join(os.getenv("SCRAPED_DATA_ROOT", "scraped_data"), safe)
        if not os.path.exists(path):
            return None, "not found"
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        owner_id = data.get("owner_id")

    if not await _permitted(db, user_id, "social_report", safe, owner_id):
        return None, "no access"
    chunks = sources.chunks_from_social(data, safe)
    if not chunks:
        return None, "too little material to analyse"
    return chunks, "ok"


async def _ensure_insights(db: AsyncSession, guide: InterviewGuide, user_id: int) -> str | None:
    """Return the guide's insights, generating and persisting them if they do not exist yet.

    Interviews supplied 51% of the issues in the reference engagement, so a guide with no
    insights is the most expensive thing to skip. Generation needs the assessment the guide was
    built from -- the insights are the analyst's reading of the answers against that assessment.
    The result is written back so the next run, and the interview module's own history view, get
    it for free.
    """
    existing = (guide.insights or {}).get("markdown") if guide.insights else None
    if existing and existing.strip():
        return existing
    if not guide.assessment_id:
        return None

    try:
        from datetime import datetime, timezone

        from app.schemas.interview_guide import InterviewGuideResponse
        from app.services.assessment.interview_insights import generate_insights
        from app.services.assessment.reporting.reporting_service import (
            build_assessment_reporting_service,
        )

        reporting = build_assessment_reporting_service(db)
        trace = await reporting.get_trace(guide.assessment_id)
        if not trace or not getattr(trace, "items", None):
            return None

        payload = dict(guide.payload or {})
        response = InterviewGuideResponse.model_validate({**payload, "id": guide.id})
        markdown = await generate_insights(response, trace.items)
        if not markdown or not markdown.strip():
            return None

        guide.insights = {
            "markdown": markdown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": user_id,
        }
        await db.commit()
        logger.info("issue_log: generated and stored insights for guide %s", guide.id)
        return markdown
    except Exception:
        await db.rollback()
        logger.warning("issue_log: insight generation failed for guide %s", guide.id,
                       exc_info=True)
        return None


async def _interview(db: AsyncSession, user_id: int, ref: str):
    guide = await db.get(InterviewGuide, int(ref))
    if guide is None:
        return None, "not found"
    if not await _permitted(db, user_id, "interview_guide", ref, guide.owner_id):
        return None, "no access"

    insights = await _ensure_insights(db, guide, user_id)
    findings = list(guide.cx_findings or []) if guide.cx_findings is not None else None

    chunks = sources.chunks_from_interview(
        insights, findings, ref,
        label=f"{guide.company_name or 'Interview'} — {guide.profile or 'stakeholder'}",
        client=guide.company_name,
        payload=dict(guide.payload or {}))
    if not chunks:
        if not guide.assessment_id:
            return None, "guide has no source assessment, so insights cannot be generated"
        return None, "insights could not be generated for this guide"
    return chunks, "ok"


async def _assessment(db: AsyncSession, user_id: int, ref: str):
    from app.services.assessment.reporting.reporting_service import (
        build_assessment_reporting_service,
    )

    reporting = build_assessment_reporting_service(db)
    trace = await reporting.get_trace(int(ref))
    if trace is None or not getattr(trace, "items", None):
        return None, "no scored capabilities"

    # Field names come from AssessmentTraceItem: axis, capability_code, maturity_level_id,
    # question, answer, justification, recommendation_guideline, priority_hint.
    rows = []
    for item in trace.items:
        rows.append({
            "axis": getattr(item, "axis", None),
            "capability": getattr(item, "capability_code", None),
            "level": getattr(item, "maturity_level_id", None),
            "question": getattr(item, "question", None) or "",
            "answer": getattr(item, "answer", None) or "",
            "justification": getattr(item, "justification", None) or "",
            "recommendation": getattr(item, "recommendation_guideline", None) or "",
            "priority_hint": getattr(item, "priority_hint", None) or "",
        })
    chunks = sources.chunks_from_assessment(rows, ref, label=f"CX maturity assessment {ref}")
    if not chunks:
        return None, "too little material to analyse"
    return chunks, "ok"


_RESOLVERS = {
    "desk_session": _desk,
    "social_report": _social,
    "interview_guide": _interview,
    "assessment": _assessment,
}


async def resolve_selections(db: AsyncSession, user_id: int,
                             selections: list[dict]) -> Resolution:
    bundle = sources.SourceBundle()
    statuses: list[dict] = []

    for selection in selections:
        kind = str(selection.get("kind") or "")
        ref = str(selection.get("ref_id") or "")
        resolver = _RESOLVERS.get(kind)
        if resolver is None:
            statuses.append({"kind": kind, "ref_id": ref, "status": "unsupported", "chunks": 0})
            continue
        try:
            chunks, status = await resolver(db, user_id, ref)
        except Exception:
            logger.exception("issue_log: failed to resolve %s/%s", kind, ref)
            chunks, status = None, "error"

        if chunks:
            bundle.chunks.extend(chunks)
            statuses.append({"kind": kind, "ref_id": ref, "status": "ok",
                             "client": chunks[0].client, "chunks": len(chunks),
                             "tokens": sum(c.tokens for c in chunks)})
        else:
            bundle.skipped.append({"kind": kind, "ref_id": ref, "reason": status})
            statuses.append({"kind": kind, "ref_id": ref, "status": status, "chunks": 0})

    return Resolution(bundle=bundle, statuses=statuses)
