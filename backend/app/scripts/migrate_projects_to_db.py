"""One-off: import the old file-based projects (projects_data/*.json) into Postgres.

Each JSON project becomes a `projects` row owned by the first admin (also added as a member),
with its per-step status carried over. Idempotent by (owner, name): re-running skips imports.
Run once after applying migrations 046-048:  python -m app.scripts.migrate_projects_to_db
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select

from app.core.config import load_env_file
from app.db.models.project import Project, ProjectMember, ProjectStep
from app.db.models.user import User
from app.db.session import SessionLocal
from app.schemas.project import PROJECT_STEPS

_ROOT = Path(os.getenv("PROJECTS_DATA_ROOT", "projects_data"))


async def _main() -> int:
    load_env_file()
    files = sorted(_ROOT.glob("*.json")) if _ROOT.exists() else []
    if not files:
        print("No project JSON files to import.")
        return 0

    async with SessionLocal() as db:
        admin = (
            await db.execute(
                select(User).where(User.role == "admin", User.status == "active").order_by(User.id)
            )
        ).scalars().first()
        if admin is None:
            print("No active admin found. Create one first: python -m app.scripts.create_admin")
            return 1

        imported = skipped = 0
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                print(f"Skipping unreadable {f.name}")
                continue
            name = (data.get("name") or "Untitled Project").strip()

            exists = (
                await db.execute(
                    select(Project.id).where(Project.owner_id == admin.id, Project.name == name)
                )
            ).first()
            if exists:
                skipped += 1
                continue

            project = Project(
                owner_id=admin.id,
                name=name,
                company_name=(data.get("company_name") or None),
                sector=(data.get("sector") or None),
            )
            db.add(project)
            await db.flush()
            db.add(ProjectMember(project_id=project.id, user_id=admin.id, role="owner"))
            steps = data.get("steps") or {}
            for key in PROJECT_STEPS:
                db.add(
                    ProjectStep(
                        project_id=project.id, step_key=key, status=steps.get(key, "todo")
                    )
                )
            imported += 1

        await db.commit()
        print(f"Imported {imported} project(s), skipped {skipped} already present. Owner: {admin.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
