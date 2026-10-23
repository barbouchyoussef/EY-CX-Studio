"""Auth crypto primitives -- pure functions, no database.

Kept deliberately small and dependency-light so it can be unit-tested in isolation: this is
where the security-critical decisions live (password hashing, JWT verification, refresh-token
hashing). The DB-touching logic lives in service.py.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

_ALGORITHM = "HS256"
_ACCESS_TOKEN_TYPE = "access"

# A bcrypt hash of a throwaway value, used to spend roughly the same CPU on the
# "user has no password / does not exist" branch as on a real verify, so login timing
# does not leak whether an account exists. Computed once at import.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt())


# --------------------------------------------------------------------------- #
# Passwords                                                                     #
# --------------------------------------------------------------------------- #

def _prepare(password: str) -> bytes:
    """SHA-256 then base64 the password before bcrypt.

    bcrypt silently ignores everything past 72 bytes and mishandles embedded null bytes.
    Pre-hashing to a fixed 44-byte base64 string removes both problems (the well-known
    'bcrypt_sha256' construction) so passwords of any length are handled correctly.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time verify. Always does a bcrypt compare, even when there is no stored
    hash (pending/unknown user), so the response time does not reveal account state."""
    if not password_hash:
        bcrypt.checkpw(_prepare(password), _DUMMY_HASH)  # spend the time, ignore the result
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed stored hash -- treat as a failed login, never a 500.
        return False


# --------------------------------------------------------------------------- #
# Access tokens (JWT)                                                           #
# --------------------------------------------------------------------------- #

def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role": role,
        "type": _ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and fully validate an access token.

    Pinning `algorithms=[_ALGORITHM]` is the key line: it rejects `alg: none` and prevents
    an attacker from swapping HS256 for an asymmetric alg to bypass the signature check.
    Raises jwt.InvalidTokenError (incl. ExpiredSignatureError) on any problem.
    """
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )
    if claims.get("type") != _ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("wrong token type")
    return claims


# --------------------------------------------------------------------------- #
# Refresh tokens (opaque, hashed at rest)                                       #
# --------------------------------------------------------------------------- #

def generate_refresh_token() -> str:
    """The raw value handed to the browser cookie. High entropy, never stored as-is."""
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    """The stored form of any opaque token (refresh cookie or invite token): SHA-256 hex.
    A database leak therefore exposes no usable token."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_family_id() -> str:
    return uuid.uuid4().hex


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)
