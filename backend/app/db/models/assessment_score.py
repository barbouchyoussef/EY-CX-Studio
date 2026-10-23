from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssessmentScore(Base):
    __tablename__ = "assessment_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "capability_id", name="assessment_scores_assessment_id_capability_id_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), nullable=False, index=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id"), nullable=False, index=True)
    maturity_level_id: Mapped[int | None] = mapped_column(ForeignKey("maturity_levels.id"), nullable=True, index=True)
    assessment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_assessed", index=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    assessment = relationship("Assessment", back_populates="scores")
    capability = relationship("Capability", back_populates="assessment_links")
