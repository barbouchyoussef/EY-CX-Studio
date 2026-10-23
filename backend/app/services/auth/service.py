"""Auth database operations. Thin, async, and the single place identity state changes.

Errors are raised as AuthError subclasses carrying a machine code; the route layer maps them
to HTTP responses with deliberately generic messages (never leak which part failed).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.user import Invite, PasswordResetToken, RefreshToken, User
from app.services.auth import security


class AuthError(Exception):
    """Base for expected auth failures (mapped to 4xx by the route)."""

    code = "auth_error"


class InvalidCredentialsError(AuthError):
    code = "invalid_credentials"


class InviteError(AuthError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RefreshError(AuthError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PasswordResetError(AuthError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UserAdminError(AuthError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------------- #
# Lookups                                                                       #
# --------------------------------------------------------------------------- #

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


# --------------------------------------------------------------------------- #
# Login                                                                         #
# --------------------------------------------------------------------------- #

async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """Return the user on success, else None. Every failure path spends a bcrypt verify so
    timing does not distinguish unknown-email from wrong-password from disabled-account."""
    user = await get_user_by_email(db, email)
    if user is None or user.status != "active":
        security.verify_password(password, user.password_hash if user else None)
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user


# --------------------------------------------------------------------------- #
# Invites                                                                       #
# --------------------------------------------------------------------------- #

async def create_invite(
    db: AsyncSession, *, email: str, role: str, invited_by_id: int | None
) -> Invite:
    email = normalize_email(email)
    existing = await get_user_by_email(db, email)
    if existing and existing.status == "active":
        raise InviteError("user_exists", "A user with this email already exists")

    settings = get_settings()
    invite = Invite(
        token=security.generate_invite_token(),
        email=email,
        role=role,
        invited_by=invited_by_id,
        expires_at=_now() + timedelta(hours=settings.invite_expire_hours),
    )
    db.add(invite)
    await db.commit()
    return invite


async def accept_invite(
    db: AsyncSession, *, token: str, full_name: str, password: str
) -> User:
    invite = await db.get(Invite, token)
    if invite is None:
        raise InviteError("invalid", "Invalid or unknown invitation")
    if invite.accepted_at is not None:
        raise InviteError("used", "This invitation has already been used")
    if invite.expires_at < _now():
        raise InviteError("expired", "This invitation has expired")

    user = await get_user_by_email(db, invite.email)
    if user and user.status == "active":
        raise InviteError("used", "This invitation has already been used")

    password_hash = security.hash_password(password)
    if user is None:
        # Role is taken from the invite (server-controlled) -- the accepter cannot choose it.
        user = User(
            email=invite.email,
            full_name=full_name.strip(),
            password_hash=password_hash,
            role=invite.role,
            status="active",
        )
        db.add(user)
    else:  # a pending/disabled row for this email -- activate it in place
        user.full_name = full_name.strip()
        user.password_hash = password_hash
        user.role = invite.role
        user.status = "active"

    invite.accepted_at = _now()
    await db.commit()
    await db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Refresh tokens (rotation + reuse detection)                                   #
# --------------------------------------------------------------------------- #

async def issue_refresh_token(
    db: AsyncSession, *, user_id: int, family_id: str | None = None
) -> str:
    """Create a refresh-token row and return the RAW value for the cookie. Only its hash is
    stored. Pass an existing family_id when rotating so the chain stays linked."""
    settings = get_settings()
    raw = security.generate_refresh_token()
    row = RefreshToken(
        jti=security.hash_token(raw),
        user_id=user_id,
        family_id=family_id or security.new_family_id(),
        expires_at=_now() + timedelta(days=settings.refresh_token_days),
    )
    db.add(row)
    await db.commit()
    return raw


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    rows = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
        )
    ).scalars()
    now = _now()
    for row in rows:
        row.revoked_at = now
    await db.commit()


async def rotate_refresh_token(db: AsyncSession, raw: str) -> tuple[User, str]:
    """Validate the presented refresh token, rotate it, and return (user, new_raw).

    Reuse detection: presenting a token that was already rotated (revoked) is the signature
    of a stolen cookie, so the whole family is revoked and the caller is rejected.
    """
    row = await db.get(RefreshToken, security.hash_token(raw))
    if row is None:
        raise RefreshError("invalid", "Invalid session")
    if row.revoked_at is not None:
        await _revoke_family(db, row.family_id)
        raise RefreshError("reuse", "Session reuse detected")
    if row.expires_at < _now():
        raise RefreshError("expired", "Session expired")

    user = await get_user_by_id(db, row.user_id)
    if user is None or user.status != "active":
        raise RefreshError("invalid", "Invalid session")

    row.revoked_at = _now()
    await db.commit()
    new_raw = await issue_refresh_token(db, user_id=user.id, family_id=row.family_id)
    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, raw: str) -> None:
    row = await db.get(RefreshToken, security.hash_token(raw))
    if row is not None and row.revoked_at is None:
        row.revoked_at = _now()
        await db.commit()


async def revoke_all_user_refresh(db: AsyncSession, user_id: int) -> None:
    """Kill every active session for a user (used on password reset/change and account disable)."""
    rows = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
    ).scalars()
    now = _now()
    for row in rows:
        row.revoked_at = now
    await db.commit()


# --------------------------------------------------------------------------- #
# Password reset + change                                                       #
# --------------------------------------------------------------------------- #

async def request_password_reset(db: AsyncSession, email: str) -> tuple[User, str] | None:
    """Create a reset token for an active user, or return None if there's no such account.
    The route treats both cases identically so it never reveals whether an email is registered."""
    user = await get_user_by_email(db, email)
    if user is None or user.status != "active":
        return None
    settings = get_settings()
    raw = security.generate_reset_token()
    db.add(
        PasswordResetToken(
            token_hash=security.hash_token(raw),
            user_id=user.id,
            expires_at=_now() + timedelta(hours=settings.password_reset_expire_hours),
        )
    )
    await db.commit()
    return user, raw


async def reset_password(db: AsyncSession, raw: str, new_password: str) -> User:
    row = await db.get(PasswordResetToken, security.hash_token(raw))
    if row is None or row.used_at is not None:
        raise PasswordResetError("invalid", "Invalid or used reset link")
    if row.expires_at < _now():
        raise PasswordResetError("expired", "This reset link has expired")

    user = await get_user_by_id(db, row.user_id)
    if user is None or user.status == "disabled":
        raise PasswordResetError("invalid", "Invalid reset link")

    user.password_hash = security.hash_password(new_password)
    if user.status == "pending":
        user.status = "active"
    row.used_at = _now()
    await db.commit()
    # A reset may follow a compromise: drop every existing session for this account.
    await revoke_all_user_refresh(db, user.id)
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not security.verify_password(current_password, user.password_hash):
        raise PasswordResetError("wrong_current", "Current password is incorrect")
    user.password_hash = security.hash_password(new_password)
    await db.commit()
    # Invalidate all sessions; the route re-issues a fresh one so the current tab stays in.
    await revoke_all_user_refresh(db, user.id)


# --------------------------------------------------------------------------- #
# User administration (admin only)                                              #
# --------------------------------------------------------------------------- #

async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars())


async def update_user(
    db: AsyncSession,
    *,
    acting_user: User,
    target_user_id: int,
    role: str | None = None,
    status: str | None = None,
) -> User:
    target = await get_user_by_id(db, target_user_id)
    if target is None:
        raise UserAdminError("not_found", "User not found")
    # Anti-lockout: an admin cannot demote or disable their own account.
    if target.id == acting_user.id and (role is not None or status is not None):
        raise UserAdminError("self", "You cannot change your own role or status")
    if role is not None:
        target.role = role
    if status is not None:
        target.status = status
    await db.commit()
    if status == "disabled":
        await revoke_all_user_refresh(db, target.id)  # kick active sessions immediately
    await db.refresh(target)
    return target


async def update_profile(db: AsyncSession, user: User, *, full_name: str) -> User:
    """Update the caller's own display name.

    Scoped to the acting user on purpose: the route passes the authenticated User, so there is
    no id in the request body that could be pointed at somebody else's account.
    """
    name = full_name.strip()
    if not name:
        raise UserAdminError("invalid", "Name cannot be empty")
    user.full_name = name
    await db.commit()
    await db.refresh(user)
    return user
