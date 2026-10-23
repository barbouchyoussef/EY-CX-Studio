from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssessmentInsight(Base):
    __tablename__ = "assessment_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id: Mapped[int | None] = mapped_column(ForeignKey("capabilities.id"), nullable=True, index=True)
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    maturity_level_id: Mapped[int | None] = mapped_column(ForeignKey("maturity_levels.id"), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    assessment = relationship("Assessment")
