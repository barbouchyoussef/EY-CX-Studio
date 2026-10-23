"""Bootstrap the first admin account.

Invite-only auth can't invite its own first user, so this seeds one from the environment:

    ADMIN_EMAIL=you@ey.com ADMIN_PASSWORD='a-strong-passphrase' python -m app.scripts.create_admin

Idempotent: run again to (re)activate the account and reset its password.
"""

from __future__ import annotations

import asyncio
import os
import sys

from app.core.config import load_env_file
from app.db.session import SessionLocal
from app.services.auth import security, service


async def _main() -> int:
    load_env_file()
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD in the environment or .env.")
        return 1
    from app.schemas.auth import _check_password

    try:
        _check_password(password)
    except ValueError as e:
        print(f"ADMIN_PASSWORD invalid: {e}")
        return 1

    async with SessionLocal() as db:
        user = await service.get_user_by_email(db, email)
        password_hash = security.hash_password(password)
        if user is None:
            from app.db.models.user import User

            user = User(
                email=service.normalize_email(email),
                full_name="Administrator",
                password_hash=password_hash,
                role="admin",
                status="active",
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = password_hash
            user.role = "admin"
            user.status = "active"
            action = "updated"
        await db.commit()
    print(f"Admin {action}: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
