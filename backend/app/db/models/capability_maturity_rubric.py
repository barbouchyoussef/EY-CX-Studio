from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CapabilityMaturityRubric(Base):
    __tablename__ = "capability_maturity_rubrics"
    __table_args__ = (
        UniqueConstraint("capability_id", "maturity_level_id", name="capability_maturity_rubrics_capability_id_maturity_level_id_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, index=True)
    maturity_level_id: Mapped[int] = mapped_column(
        ForeignKey("maturity_levels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    card_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    capability = relationship("Capability")
    maturity_level = relationship("MaturityLevel")
