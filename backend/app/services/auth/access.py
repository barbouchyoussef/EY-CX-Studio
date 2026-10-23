"""Authorization core -- the single place "can this user see/touch X" is decided.

Deny-by-default: routes call these helpers and 403 on a False. Access to an analysis is:
  owner (owner_id == user, checked per-table by the route)
  OR member of a project it's attached to
  OR it was explicitly shared with the user.
"""

from __future__ import annotations

import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment import Assessment
from app.db.models.interview_guide import InterviewGuide
from app.db.models.project import ProjectArtifact, ProjectMember
from app.db.models.scraping_job import ScrapingJob
from app.db.models.share import AnalysisShare


def _file_owner_id(kind: str, ref_id: str) -> int | None:
    """Legacy on-disk lookup, kept only as a fallback for records written before the move to
    object storage. basename guards against path traversal."""
    safe = os.path.basename(str(ref_id))
    if kind == "social_report":
        path = os.path.join(os.getenv("SCRAPED_DATA_ROOT", "scraped_data"), safe)
    elif kind == "desk_session":
        path = os.path.join(os.getenv("DESK_RESEARCH_DATA_ROOT", "desk_research_data"), safe, "session.json")
    else:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("owner_id")
    except Exception:
        return None


def _desk_session_owner_id(ref_id: str) -> int | None:
    """Owner of a desk-research session, read through the storage adapter.

    Sessions are written via ``app.services.storage`` so they survive on an ephemeral host, which
    means the backend may be object storage rather than local disk. Reading the file directly only
    works with the disk backend; going through the adapter works with either. Falls back to a
    direct read for anything written before the move.
    """
    from app.services import storage

    safe = os.path.basename(str(ref_id))
    try:
        raw = storage.get_text(f"desk_research_data/{safe}/session.json")
        return json.loads(raw).get("owner_id")
    except Exception:
        return _file_owner_id("desk_session", safe)


async def _social_report_owner_id(db: AsyncSession, ref_id: str) -> int | None:
    """Owner of a social report, read from the job row that holds it.

    Reports live in ``scraping_jobs.result`` (JSONB), addressed by the ``report_filename`` inside
    it. Falls back to the legacy on-disk copy for reports produced before that move.
    """
    safe = os.path.basename(str(ref_id))
    row = (await db.execute(
        select(ScrapingJob.owner_id).where(ScrapingJob.result["report_filename"].astext == safe)
    )).scalars().first()
    if row is not None:
        return row
    return _file_owner_id("social_report", safe)


async def owns_analysis(db: AsyncSession, user_id: int, kind: str, ref_id: str) -> bool:
    """True if the user owns this analysis, across both DB-backed and file-backed kinds."""
    if kind == "assessment":
        try:
            row = await db.get(Assessment, int(ref_id))
        except (TypeError, ValueError):
            return False
        return row is not None and row.owner_id == user_id
    if kind == "interview_guide":
        try:
            row = await db.get(InterviewGuide, int(ref_id))
        except (TypeError, ValueError):
            return False
        return row is not None and row.owner_id == user_id
    if kind == "social_report":
        return await _social_report_owner_id(db, ref_id) == user_id
    if kind == "desk_session":
        return _desk_session_owner_id(ref_id) == user_id
    if kind == "issue_log":
        from app.db.models.issue_log import IssueLog

        try:
            row = await db.get(IssueLog, int(ref_id))
        except (TypeError, ValueError):
            return False
        return row is not None and row.owner_id == user_id
    return False


async def get_project_role(db: AsyncSession, user_id: int, project_id: int) -> str | None:
    """'owner' | 'collaborator' | None."""
    row = await db.get(ProjectMember, (project_id, user_id))
    return row.role if row else None


async def visible_project_ids(db: AsyncSession, user_id: int) -> set[int]:
    rows = await db.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    )
    return set(rows.scalars())


async def _shared_with(db: AsyncSession, user_id: int, kind: str, ref_id: str) -> bool:
    row = await db.execute(
        select(AnalysisShare.id)
        .where(
            AnalysisShare.kind == kind,
            AnalysisShare.ref_id == str(ref_id),
            AnalysisShare.shared_with == user_id,
        )
        .limit(1)
    )
    return row.first() is not None


async def can_view_via_project_or_share(
    db: AsyncSession, user_id: int, kind: str, ref_id: str
) -> bool:
    """True if the analysis is attached to a project the user belongs to, or shared with them.
    (Ownership via owner_id is a separate, per-table check the caller does first.)"""
    if await _shared_with(db, user_id, kind, str(ref_id)):
        return True
    pids = await visible_project_ids(db, user_id)
    if not pids:
        return False
    row = await db.execute(
        select(ProjectArtifact.id)
        .where(
            ProjectArtifact.kind == kind,
            ProjectArtifact.ref_id == str(ref_id),
            ProjectArtifact.project_id.in_(pids),
        )
        .limit(1)
    )
    return row.first() is not None


async def visible_refs(db: AsyncSession, user_id: int, kind: str) -> set[str]:
    """All ref_ids of `kind` the user can see via project membership or a share. The caller
    unions this with the ids they own (owner_id == user) to scope a list endpoint."""
    refs: set[str] = set()
    rows = await db.execute(
        select(AnalysisShare.ref_id).where(
            AnalysisShare.kind == kind, AnalysisShare.shared_with == user_id
        )
    )
    refs |= set(rows.scalars())
    pids = await visible_project_ids(db, user_id)
    if pids:
        rows = await db.execute(
            select(ProjectArtifact.ref_id).where(
                ProjectArtifact.kind == kind, ProjectArtifact.project_id.in_(pids)
            )
        )
        refs |= set(rows.scalars())
    return refs
