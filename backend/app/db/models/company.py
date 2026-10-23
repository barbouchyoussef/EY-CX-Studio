from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True, index=True)
    size_id: Mapped[int | None] = mapped_column(ForeignKey("company_sizes.id"), nullable=True, index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True, index=True)

    assessments = relationship("Assessment", back_populates="company")
    sector = relationship("Sector", back_populates="companies")
    company_size = relationship("CompanySize", back_populates="companies", foreign_keys=[size_id])
    region_ref = relationship("Region", back_populates="companies", foreign_keys=[region_id])
