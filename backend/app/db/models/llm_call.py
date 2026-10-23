from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMCall(Base):
    """One LLM API call, recorded best-effort for observability (cost, latency, errors).

    Written from the LLM gateway on its own short-lived session; a logging failure must never
    break the call it describes. The schema is owned by migrations/051_create_llm_calls.sql.
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    feature: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # run | assistant | util
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="mistral")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ref_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
