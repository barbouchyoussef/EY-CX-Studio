from sqlalchemy import SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaturityLevel(Base):
    __tablename__ = "maturity_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    level_number: Mapped[int] = mapped_column(SmallInteger, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
