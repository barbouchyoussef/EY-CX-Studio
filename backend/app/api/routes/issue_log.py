"""Issue Log API: preview sources, generate a log, recommend, save, export.

Flow the UI drives:
    POST /issue-log/preview      what will be analysed, and what could not be read
    POST /issue-log/generate     start a run; returns 202 and a job id immediately
    GET  /issue-log/{id}/status  poll it; carries the result once finished
    GET  /issue-log/{id}/export.xlsx   download the workbook

Generation is a background job because a real engagement takes minutes -- see
``services/issue_log/job_service.py``. Closing the browser cancels nothing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_log import IssueLog
from app.db.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.services.auth import access
from app.services.issue_log import export, job_service, pipeline, resolve, taxonomy, verify
from app.services.issue_log.collector import collect_findings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issue-log", dependencies=[Depends(get_current_user)])

MAX_SELECTIONS = 40


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(description="desk_session | social_report | interview_guide | assessment")
    ref_id: str


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[Selection] = Field(default_factory=list, max_length=MAX_SELECTIONS)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="Issue Log", max_length=255)
    project_id: int | None = None
    selections: list[Selection] = Field(default_factory=list, max_length=MAX_SELECTIONS)
    focus: str | None = Field(default=None, max_length=2000)
    sweep: bool = True
    correlate: bool = True
    recommendations: bool = True
    max_issues: int = Field(default=200, ge=10, le=400)


class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=255)


class IssueEdit(BaseModel):
    """Consultant corrections to one generated row.

    Only the fields a reviewer should be able to change. Provenance -- inspection_point,
    evidence, source_kind, the verification verdict -- is deliberately NOT editable: those record
    where the issue came from and whether the quote was found in the source, and a log where the
    author can rewrite its own audit trail is worth nothing.
    """
    model_config = ConfigDict(extra="forbid")
    finding: str | None = Field(default=None, max_length=300)
    investigation: str | None = Field(default=None, max_length=4000)
    strategic_dimension: str | None = Field(default=None, max_length=80)
    sub_category: str | None = Field(default=None, max_length=80)
    severity: str | None = Field(default=None, max_length=20)
    severity_reason: str | None = Field(default=None, max_length=600)
    channel: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=1000)


async def _readable(db: AsyncSession, log_id: int, user: User) -> IssueLog:
    """Owner, or someone it was shared with / a member of its project."""
    row = await db.get(IssueLog, log_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Issue log not found")
    if row.owner_id == user.id:
        return row
    if await access.can_view_via_project_or_share(db, user.id, "issue_log", str(log_id)):
        return row
    raise HTTPException(status_code=404, detail="Issue log not found")  # 404: don't confirm it exists


async def _owned(db: AsyncSession, log_id: int, user: User) -> IssueLog:
    """Owner only. Editing, deleting and renaming stay with whoever generated the log."""
    row = await db.get(IssueLog, log_id)
    if row is None or row.owner_id != user.id:   # 404, not 403 — don't confirm existence
        raise HTTPException(status_code=404, detail="Issue log not found")
    return row


@router.post("/preview")
async def preview(body: PreviewRequest, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)) -> dict:
    """What the run will actually read: chunk counts and sizes per selection, plus the reason
    anything was skipped. Cheap — no LLM calls."""
    resolution = await resolve.resolve_selections(db, user.id,
                                                  [s.model_dump() for s in body.selections])
    bundle = resolution.bundle
    return {
        "chunks": len(bundle.chunks),
        "tokens": bundle.tokens,
        "clients": {k: len(v) for k, v in bundle.by_client().items()},
        "sources": resolution.statuses,
        "skipped": bundle.skipped,
    }


@router.post("/generate", status_code=202)
async def generate(body: GenerateRequest, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)) -> dict:
    """Start a run and return immediately.

    Reading each source separately is what makes the log good, and it is also what makes it
    slow -- minutes, not seconds. The row is persisted as `pending` before the task starts, so
    the consultant sees it in their dashboard straight away and can close the tab.
    """
    if not body.selections:
        raise HTTPException(status_code=400, detail="Select at least one analysis.")

    row = await job_service.create_job(
        db, name=body.name, owner_id=user.id, project_id=body.project_id,
        selections=[s.model_dump() for s in body.selections],
        focus=body.focus, sweep=body.sweep, correlate=body.correlate,
        recommendations=body.recommendations, max_issues=body.max_issues)

    job_service.start_job(row.id, user.id)
    return job_service.to_status(row)


@router.get("/{log_id}/status")
async def job_status(log_id: int, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)) -> dict:
    """Poll a run. Issues and recommendations are included once it has finished."""
    row = await _readable(db, log_id, user)
    return job_service.to_status(row)


@router.get("")
async def list_issue_logs(user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)) -> list[dict]:
    shared = await access.visible_refs(db, user.id, "issue_log")
    shared_ids = {int(x) for x in shared if str(x).isdigit()}
    rows = (await db.execute(
        select(IssueLog)
        .where(or_(IssueLog.owner_id == user.id, IssueLog.id.in_(shared_ids or {-1})))
        .order_by(IssueLog.updated_at.desc())
    )).scalars().all()
    return [{
        "id": r.id, "name": r.name, "project_id": r.project_id,
        "owned": r.owner_id == user.id,
        "status": r.status, "progress": r.progress, "error": r.error,
        "findings_count": len(r.findings or []),
        "recommendations_count": len(r.recommendations or []),
        "created_at": r.created_at.isoformat(),
    } for r in rows]


@router.patch("/{log_id}")
async def rename_issue_log(log_id: int, body: RenameRequest,
                           user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> dict:
    """Rename a log. There is no separate save step -- the job persists its own result."""
    row = await _owned(db, log_id, user)
    row.name = (body.name or "").strip() or row.name
    await db.commit()
    return {"id": row.id, "name": row.name}


@router.get("/{log_id}")
async def get_issue_log(log_id: int, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)) -> dict:
    row = await _readable(db, log_id, user)
    return {
        "id": row.id, "name": row.name, "project_id": row.project_id,
        "status": row.status, "progress": row.progress, "error": row.error,
        "findings": row.findings or [],
        "recommendations": row.recommendations or [],
        "run": row.run or {}, "conflicts": (row.run or {}).get("conflicts") or [],
        "sources": row.sources or [],
        "created_at": row.created_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.get("/{log_id}/export.xlsx")
async def export_issue_log(log_id: int, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> Response:
    """The workbook: Issue List, Recommendations, Summary, Category Definitions."""
    row = await _readable(db, log_id, user)
    if row.status != "completed":
        raise HTTPException(status_code=409,
                            detail=f"This issue log is {row.status}; nothing to export yet.")
    run = row.run or {}
    workbook = export.build_workbook(
        row.findings or [], row.recommendations or [], run=run or None, title=row.name,
        conflicts=run.get("conflicts") or [])
    safe = "".join(c for c in (row.name or "issue-log") if c.isalnum() or c in " -_").strip()
    return Response(
        content=workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe or "issue-log"}.xlsx"'},
    )


@router.patch("/{log_id}/issues/{issue_no}")
async def edit_issue(log_id: int, issue_no: str, body: IssueEdit,
                     user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)) -> dict:
    """Correct one row. The generator is a first draft; the consultant owns the final text."""
    row = await _owned(db, log_id, user)
    findings = list(row.findings or [])
    target = next((i for i in findings if str(i.get("issue_no")) == issue_no), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Issue not found in this log")

    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to change.")

    if "severity" in changes:
        severity = str(changes["severity"]).strip().lower()
        if severity not in pipeline.SEVERITIES:
            raise HTTPException(status_code=400,
                                detail=f"severity must be one of {', '.join(pipeline.SEVERITIES)}")
        changes["severity"] = severity

    if "strategic_dimension" in changes or "sub_category" in changes:
        dimension, sub = taxonomy.resolve(
            changes.get("strategic_dimension", target.get("strategic_dimension")),
            changes.get("sub_category", target.get("sub_category")))
        if dimension is None:
            raise HTTPException(status_code=400, detail="Unrecognised strategic dimension.")
        changes["strategic_dimension"], changes["sub_category"] = dimension, sub

    for key, value in changes.items():
        target[key] = value.strip() if isinstance(value, str) else value
    # An edited row is no longer the model's wording, and its shape flag would be stale.
    target["edited"] = True
    target["sentence_shaped"] = verify.is_sentence_shaped(str(target.get("finding") or ""))

    row.findings = findings          # JSONB is only persisted on reassignment
    await db.commit()
    return target


@router.delete("/{log_id}/issues/{issue_no}", status_code=200)
async def delete_issue(log_id: int, issue_no: str,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> dict:
    """Remove one row and renumber the rest, so Issue # stays contiguous for the client."""
    row = await _owned(db, log_id, user)
    findings = list(row.findings or [])
    remaining = [i for i in findings if str(i.get("issue_no")) != issue_no]
    if len(remaining) == len(findings):
        raise HTTPException(status_code=404, detail="Issue not found in this log")

    renumbered = {}
    for n, issue in enumerate(remaining, 1):
        renumbered[str(issue.get("issue_no"))] = f"{n}.0"
        issue["issue_no"] = f"{n}.0"

    # Recommendations and conflicts point at issue numbers. Re-point the survivors and drop the
    # references to the deleted row, or the workbook would cite issues that no longer exist.
    recommendations = []
    for rec in list(row.recommendations or []):
        addresses = [renumbered[a] for a in (rec.get("addresses") or []) if a in renumbered]
        rec["addresses"] = addresses
        rec["issues_addressed"] = len(addresses)
        recommendations.append(rec)

    run = dict(row.run or {})
    conflicts = [c for c in (run.get("conflicts") or [])
                 if str(c.get("issue_a")) in renumbered and str(c.get("issue_b")) in renumbered]
    for conflict in conflicts:
        conflict["issue_a"] = renumbered[str(conflict["issue_a"])]
        conflict["issue_b"] = renumbered[str(conflict["issue_b"])]
    run["conflicts"] = conflicts

    row.findings = remaining
    row.recommendations = recommendations
    row.run = run
    await db.commit()
    return {"deleted": issue_no, "remaining": len(remaining)}


@router.delete("/{log_id}", status_code=204)
async def delete_issue_log(log_id: int, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> Response:
    row = await _owned(db, log_id, user)
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------------------------------
# Deprecated. The original Issue Log surfaced *maturity findings* (axis / capability / severity)
# rather than issue-log rows, which is a different object entirely. The current UI still calls
# this; remove it once the frontend moves to /generate.
# ------------------------------------------------------------------------------------------

class CollectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[Selection] = Field(default_factory=list, max_length=MAX_SELECTIONS)


@router.post("/collect", deprecated=True)
async def collect(body: CollectRequest, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)) -> dict:
    return await collect_findings(db, user.id, [s.model_dump() for s in body.selections])
