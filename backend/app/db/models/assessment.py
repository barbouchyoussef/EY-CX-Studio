from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    current_axis_id: Mapped[int | None] = mapped_column(ForeignKey("axes.id"), nullable=True, index=True)
    overall_maturity_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("maturity_levels.id"), nullable=True, index=True
    )
    overall_maturity_band: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_axis_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_axis_low_quality_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_followup_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_question: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pending_options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pending_focus_capability_id: Mapped[int | None] = mapped_column(
        ForeignKey("capabilities.id"), nullable=True, index=True
    )
    conversation_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="intro")
    clarification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_profile: Mapped[str] = mapped_column(String(40), nullable=False, default="consultant_guided")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    executive_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    leaders_snapshot_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    leaders_snapshot_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    leaders_snapshot_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leaders_snapshot_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="assessments")
    current_axis = relationship("Axis")
    pending_focus_capability = relationship("Capability", foreign_keys=[pending_focus_capability_id])
    scores = relationship("AssessmentScore", back_populates="assessment", cascade="all, delete-orphan")
    answers = relationship("AssessmentAnswer", back_populates="assessment", cascade="all, delete-orphan")
