"""Making a repeated answer submission harmless.

A client on a phone taps Send, the connection stalls, they tap again. Without this the same answer
is scored twice and the assessment advances two questions for one reply.

Every answer POST carries an `Idempotency-Key` the browser generates per submission. The first
request stores its key alongside the response it produced; a second request with the same key gets
that stored response back rather than being processed again. The key is scoped to the assessment,
so keys never need to be globally unique.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment_idempotency import AssessmentIdempotency


class AssessmentIdempotencyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, assessment_id: int, idempotency_key: str) -> AssessmentIdempotency | None:
        result = await self.db.execute(
            select(AssessmentIdempotency).where(
                AssessmentIdempotency.assessment_id == assessment_id,
                AssessmentIdempotency.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, assessment_id: int, idempotency_key: str, response_payload: dict) -> AssessmentIdempotency:
        row = AssessmentIdempotency(
            assessment_id=assessment_id,
            idempotency_key=idempotency_key,
            response_payload=response_payload,
        )
        self.db.add(row)
        await self.db.flush()
        return row
