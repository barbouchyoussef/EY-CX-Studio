from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecommendationOutput(Base):
    __tablename__ = "recommendation_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id: Mapped[int | None] = mapped_column(ForeignKey("capabilities.id"), nullable=True, index=True)
    maturity_level_id: Mapped[int | None] = mapped_column(ForeignKey("maturity_levels.id"), nullable=True, index=True)
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    assessment = relationship("Assessment")
