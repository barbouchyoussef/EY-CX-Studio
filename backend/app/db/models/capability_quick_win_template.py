from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CapabilityQuickWinTemplate(Base):
    __tablename__ = "capability_quick_win_templates"
    __table_args__ = (
        UniqueConstraint(
            "capability_id",
            "maturity_level_id",
            name="capability_quick_win_templates_capability_id_maturity_level_id_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, index=True)
    maturity_level_id: Mapped[int] = mapped_column(
        ForeignKey("maturity_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quick_win_guideline: Mapped[str] = mapped_column(Text, nullable=False)
    after_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeline_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    capability = relationship("Capability")
    maturity_level = relationship("MaturityLevel")
