"""Sectors: reference data the admin screens maintain.

The most load-bearing of the reference tables. A sector selects the benchmark's candidate leaders,
the EY deck attached to the report, and part of how questions are worded -- so an assessment
cannot start without one, which is why the platform tries to infer it from the company name.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sector import Sector


def normalize_code(value: str) -> str:
    return value.strip().lower()


class SectorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_options(self, limit: int = 200) -> list[Sector]:
        result = await self.db.execute(
            select(Sector)
            .where(Sector.code.notin_(["unknown", "string"]))
            .order_by(Sector.name.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create(self, label: str) -> Sector:
        code = normalize_code(label) if label.strip() else "unknown"
        result = await self.db.execute(select(Sector).where(Sector.code == code))
        sector = result.scalar_one_or_none()
        if sector is not None:
            return sector
        sector = Sector(code=code, name=label.strip() or "Unknown")
        self.db.add(sector)
        await self.db.flush()
        return sector

    async def get_by_code(self, code: str) -> Sector | None:
        code_n = normalize_code(code)
        result = await self.db.execute(select(Sector).where(Sector.code == code_n))
        return result.scalar_one_or_none()

    async def get_or_create_by_code(self, code: str, label: str | None = None) -> Sector:
        code_n = normalize_code(code) if code.strip() else "unknown"
        result = await self.db.execute(select(Sector).where(Sector.code == code_n))
        sector = result.scalar_one_or_none()
        if sector is not None:
            return sector
        sector = Sector(code=code_n, name=(label or code).strip() or "Unknown")
        self.db.add(sector)
        await self.db.flush()
        return sector
