from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession


class AsyncUnitOfWork:
    """Async-compatible transaction boundary for the current SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def __aenter__(self) -> "AsyncUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            await self.db.rollback()
            return False

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return False
