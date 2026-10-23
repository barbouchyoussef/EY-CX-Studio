"""Assign all pre-auth data to an owner so it stays visible once owner-scoping is on.

Records created before authentication existed have owner_id = NULL; a scoped "show only my
data" list would hide (never delete) them. This backfills them to a chosen admin.

    ADMIN_EMAIL=you@example.com python -m app.scripts.backfill_ownership
      (falls back to the oldest active admin if ADMIN_EMAIL is unset)

Idempotent: only touches rows where owner_id IS NULL.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select, update

from app.core.config import load_env_file
from app.db.models.assessment import Assessment
from app.db.models.interview_guide import InterviewGuide
from app.db.models.scraping_job import ScrapingJob
from app.db.models.user import User
from app.db.session import SessionLocal


async def _resolve_admin_id(db) -> int | None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if email:
        uid = (await db.execute(select(User.id).where(User.email == email))).scalar_one_or_none()
        if uid:
            return uid
    return (
        await db.execute(
            select(User.id).where(User.role == "admin", User.status == "active").order_by(User.id)
        )
    ).scalars().first()


async def _main() -> int:
    load_env_file()
    async with SessionLocal() as db:
        admin_id = await _resolve_admin_id(db)
        if admin_id is None:
            print("No admin user found. Create one first (python -m app.scripts.create_admin).")
            return 1
        total = 0
        for model in (Assessment, InterviewGuide, ScrapingJob):
            res = await db.execute(
                update(model).where(model.owner_id.is_(None)).values(owner_id=admin_id)
            )
            print(f"{model.__tablename__}: assigned {res.rowcount} row(s) to user {admin_id}")
            total += res.rowcount or 0
        await db.commit()

    # File stores: stamp owner_id into report/session JSON that predates ownership.
    reports = _backfill_report_files(admin_id)
    sessions = _backfill_desk_sessions(admin_id)
    print(f"scraped_data reports: stamped {reports} file(s)")
    print(f"desk_research sessions: stamped {sessions} file(s)")
    print(f"Done. Backfilled {total} DB row(s) + {reports + sessions} file(s) to admin id {admin_id}.")
    return 0


def _backfill_report_files(admin_id: int) -> int:
    root = Path(os.getenv("SCRAPED_DATA_ROOT", "scraped_data"))
    if not root.exists():
        return 0
    count = 0
    for f in root.glob("*_report_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("owner_id") is None:
                data["owner_id"] = admin_id
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                count += 1
        except Exception:
            pass
    return count


def _backfill_desk_sessions(admin_id: int) -> int:
    root = Path(os.getenv("DESK_RESEARCH_DATA_ROOT", "desk_research_data"))
    if not root.exists():
        return 0
    count = 0
    for session_json in root.glob("*/session.json"):
        try:
            data = json.loads(session_json.read_text(encoding="utf-8"))
            if data.get("owner_id") is None:
                data["owner_id"] = admin_id
                session_json.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                count += 1
        except Exception:
            pass
    return count


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
