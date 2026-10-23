from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CapabilityMaturityContent(Base):
    __tablename__ = "capability_maturity_content"
    __table_args__ = (
        UniqueConstraint(
            "capability_id",
            "maturity_level_id",
            name="capability_maturity_content_capability_level_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    capability_id: Mapped[int] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    maturity_level_id: Mapped[int] = mapped_column(
        ForeignKey("maturity_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    modal_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    capability = relationship("Capability")
    maturity_level = relationship("MaturityLevel")
