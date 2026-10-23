"""Per-analysis share (mirrors migration 047)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisShare(Base):
    __tablename__ = "analysis_shares"
    __table_args__ = (UniqueConstraint("kind", "ref_id", "shared_with"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(255), nullable=False)
    shared_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    shared_with: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
