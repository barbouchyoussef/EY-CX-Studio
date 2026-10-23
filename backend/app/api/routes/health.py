from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db


router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    # Minimal readiness checks for deployments and admin-side assumptions.
    checks: dict[str, object] = {"db": False, "sectors": 0, "company_sizes": 0, "axes": 0, "capabilities": 0}
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = True
        checks["sectors"] = int((await db.execute(text("SELECT COUNT(*) FROM sectors"))).scalar() or 0)
        checks["company_sizes"] = int((await db.execute(text("SELECT COUNT(*) FROM company_sizes"))).scalar() or 0)
        checks["axes"] = int((await db.execute(text("SELECT COUNT(*) FROM axes"))).scalar() or 0)
        checks["capabilities"] = int((await db.execute(text("SELECT COUNT(*) FROM capabilities"))).scalar() or 0)
    except Exception as e:
        checks["error"] = str(e)

    ok = (
        bool(checks["db"])
        and checks["sectors"] > 0
        and checks["company_sizes"] > 0
        and checks["axes"] > 0
        and checks["capabilities"] > 0
    )
    checks["status"] = "ok" if ok else "not_ready"
    return checks
