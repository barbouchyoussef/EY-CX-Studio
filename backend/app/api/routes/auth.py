"""Authentication routes: login, refresh, logout, me, invite, accept.

Token model (locked design): a short-lived JWT *access* token returned in the body and kept
in memory by the SPA, plus a rotating *refresh* token in an HttpOnly, path-scoped cookie.
The long-lived credential (refresh) is never readable by JavaScript, so XSS cannot exfiltrate
a durable session.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.user import User
from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.db import get_db
from app.schemas.auth import (
    AcceptInviteRequest,
    AccessTokenResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InviteCreatedResponse,
    InviteRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserAdminUpdate,
    UserOut,
)
from app.services.auth import security, service
from app.services.email import sender as email_sender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")

_REFRESH_COOKIE = "cx_refresh"
_COOKIE_PATH = "/api/v1/auth"  # cookie is only ever sent to /auth/refresh and /auth/logout


def _set_refresh_cookie(response: Response, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=raw,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,                      # unreadable by JS -> XSS-safe
        secure=settings.cookie_secure,      # HTTPS-only in production
        samesite=settings.cookie_samesite,  # 'strict' -> primary CSRF defense
        path=_COOKIE_PATH,
        domain=settings.cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=_REFRESH_COOKIE, path=_COOKIE_PATH, domain=settings.cookie_domain
    )


def _login_response(response: Response, user: User) -> LoginResponse:
    access = security.create_access_token(user.id, user.role)
    return LoginResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    user = await service.authenticate(db, body.email, body.password)
    if user is None:
        # One generic error for unknown-email / wrong-password / disabled: no enumeration.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    raw = await service.issue_refresh_token(db, user_id=user.id)
    _set_refresh_cookie(response, raw)
    return _login_response(response, user)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session")
    try:
        user, new_raw = await service.rotate_refresh_token(db, raw)
    except service.RefreshError:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    _set_refresh_cookie(response, new_raw)
    return AccessTokenResponse(access_token=security.create_access_token(user.id, user.role))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(_REFRESH_COOKIE)
    if raw:
        await service.revoke_refresh_token(db, raw)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/invite", response_model=InviteCreatedResponse, status_code=201)
async def invite(
    body: InviteRequest,
    current: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> InviteCreatedResponse:
    # Only an admin may mint an admin invite; a consultant can only invite consultants.
    if body.role == "admin" and current.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    try:
        inv = await service.create_invite(
            db, email=body.email, role=body.role, invited_by_id=current.id
        )
    except service.InviteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    accept_url = f"{get_settings().app_base_url}/accept-invite?token={inv.token}"
    # Best-effort delivery: if SMTP is down/unconfigured, the token is still returned below so
    # the admin can share the link manually. Never fail the invite because mail failed.
    if email_sender.is_configured():
        try:
            subject, text, html = email_sender.build_invite_email(accept_url, current.full_name)
            await email_sender.send_email(inv.email, subject, text, html)
        except Exception:
            logger.exception("Invite email to %s failed to send", inv.email)

    return InviteCreatedResponse(
        email=inv.email,
        role=inv.role,
        token=inv.token,
        expires_at=inv.expires_at,
        accept_path=accept_url,
    )


@router.post("/forgot-password", status_code=202, response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    # Always 202 with the same body, whether or not the email exists -- no account enumeration.
    result = await service.request_password_reset(db, body.email)
    if result is not None and email_sender.is_configured():
        user, raw = result
        reset_url = f"{get_settings().app_base_url}/reset-password?token={raw}"
        try:
            subject, text, html = email_sender.build_reset_email(reset_url)
            await email_sender.send_email(user.email, subject, text, html)
        except Exception:
            logger.exception("Password-reset email to %s failed to send", user.email)
    return MessageResponse(detail="If that email is registered, a reset link has been sent.")


@router.post("/reset-password", response_model=LoginResponse)
async def reset_password(
    body: ResetPasswordRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    try:
        user = await service.reset_password(db, body.token, body.password)
    except service.PasswordResetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    raw = await service.issue_refresh_token(db, user_id=user.id)  # fresh session after reset
    _set_refresh_cookie(response, raw)
    return _login_response(response, user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateProfileRequest,
    current: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Update the caller's own profile. The target is always the authenticated user, never an
    id from the request, so this cannot be pointed at another account."""
    try:
        user = await service.update_profile(db, current, full_name=body.full_name)
    except service.UserAdminError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=AccessTokenResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    current: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    try:
        await service.change_password(db, current, body.current_password, body.new_password)
    except service.PasswordResetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # change_password revoked every session; re-issue one so the current tab stays signed in.
    raw = await service.issue_refresh_token(db, user_id=current.id)
    _set_refresh_cookie(response, raw)
    return AccessTokenResponse(access_token=security.create_access_token(current.id, current.role))


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _admin: Annotated[User, Depends(require_admin)], db: AsyncSession = Depends(get_db)
) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await service.list_users(db)]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserAdminUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    try:
        user = await service.update_user(
            db, acting_user=admin, target_user_id=user_id, role=body.role, status=body.status
        )
    except service.UserAdminError as e:
        code = 404 if e.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=str(e))
    return UserOut.model_validate(user)


@router.post("/accept", response_model=LoginResponse)
async def accept(
    body: AcceptInviteRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    try:
        user = await service.accept_invite(
            db, token=body.token, full_name=body.full_name, password=body.password
        )
    except service.InviteError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    raw = await service.issue_refresh_token(db, user_id=user.id)
    _set_refresh_cookie(response, raw)
    return _login_response(response, user)
