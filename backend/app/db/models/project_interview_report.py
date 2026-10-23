"""The consolidated interview report for a project (schema owned by migration 057)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectInterviewReport(Base):
    __tablename__ = "project_interview_reports"

    # One report per project: regenerating replaces it, so the UI never has to choose between
    # versions and "generate" and "regenerate" are the same write.
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    overview: Mapped[dict] = mapped_column(JSONB, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # {"guide_ids": [...], "assessment_ids": [...]} at generation time -- what the report was
    # built from, so the UI can tell the user it is out of date.
    sources: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    generated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
