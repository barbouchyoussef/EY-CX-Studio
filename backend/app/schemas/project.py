"""Schemas for CX engagement projects (Postgres-backed).

A project is the owned, shareable anchor over the existing modules: it records per-step status
and links (artifacts) to the results produced in each step, and it carries members.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

StepStatus = Literal["todo", "in_progress", "done"]
ArtifactKind = Literal["assessment", "interview_guide", "desk_session", "social_report"]

# The pipeline steps, in engagement order. Keys map to the services-hub modules.
# 'issue_log' is the consolidation capstone — it opens the Issue Log module rather than
# producing a per-step artifact, but it is a tracked step so it shows and toggles like the rest.
PROJECT_STEPS: list[str] = ["assessment", "interview", "social", "desk_research", "issue_log"]


class ProjectMemberOut(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    role: str  # 'owner' | 'collaborator'


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    ref_id: str
    step_key: str
    title: str | None = None
    created_at: datetime


class Project(BaseModel):
    id: int
    name: str
    company_name: str | None = None
    sector: str | None = None
    owner_id: int
    my_role: str  # role of the requesting user on this project
    created_at: datetime
    updated_at: datetime
    steps: dict[str, StepStatus] = Field(default_factory=dict)
    members: list[ProjectMemberOut] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=255)
    company_name: str | None = None
    sector: str | None = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    company_name: str | None = None
    sector: str | None = None


class StepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: StepStatus


class MemberAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ArtifactKind
    ref_id: str
    step_key: str
    title: str | None = None


class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ArtifactKind
    ref_id: str
    email: EmailStr


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    ref_id: str
    shared_with: int


class ShareRecipientOut(BaseModel):
    """A person a given analysis has been shared with (for the owner's 'shared with' list)."""
    share_id: int
    user_id: int
    email: EmailStr
    full_name: str
