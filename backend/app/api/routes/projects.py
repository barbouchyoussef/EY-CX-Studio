"""Routes for engagement projects -- Postgres-backed and authenticated.

Access model: you must be a project member to view/work on it (non-members get 404, which also
avoids leaking that a project exists); only the owner may delete it or manage members.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_interview_report import ProjectInterviewReport
from app.db.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.schemas.project import (
    ArtifactCreate,
    ArtifactOut,
    MemberAdd,
    Project,
    ProjectCreate,
    ProjectMemberOut,
    ProjectUpdate,
    ShareCreate,
    ShareOut,
    ShareRecipientOut,
    StepUpdate,
)
from app.services.auth import access
from app.services.assessment import interview_project_report
from app.services.projects import interview_sources
from app.services.projects import project_service as svc

router = APIRouter(prefix="/projects")
shares_router = APIRouter(prefix="/shares")

CurrentUser = Annotated[User, Depends(get_current_user)]


async def _role_or_404(db: AsyncSession, user_id: int, project_id: int) -> str:
    role = await access.get_project_role(db, user_id, project_id)
    if role is None:
        # 404 (not 403) so a non-member can't even tell the project exists.
        raise HTTPException(status_code=404, detail="Project not found")
    return role


def _require_owner(role: str) -> None:
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only the project owner can do this")


# --------------------------------------------------------------------------- #
# Projects                                                                      #
# --------------------------------------------------------------------------- #

@router.get("", response_model=list[Project])
async def list_projects(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[Project]:
    return await svc.list_for_user(db, user.id)


@router.post("", response_model=Project, status_code=201)
async def create_project(
    body: ProjectCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> Project:
    # owner is always the caller -- never taken from the client.
    return await svc.create(db, user.id, body.name, body.company_name, body.sector)


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> Project:
    await _role_or_404(db, user.id, project_id)
    project = await svc.get_serialized(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: int, body: ProjectUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> Project:
    await _role_or_404(db, user.id, project_id)
    project = await svc.update(
        db, project_id, user.id, name=body.name, company_name=body.company_name, sector=body.sector
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}/steps/{step_key}", response_model=Project)
async def set_project_step(
    project_id: int,
    step_key: str,
    body: StepUpdate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Project:
    await _role_or_404(db, user.id, project_id)
    try:
        project = await svc.set_step(db, project_id, step_key, body.status, user.id)
    except svc.ProjectError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    role = await _role_or_404(db, user.id, project_id)
    _require_owner(role)
    await svc.delete_project(db, project_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Members                                                                       #
# --------------------------------------------------------------------------- #

@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_member(
    project_id: int, body: MemberAdd, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectMemberOut:
    role = await _role_or_404(db, user.id, project_id)
    _require_owner(role)
    try:
        return await svc.add_member(db, project_id, body.email)
    except svc.ProjectError as e:
        raise HTTPException(status_code=404 if e.code == "no_user" else 400, detail=str(e))


@router.delete("/{project_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    project_id: int, member_user_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    role = await _role_or_404(db, user.id, project_id)
    _require_owner(role)
    project = await svc.get_serialized(db, project_id, user.id)
    owner_id = project.owner_id if project else user.id
    try:
        await svc.remove_member(db, project_id, member_user_id, owner_id)
    except svc.ProjectError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Artifacts                                                                     #
# --------------------------------------------------------------------------- #

@router.get("/{project_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(
    project_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ArtifactOut]:
    await _role_or_404(db, user.id, project_id)
    return await svc.list_artifacts(db, project_id)


@router.post("/{project_id}/artifacts", response_model=ArtifactOut, status_code=201)
async def add_artifact(
    project_id: int, body: ArtifactCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ArtifactOut:
    await _role_or_404(db, user.id, project_id)
    return await svc.add_artifact(
        db,
        project_id,
        kind=body.kind,
        ref_id=body.ref_id,
        step_key=body.step_key,
        title=body.title,
        created_by=user.id,
    )


@router.delete("/{project_id}/artifacts/{artifact_id}", status_code=204)
async def detach_artifact(
    project_id: int, artifact_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    """Unlink a result from the project (keeps the underlying analysis in the normal tools)."""
    await _role_or_404(db, user.id, project_id)  # any member may tidy the project
    if not await svc.detach_artifact(db, project_id, artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Interview report (project-level)                                               #
# --------------------------------------------------------------------------- #
#
# This lives on the project rather than on a guide because it is the one report that has no single
# owning interview: it exists to say what several interviews mean TOGETHER, and where they
# contradict each other and the self-assessments they came from. Any member may generate it --
# same rule as attaching an artifact -- and `_role_or_404` above is what enforces that.


def _report_sources(interviews: list[dict], assessments: list[dict]) -> dict:
    """What the report was built from, in a form that changes when the material does.

    The answered count is in here on purpose: recording more answers to an interview already in
    the report changes what the report should say, and the id list alone would not notice.
    """
    return {
        "guides": [{"id": iv["id"], "answered": iv["answered"], "total": iv["total"]}
                   for iv in interviews],
        "assessment_ids": [a["id"] for a in assessments],
    }


@router.get("/{project_id}/interview-report")
async def get_interview_report(
    project_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    """The stored report, plus whether it still matches the interviews it was built from.

    `stale` is what lets the UI offer "Regenerate" with a reason: a report generated before
    another interview was attached, or before more answers were recorded, is out of date even
    though nothing about it failed.
    """
    await _role_or_404(db, user.id, project_id)
    row = await db.get(ProjectInterviewReport, project_id)
    interviews, assessments, _company = await interview_sources.gather(db, project_id)

    if row is None:
        return {"status": "none", "report": None, "can_generate": bool(interviews),
                "interview_count": len(interviews)}
    return {
        "status": "ready",
        "report": {
            "overview": row.overview,
            "markdown": row.markdown,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        },
        "stale": row.sources != _report_sources(interviews, assessments),
        "can_generate": bool(interviews),
        "interview_count": len(interviews),
    }


@router.post("/{project_id}/interview-report", status_code=201)
async def generate_interview_report(
    project_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    """Build the consolidated interview report and store it, replacing any previous one."""
    await _role_or_404(db, user.id, project_id)
    interviews, assessments, company = await interview_sources.gather(db, project_id)

    try:
        overview, markdown = await interview_project_report.generate(
            company, interviews, assessments,
            language=(interviews[0]["language"] if interviews else "en"),
        )
    except ValueError as exc:
        # Nothing to report on -- the caller's problem to fix, not a server error.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sources = _report_sources(interviews, assessments)
    existing = await db.get(ProjectInterviewReport, project_id)
    if existing is None:
        db.add(ProjectInterviewReport(
            project_id=project_id, overview=overview, markdown=markdown,
            sources=sources, generated_by=user.id,
        ))
    else:
        existing.overview = overview
        existing.markdown = markdown
        existing.sources = sources
        existing.generated_by = user.id
        existing.generated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "success", "report": {"overview": overview, "markdown": markdown,
                                            "generated_at": datetime.now(timezone.utc).isoformat()},
            "stale": False, "can_generate": True, "interview_count": len(interviews)}


# --------------------------------------------------------------------------- #
# Shares (analysis-level)                                                        #
# --------------------------------------------------------------------------- #

@shares_router.get("/mine", response_model=list[ShareOut])
async def my_shares(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ShareOut]:
    return await svc.shared_with_me(db, user.id)


@shares_router.get("/for", response_model=list[ShareRecipientOut])
async def shares_for(
    kind: str, ref_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ShareRecipientOut]:
    """Who the current user has shared a specific analysis with."""
    return await svc.shares_created_for(db, user.id, kind, ref_id)


@shares_router.post("", response_model=ShareOut, status_code=201)
async def create_share(
    body: ShareCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ShareOut:
    try:
        return await svc.create_share(db, user.id, body.kind, body.ref_id, body.email)
    except svc.ProjectError as e:
        code = {"no_user": 404, "forbidden": 403, "self": 400}.get(e.code, 400)
        raise HTTPException(status_code=code, detail=str(e))


@shares_router.delete("/{share_id}", status_code=204)
async def delete_share(
    share_id: int, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    try:
        ok = await svc.delete_share(db, share_id, user.id)
    except svc.ProjectError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Share not found")
    return Response(status_code=204)
