"""Regions: reference data the admin screens maintain.

Optional on an assessment -- a client's region sharpens the competitor benchmark but the
diagnostic runs without it.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.region import Region


class RegionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_options(self) -> list[Region]:
        result = await self.db.execute(select(Region).order_by(Region.name.asc()))
        return list(result.scalars().all())

    async def get_by_code_or_name(self, value: str | None) -> Region | None:
        normalized = (value or "").strip()
        if not normalized:
            return None
        result = await self.db.execute(
            select(Region).where(
                func.lower(Region.name) == normalized.lower()
            )
        )
        return result.scalar_one_or_none()
