"""Client magic-link lifecycle for assessments.

A consultant creates a recipient for an assessment → a raw token (returned once, put in the link);
only its sha256 is stored. The client opens the link with no login; the token grants access to
exactly one assessment. Tokens expire and can be revoked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment_recipient import AssessmentRecipient
from app.services.auth import security


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_recipient(
    db: AsyncSession,
    *,
    assessment_id: int,
    client_name: str | None,
    client_role: str | None,
    created_by: int,
    expire_days: int = 30,
) -> tuple[AssessmentRecipient, str]:
    """Create a recipient and return (row, RAW token). Only the token's hash is stored."""
    raw = security.generate_reset_token()  # high-entropy urlsafe token
    rec = AssessmentRecipient(
        assessment_id=assessment_id,
        token_hash=security.hash_token(raw),
        client_name=(client_name or "").strip() or None,
        client_role=(client_role or "").strip() or None,
        created_by=created_by,
        status="sent",
        expires_at=_now() + timedelta(days=expire_days),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec, raw


async def resolve(db: AsyncSession, raw_token: str) -> AssessmentRecipient | None:
    """Return the recipient a valid, unexpired, non-revoked token grants, else None."""
    rec = (
        await db.execute(
            select(AssessmentRecipient).where(
                AssessmentRecipient.token_hash == security.hash_token(raw_token)
            )
        )
    ).scalar_one_or_none()
    if rec is None or rec.status == "revoked":
        return None
    if rec.expires_at is not None and rec.expires_at < _now():
        return None
    return rec


async def mark_opened(db: AsyncSession, rec: AssessmentRecipient) -> None:
    if rec.status == "sent":
        rec.status = "opened"
        rec.opened_at = _now()
        await db.commit()


async def mark_completed(db: AsyncSession, assessment_id: int) -> None:
    """Flip the (non-revoked) recipient(s) of an assessment to completed."""
    rows = (
        await db.execute(
            select(AssessmentRecipient).where(
                AssessmentRecipient.assessment_id == assessment_id,
                AssessmentRecipient.status != "revoked",
                AssessmentRecipient.status != "completed",
            )
        )
    ).scalars()
    now = _now()
    changed = False
    for rec in rows:
        rec.status = "completed"
        rec.completed_at = now
        changed = True
    if changed:
        await db.commit()


async def list_for_assessment(db: AsyncSession, assessment_id: int) -> list[AssessmentRecipient]:
    rows = await db.execute(
        select(AssessmentRecipient)
        .where(AssessmentRecipient.assessment_id == assessment_id)
        .order_by(AssessmentRecipient.created_at.desc())
    )
    return list(rows.scalars())


async def revoke(db: AsyncSession, recipient_id: int, assessment_id: int) -> bool:
    rec = await db.get(AssessmentRecipient, recipient_id)
    if rec is None or rec.assessment_id != assessment_id:
        return False
    rec.status = "revoked"
    await db.commit()
    return True


async def latest_recipient_by_assessment(
    db: AsyncSession, assessment_ids: list[int]
) -> dict[int, AssessmentRecipient]:
    """Map assessment_id -> its most recent non-revoked recipient row (for the list view).

    Carries who the link was sent to (name/role) plus its status, so the dashboard can show it.
    """
    if not assessment_ids:
        return {}
    rows = (
        await db.execute(
            select(AssessmentRecipient)
            .where(
                AssessmentRecipient.assessment_id.in_(assessment_ids),
                AssessmentRecipient.status != "revoked",
            )
            .order_by(AssessmentRecipient.created_at.desc())
        )
    ).scalars()
    out: dict[int, AssessmentRecipient] = {}
    for rec in rows:  # newest first, so first seen per assessment wins
        out.setdefault(rec.assessment_id, rec)
    return out
