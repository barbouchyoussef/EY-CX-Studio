"""Security properties of the auth crypto core (no database needed).

Each test maps to a concrete attack or footgun: silent bcrypt truncation, login timing leaks,
and the JWT forgery classes (alg:none, tampering, wrong key, wrong token type, expiry).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.services.auth import security


# --------------------------------------------------------------------------- #
# Passwords                                                                     #
# --------------------------------------------------------------------------- #

def test_hash_verify_roundtrip_and_rejects_wrong():
    h = security.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"          # never stored in the clear
    assert security.verify_password("correct horse battery staple", h)
    assert not security.verify_password("wrong password here", h)


def test_verify_with_no_stored_hash_is_false_not_error():
    # A pending/unknown user has password_hash=None; this must not raise (timing branch).
    assert security.verify_password("anything at all", None) is False


def test_long_passwords_are_not_silently_truncated():
    # bcrypt alone ignores everything past 72 bytes; our sha256 pre-hash must defeat that,
    # so two 100-char passwords that share a 72-char prefix still verify distinctly.
    base = "A" * 72
    p1, p2 = base + "1" * 40, base + "2" * 40
    h1 = security.hash_password(p1)
    assert security.verify_password(p1, h1)
    assert not security.verify_password(p2, h1)


def test_malformed_stored_hash_fails_closed():
    assert security.verify_password("whatever", "not-a-bcrypt-hash") is False


# --------------------------------------------------------------------------- #
# Access tokens                                                                 #
# --------------------------------------------------------------------------- #

def _claims(**over):
    now = datetime.now(timezone.utc)
    base = {"sub": "42", "role": "consultant", "type": "access",
            "iat": now, "exp": now + timedelta(minutes=10), "jti": "x"}
    base.update(over)
    return base


def test_access_token_roundtrip():
    tok = security.create_access_token(42, "admin")
    claims = security.decode_access_token(tok)
    assert claims["sub"] == "42" and claims["role"] == "admin" and claims["type"] == "access"


def test_expired_token_is_rejected():
    secret = get_settings().jwt_secret
    tok = jwt.encode(_claims(exp=datetime.now(timezone.utc) - timedelta(seconds=1)), secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(tok)


def test_tampered_signature_is_rejected():
    tok = security.create_access_token(42, "consultant")
    tampered = tok[:-3] + ("aaa" if not tok.endswith("aaa") else "bbb")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(tampered)


def test_alg_none_forgery_is_rejected():
    # The classic bypass: an attacker strips the signature and sets alg=none.
    forged = jwt.encode(_claims(), key="", algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(forged)


def test_token_signed_with_wrong_secret_is_rejected():
    forged = jwt.encode(_claims(), "some-other-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(forged)


def test_non_access_token_type_is_rejected():
    secret = get_settings().jwt_secret
    refreshy = jwt.encode(_claims(type="refresh"), secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(refreshy)


def test_token_missing_required_claims_is_rejected():
    secret = get_settings().jwt_secret
    # No exp -> decode's required-claims option must reject it.
    bad = jwt.encode({"sub": "42", "type": "access", "iat": datetime.now(timezone.utc)}, secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(bad)


# --------------------------------------------------------------------------- #
# Refresh tokens                                                                #
# --------------------------------------------------------------------------- #

def test_refresh_tokens_are_unique_and_stored_as_hash():
    a, b = security.generate_refresh_token(), security.generate_refresh_token()
    assert a != b                                  # high entropy, not colliding
    assert security.hash_token(a) != a             # the DB never holds the raw value
    assert security.hash_token(a) == security.hash_token(a)   # deterministic lookup key
    assert len(security.hash_token(a)) == 64       # sha256 hex


def test_reset_tokens_are_unique():
    assert security.generate_reset_token() != security.generate_reset_token()


# --------------------------------------------------------------------------- #
# Email builders (pure)                                                         #
# --------------------------------------------------------------------------- #

def test_email_sender_is_configured_reflects_settings(monkeypatch):
    from types import SimpleNamespace

    from app.services.email import sender

    # Hermetic: don't depend on the ambient .env (which may have real SMTP set).
    monkeypatch.setattr(sender, "get_settings", lambda: SimpleNamespace(smtp_host=None, email_from=None))
    assert sender.is_configured() is False
    monkeypatch.setattr(
        sender, "get_settings", lambda: SimpleNamespace(smtp_host="smtp.x", email_from="a@b.com")
    )
    assert sender.is_configured() is True


def test_invite_and_reset_emails_embed_their_url():
    from app.services.email import sender

    url = "http://localhost:5173/accept-invite?token=abc123"
    subject, text, html = sender.build_invite_email(url, "Alice")
    assert url in text and url in html and "Alice" in text

    rurl = "http://localhost:5173/reset-password?token=xyz789"
    subject, text, html = sender.build_reset_email(rurl)
    assert rurl in text and rurl in html and "reset" in subject.lower()
