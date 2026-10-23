"""Postgres-backed project operations: projects, members, steps, artifacts, and shares.

Replaces the old JSON file store. Access decisions live in app/services/auth/access.py; the
route layer enforces them (member to view, owner to manage) and maps ProjectError to HTTP.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.project import Project, ProjectArtifact, ProjectMember, ProjectStep
from app.db.models.share import AnalysisShare
from app.db.models.user import User
from app.schemas.project import (
    PROJECT_STEPS,
    ArtifactOut,
    ProjectMemberOut,
    ShareOut,
    ShareRecipientOut,
)
from app.schemas.project import Project as ProjectSchema
from app.services.auth import access, service


class ProjectError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load(db: AsyncSession, project_id: int) -> Project | None:
    q = (
        select(Project)
        .options(
            selectinload(Project.steps),
            selectinload(Project.members).selectinload(ProjectMember.user),
        )
        .where(Project.id == project_id)
    )
    return (await db.execute(q)).scalar_one_or_none()


def _serialize(project: Project, user_id: int) -> ProjectSchema:
    steps = {s.step_key: s.status for s in project.steps}
    for key in PROJECT_STEPS:
        steps.setdefault(key, "todo")
    members = [
        ProjectMemberOut(
            user_id=m.user_id, full_name=m.user.full_name, email=m.user.email, role=m.role
        )
        for m in project.members
    ]
    my_role = next((m.role for m in project.members if m.user_id == user_id), "none")
    return ProjectSchema(
        id=project.id,
        name=project.name,
        company_name=project.company_name,
        sector=project.sector,
        owner_id=project.owner_id,
        my_role=my_role,
        created_at=project.created_at,
        updated_at=project.updated_at,
        steps=steps,  # type: ignore[arg-type]
        members=members,
    )


# --------------------------------------------------------------------------- #
# Projects                                                                      #
# --------------------------------------------------------------------------- #

async def list_for_user(db: AsyncSession, user_id: int) -> list[ProjectSchema]:
    pids = await access.visible_project_ids(db, user_id)
    if not pids:
        return []
    q = (
        select(Project)
        .options(
            selectinload(Project.steps),
            selectinload(Project.members).selectinload(ProjectMember.user),
        )
        .where(Project.id.in_(pids))
        .order_by(Project.updated_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()
    return [_serialize(p, user_id) for p in rows]


async def create(
    db: AsyncSession, owner_id: int, name: str, company_name: str | None, sector: str | None
) -> ProjectSchema:
    project = Project(
        owner_id=owner_id,
        name=name.strip() or "Untitled Project",
        company_name=(company_name or "").strip() or None,
        sector=(sector or "").strip() or None,
    )
    db.add(project)
    await db.flush()  # assigns project.id
    db.add(ProjectMember(project_id=project.id, user_id=owner_id, role="owner"))
    for key in PROJECT_STEPS:
        db.add(ProjectStep(project_id=project.id, step_key=key, status="todo"))
    await db.commit()
    loaded = await _load(db, project.id)
    assert loaded is not None
    return _serialize(loaded, owner_id)


async def get_serialized(db: AsyncSession, project_id: int, user_id: int) -> ProjectSchema | None:
    project = await _load(db, project_id)
    return _serialize(project, user_id) if project else None


async def update(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    *,
    name: str | None,
    company_name: str | None,
    sector: str | None,
) -> ProjectSchema | None:
    project = await db.get(Project, project_id)
    if project is None:
        return None
    if name is not None and name.strip():
        project.name = name.strip()
    if company_name is not None:
        project.company_name = company_name.strip() or None
    if sector is not None:
        project.sector = sector.strip() or None
    project.updated_at = _now()
    await db.commit()
    return await get_serialized(db, project_id, user_id)


async def set_step(
    db: AsyncSession, project_id: int, step_key: str, status: str, user_id: int
) -> ProjectSchema | None:
    if step_key not in PROJECT_STEPS:
        raise ProjectError("bad_step", f"Unknown step '{step_key}'")
    project = await db.get(Project, project_id)
    if project is None:
        return None
    row = await db.get(ProjectStep, (project_id, step_key))
    if row is None:
        db.add(ProjectStep(project_id=project_id, step_key=step_key, status=status))
    else:
        row.status = status
    project.updated_at = _now()
    await db.commit()
    return await get_serialized(db, project_id, user_id)


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    project = await db.get(Project, project_id)
    if project is None:
        return False
    await db.execute(delete(Project).where(Project.id == project_id))  # cascades to children
    await db.commit()
    return True


# --------------------------------------------------------------------------- #
# Members                                                                       #
# --------------------------------------------------------------------------- #

async def add_member(db: AsyncSession, project_id: int, email: str) -> ProjectMemberOut:
    user = await service.get_user_by_email(db, email)
    if user is None or user.status != "active":
        raise ProjectError("no_user", "No active user with that email. Invite them first.")
    existing = await db.get(ProjectMember, (project_id, user.id))
    if existing is None:
        db.add(ProjectMember(project_id=project_id, user_id=user.id, role="collaborator"))
        await db.commit()
    return ProjectMemberOut(
        user_id=user.id, full_name=user.full_name, email=user.email, role="collaborator"
    )


async def remove_member(
    db: AsyncSession, project_id: int, target_user_id: int, owner_id: int
) -> None:
    if target_user_id == owner_id:
        raise ProjectError("owner", "The project owner cannot be removed")
    await db.execute(
        delete(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == target_user_id
        )
    )
    await db.commit()


# --------------------------------------------------------------------------- #
# Artifacts                                                                     #
# --------------------------------------------------------------------------- #

async def add_artifact(
    db: AsyncSession,
    project_id: int,
    *,
    kind: str,
    ref_id: str,
    step_key: str,
    title: str | None,
    created_by: int,
) -> ArtifactOut:
    # Idempotent: the same result attached to the same project only appears once, so a module
    # re-render or repeated completion can't duplicate it.
    existing = (
        await db.execute(
            select(ProjectArtifact).where(
                ProjectArtifact.project_id == project_id,
                ProjectArtifact.kind == kind,
                ProjectArtifact.ref_id == str(ref_id),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ArtifactOut.model_validate(existing)

    artifact = ProjectArtifact(
        project_id=project_id,
        kind=kind,
        ref_id=str(ref_id),
        step_key=step_key,
        title=title,
        created_by=created_by,
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return ArtifactOut.model_validate(artifact)


async def list_artifacts(db: AsyncSession, project_id: int) -> list[ArtifactOut]:
    rows = await db.execute(
        select(ProjectArtifact)
        .where(ProjectArtifact.project_id == project_id)
        .order_by(ProjectArtifact.created_at.desc())
    )
    return [ArtifactOut.model_validate(a) for a in rows.scalars()]


async def detach_artifact(db: AsyncSession, project_id: int, artifact_id: int) -> bool:
    """Unlink a result from a project (the underlying analysis is untouched)."""
    row = await db.get(ProjectArtifact, artifact_id)
    if row is None or row.project_id != project_id:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def cleanup_analysis_links(db: AsyncSession, kind: str, ref_id: str) -> None:
    """Remove every project link + share pointing at an analysis. Called when the underlying
    analysis is deleted for good, so no project or shared-with list keeps a dangling reference."""
    await db.execute(
        delete(ProjectArtifact).where(
            ProjectArtifact.kind == kind, ProjectArtifact.ref_id == str(ref_id)
        )
    )
    await db.execute(
        delete(AnalysisShare).where(AnalysisShare.kind == kind, AnalysisShare.ref_id == str(ref_id))
    )
    await db.commit()


# --------------------------------------------------------------------------- #
# Shares (analysis-level, independent of projects)                              #
# --------------------------------------------------------------------------- #

async def create_share(
    db: AsyncSession, actor_id: int, kind: str, ref_id: str, email: str
) -> ShareOut:
    target = await service.get_user_by_email(db, email)
    if target is None or target.status != "active":
        raise ProjectError("no_user", "No active user with that email.")
    if target.id == actor_id:
        raise ProjectError("self", "You already have access to this.")
    # You can only share what you can already see.
    allowed = await access.owns_analysis(db, actor_id, kind, ref_id) or (
        await access.can_view_via_project_or_share(db, actor_id, kind, ref_id)
    )
    if not allowed:
        raise ProjectError("forbidden", "You cannot share something you don't have access to.")
    existing = (
        await db.execute(
            select(AnalysisShare).where(
                AnalysisShare.kind == kind,
                AnalysisShare.ref_id == str(ref_id),
                AnalysisShare.shared_with == target.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ShareOut.model_validate(existing)
    share = AnalysisShare(
        kind=kind, ref_id=str(ref_id), shared_by=actor_id, shared_with=target.id
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return ShareOut.model_validate(share)


async def shared_with_me(db: AsyncSession, user_id: int) -> list[ShareOut]:
    rows = await db.execute(
        select(AnalysisShare).where(AnalysisShare.shared_with == user_id)
    )
    return [ShareOut.model_validate(s) for s in rows.scalars()]


async def shares_created_for(
    db: AsyncSession, owner_id: int, kind: str, ref_id: str
) -> list[ShareRecipientOut]:
    """Who the owner has shared a specific analysis with (for the Share dialog's recipient list)."""
    rows = await db.execute(
        select(AnalysisShare, User)
        .join(User, User.id == AnalysisShare.shared_with)
        .where(
            AnalysisShare.shared_by == owner_id,
            AnalysisShare.kind == kind,
            AnalysisShare.ref_id == str(ref_id),
        )
    )
    return [
        ShareRecipientOut(
            share_id=s.id, user_id=u.id, email=u.email, full_name=u.full_name
        )
        for s, u in rows.all()
    ]


async def delete_share(db: AsyncSession, share_id: int, actor_id: int) -> bool:
    share = await db.get(AnalysisShare, share_id)
    if share is None:
        return False
    if share.shared_by != actor_id:
        raise ProjectError("forbidden", "Only the person who shared it can revoke it.")
    await db.execute(delete(AnalysisShare).where(AnalysisShare.id == share_id))
    await db.commit()
    return True
