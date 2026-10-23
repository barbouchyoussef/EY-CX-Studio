from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maturity_level import MaturityLevel


class MaturityLevelCache:
    """Request-scoped cache for maturity level reference data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._labels: dict[int, str] | None = None
        self._numbers: dict[int, int] | None = None

    async def get_labels(self) -> dict[int, str]:
        await self._ensure_loaded()
        return self._labels or {}

    async def get_numbers(self) -> dict[int, int]:
        await self._ensure_loaded()
        return self._numbers or {}

    def clear(self) -> None:
        self._labels = None
        self._numbers = None

    async def _ensure_loaded(self) -> None:
        if self._labels is not None and self._numbers is not None:
            return

        result = await self.db.execute(select(MaturityLevel))
        rows = result.scalars().all()
        self._labels = {int(row.id): str(row.label) for row in rows}
        self._numbers = {int(row.id): int(row.level_number) for row in rows}
