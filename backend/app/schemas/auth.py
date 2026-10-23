"""Request/response schemas for auth. Request models forbid extra fields so a client cannot
inject values the server is meant to control (e.g. role, status, owner ids)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Role = Literal["admin", "consultant"]

# Password policy: at least 8 characters, and a mix of letters and numbers. bcrypt (after our
# sha256 pre-hash) handles any length; the ceiling just stops absurd payloads. Keep this in sync
# with the frontend checklist (frontend/src/lib/password.ts).
PASSWORD_MIN_LEN = 8


def _check_password(v: str) -> str:
    if len(v) < PASSWORD_MIN_LEN:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LEN} characters")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Password must include at least one letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must include at least one number")
    return v


Password = Annotated[str, Field(max_length=200), AfterValidator(_check_password)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str


class InviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    role: Role = "consultant"


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    full_name: str = Field(min_length=1, max_length=200)
    password: Password


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    password: Password


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str
    new_password: Password


class UpdateProfileRequest(BaseModel):
    """Self-service profile edit. Deliberately only the display name: email is the login
    identifier and is what invitations and password resets are addressed to, so changing it
    is an admin concern rather than a profile setting."""

    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=200)


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role | None = None
    status: Literal["active", "disabled"] | None = None


class MessageResponse(BaseModel):
    detail: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    role: Role
    status: str
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class InviteCreatedResponse(BaseModel):
    email: EmailStr
    role: Role
    token: str
    expires_at: datetime
    accept_path: str
