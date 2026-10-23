from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import signature
from typing import Any, TypeVar, cast

from app.schemas.assessment import AnswerResponse


F = TypeVar("F", bound=Callable[..., Awaitable[AnswerResponse | None]])


def idempotent_request(func: F) -> F:
    """Run an async service method inside a UoW with idempotency caching."""

    method_signature = signature(func)

    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> AnswerResponse | None:
        bound = method_signature.bind(self, *args, **kwargs)
        bound.apply_defaults()

        assessment_id = int(bound.arguments["assessment_id"])
        idempotency_key = bound.arguments.get("idempotency_key")

        async with self.uow:
            if idempotency_key:
                cached = await self.idempotency.get(
                    assessment_id=assessment_id,
                    idempotency_key=str(idempotency_key),
                )
                if cached is not None:
                    return AnswerResponse(**cached.response_payload)

            response = await func(*bound.args, **bound.kwargs)

            if idempotency_key and response is not None:
                await self.idempotency.create(
                    assessment_id=assessment_id,
                    idempotency_key=str(idempotency_key),
                    response_payload=response.model_dump(),
                )

            return response

    return cast(F, wrapper)
