"""Company size bands: reference data the admin screens maintain.

Read constantly (every assessment resolves one) and written rarely (only through the admin
dashboard), so the shape here is list-and-lookup with the writes present but incidental.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_size import CompanySize
from app.repositories.sector_repository import normalize_code


class CompanySizeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_options(self, limit: int = 200) -> list[CompanySize]:
        result = await self.db.execute(
            select(CompanySize)
            .where(CompanySize.code.notin_(["unknown", "string"]))
            .order_by(CompanySize.name.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create(self, label: str) -> CompanySize:
        code = normalize_code(label) if label.strip() else "unknown"
        result = await self.db.execute(select(CompanySize).where(CompanySize.code == code))
        size = result.scalar_one_or_none()
        if size is not None:
            return size
        size = CompanySize(code=code, name=label.strip() or "Unknown")
        self.db.add(size)
        await self.db.flush()
        return size

    async def get_by_code(self, code: str) -> CompanySize | None:
        code_n = normalize_code(code)
        result = await self.db.execute(select(CompanySize).where(CompanySize.code == code_n))
        return result.scalar_one_or_none()

    async def get_or_create_by_code(self, code: str, label: str | None = None) -> CompanySize:
        code_n = normalize_code(code) if code.strip() else "unknown"
        result = await self.db.execute(select(CompanySize).where(CompanySize.code == code_n))
        size = result.scalar_one_or_none()
        if size is not None:
            return size
        size = CompanySize(code=code_n, name=(label or code).strip() or "Unknown")
        self.db.add(size)
        await self.db.flush()
        return size
