"""Issue-log findings collector.

Given selected inputs (a project's attached artifacts, or hand-picked ones), resolve each source to
unified structured findings on the shared Finding shape (app/services/cx_findings.py), stamping
``source_kind`` and ``source_ref`` so every issue-log row traces back to its origin.

- Social      → deterministic, from the saved report (extract_social_findings + KPIs).
- Desk        → the persisted session.cx_findings.
- Interview   → the LLM insights (generated on the fly if missing) + answer notes.
- Assessment  → per-capability gaps (basic; expand later).

Each source is access-checked (owner, or shared / in the caller's project) before it is read.
"""

from __future__ import annotations

import json
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interview_guide import InterviewGuide
from app.services.auth import access

logger = logging.getLogger(__name__)

# artifact kind -> issue-log source_kind
_SOURCE_KIND = {
    "desk_session": "desk_research",
    "social_report": "social",
    "interview_guide": "interview",
    "assessment": "assessment",
}


async def _can_access(db: AsyncSession, user_id: int, kind: str, ref: str, owner_id: int | None) -> bool:
    if owner_id is not None and owner_id == user_id:
        return True
    return await access.can_view_via_project_or_share(db, user_id, kind, ref)


async def _desk(db, user_id, ref):
    from app.services.desk_research import session_manager
    info = session_manager.get_session(ref)
    if info is None:
        return None
    if not await _can_access(db, user_id, "desk_session", ref, getattr(info, "owner_id", None)):
        return None
    return list(info.cx_findings or []), {}, info.title or "Desk research"


async def _social(db, user_id, ref):
    """Resolve a social report to findings.

    The report lives in ``scraping_jobs.result`` (JSONB) -- that is the single source of truth,
    addressed by the ``report_filename`` carried inside it. Older runs, made before the move off
    disk, are still read from ``scraped_data/`` as a fallback so historical reports keep working.
    """
    from sqlalchemy import select

    from app.db.models.scraping_job import ScrapingJob
    from app.schemas.scraping import DetailedSocialReport
    from app.services.scraping.findings import extract_social_findings, extract_social_kpis

    safe = os.path.basename(ref)

    # ── Primary source: the job row ──────────────────────────────────────────
    job = (await db.execute(
        select(ScrapingJob).where(ScrapingJob.result["report_filename"].astext == safe)
    )).scalars().first()

    if job is not None:
        data = job.result or {}
        owner_id = job.owner_id
    else:
        # ── Fallback: a legacy report still on disk ──────────────────────────
        path = os.path.join(os.getenv("SCRAPED_DATA_ROOT", "scraped_data"), safe)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        owner_id = data.get("owner_id")

    if not await _can_access(db, user_id, "social_report", safe, owner_id):
        return None

    det = data.get("detailed_report")
    brand = data.get("brand_name", "Social listening")
    if not det:
        return [], {}, brand
    report = DetailedSocialReport.model_validate(det)
    return extract_social_findings(report, source_label=brand), extract_social_kpis(report), brand


async def _interview(db, user_id, ref):
    from app.services.assessment.interview_findings import extract_interview_findings
    guide = await db.get(InterviewGuide, int(ref))
    if guide is None:
        return None
    if not await _can_access(db, user_id, "interview_guide", ref, guide.owner_id):
        return None
    label = guide.company_name or "Stakeholder interview"

    # Fast path: findings already computed (by the interview module's insights button, or a prior
    # collect) and persisted. NULL = never computed; [] = computed-but-empty (both are truthy-safe
    # to reuse). This is the whole point — the Issue Log spends no interview tokens when warm.
    if guide.cx_findings is not None:
        return list(guide.cx_findings), {}, label

    payload = dict(guide.payload or {})
    insights_md = (guide.insights or {}).get("markdown") if guide.insights else None

    # Generate insights on the fly if missing and the guide came from an assessment.
    if not insights_md and guide.assessment_id:
        try:
            from app.schemas.interview_guide import InterviewGuideResponse
            from app.services.assessment.interview_insights import generate_insights
            from app.services.assessment.reporting.reporting_service import build_assessment_reporting_service
            reporting = build_assessment_reporting_service(db)
            trace = await reporting.get_trace(guide.assessment_id)
            if trace and getattr(trace, "items", None):
                gr = InterviewGuideResponse.model_validate({**payload, "id": guide.id})
                insights_md = await generate_insights(gr, trace.items)
                if insights_md:
                    # Persist so history shows it and it never regenerates on the next collect.
                    from datetime import datetime, timezone
                    guide.insights = {
                        "markdown": insights_md,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "generated_by": user_id,
                    }
        except Exception:
            logger.warning("interview insights generation failed for guide %s", ref, exc_info=True)

    findings = await extract_interview_findings(payload, insights_md)
    # Cache the findings (and any freshly-made insights) so the next collect is token-free.
    try:
        guide.cx_findings = findings
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("interview findings cache write failed for guide %s", ref, exc_info=True)
    return findings, {}, label


_RESOLVERS = {"desk_session": _desk, "social_report": _social, "interview_guide": _interview}


async def collect_findings(db: AsyncSession, user_id: int, selections: list[dict]) -> dict:
    """Resolve each {kind, ref_id} selection to findings; returns findings + per-source KPIs + a
    progress summary. Inaccessible or unresolvable selections are skipped (reported in `sources`)."""
    all_findings: list[dict] = []
    kpis_by_source: dict[str, dict] = {}
    sources: list[dict] = []

    for sel in selections:
        kind = sel.get("kind")
        ref = str(sel.get("ref_id"))
        resolver = _RESOLVERS.get(kind)
        status = "ok"
        findings: list[dict] = []
        kpis: dict = {}
        label = ref
        if resolver is None:
            status = "unsupported"
        else:
            try:
                result = await resolver(db, user_id, ref)
            except Exception:
                logger.exception("collect: failed to resolve %s/%s", kind, ref)
                result = None
                status = "error"
            if result is None:
                status = "denied_or_missing" if status == "ok" else status
            else:
                findings, kpis, label = result

        source_kind = _SOURCE_KIND.get(kind, kind)
        for f in findings:
            f["source_kind"] = source_kind
            f["source_ref"] = ref
        all_findings.extend(findings)
        if kpis:
            kpis_by_source[f"{source_kind}:{ref}"] = kpis
        sources.append({
            "kind": kind, "source_kind": source_kind, "ref_id": ref,
            "label": label, "findings": len(findings), "status": status,
        })

    return {
        "findings": all_findings,
        "kpis": kpis_by_source,
        "sources": sources,
        "total": len(all_findings),
    }
