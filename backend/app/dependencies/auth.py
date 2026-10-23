"""FastAPI auth dependencies.

`get_current_user` is the gate protected routes depend on -- it turns a Bearer access token
into a live, active User or raises 401. `require_admin` layers a role check on top.
Until now the app's only dependency was get_db; this is the missing authorization hook.
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.dependencies.db import get_db
from app.services.auth import security, service

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization[7:].strip()
    try:
        claims = security.decode_access_token(token)
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        # Expired, tampered, wrong-alg, wrong-type, or malformed subject -- all one generic 401.
        raise _UNAUTHORIZED

    user = await service.get_user_by_id(db, user_id)
    if user is None or user.status != "active":
        raise _UNAUTHORIZED
    # Observability: tag every LLM call made while serving this request with who triggered it.
    from app.services.observability.llm_metrics import bind_owner

    bind_owner(user.id)
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
