from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AxisMaturityContent(Base):
    __tablename__ = "axis_maturity_content"
    __table_args__ = (
        UniqueConstraint("axis_id", "maturity_level_id", name="axis_maturity_content_axis_level_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    axis_id: Mapped[int] = mapped_column(ForeignKey("axes.id", ondelete="CASCADE"), nullable=False, index=True)
    maturity_level_id: Mapped[int] = mapped_column(
        ForeignKey("maturity_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    axis_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    axis_panel_copy: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    axis = relationship("Axis")
    maturity_level = relationship("MaturityLevel")
