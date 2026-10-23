"""The single door out to the language model.

Every model call in the platform goes through `MistralGateway.chat_messages`, and that is
deliberate rather than incidental: this is the seam that records usage into `llm_calls`, so a
caller that builds its own HTTP request is invisible to cost reporting. If a feature's spend does
not show up in the dashboard, this is the first thing to check.

The retry policy lives here too, once, for all 24 call sites -- what is worth retrying, how long
to wait, and why a rate limit backs off harder than a server error. The constants at the top carry
the reasoning; `_retry_delay` applies it.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Retry policy. Four attempts total, so three retries.
_MAX_ATTEMPTS = 4
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
# A rate limit needs a longer pause than a transient server error, so it backs off harder.
_BACKOFF_BASE_RATE_LIMIT = 1.5
_BACKOFF_BASE_SERVER_ERROR = 0.5
# Two different ceilings on purpose: the provider's own Retry-After is trusted further than a
# number we computed.
_MAX_RETRY_AFTER_SECONDS = 30
_MAX_BACKOFF_SECONDS = 20
# Transport failures (timeout, connection reset) get their own gentler curve -- nothing suggests
# the server is overloaded, only that this attempt did not arrive.
_TRANSPORT_BACKOFF_BASE = 0.5


def _retry_delay(status_code: int, attempt: int, retry_after: str) -> float:
    """Seconds to wait before retrying a failed response.

    The provider's `Retry-After` wins when it sends one, since it knows when its own limit
    resets. Otherwise back off exponentially from a base that depends on why the call failed.
    """
    if retry_after.isdigit():
        return min(int(retry_after), _MAX_RETRY_AFTER_SECONDS)
    base = _BACKOFF_BASE_RATE_LIMIT if status_code == 429 else _BACKOFF_BASE_SERVER_ERROR
    return min(base * (2 ** attempt), _MAX_BACKOFF_SECONDS)


class MistralGateway:
    """Low-level async gateway for Mistral chat completion calls.

    Every language-model call in the platform goes through here, which is also why this is the
    seam that records usage into `llm_calls`: a caller that bypasses it is invisible to cost
    reporting.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _benchmark_limiter(self):
        """The shared rate limiter for competitor benchmarking.

        Imported lazily because that module imports assessment code, and importing it at module
        scope would make the LLM gateway depend on a feature that uses it.
        """
        from app.services.assessment.reporting.provider_rate_limits import get_mistral_limiter

        return get_mistral_limiter(self.settings)

    async def _post_with_retries(
        self,
        client: Any,
        url: str,
        payload: dict[str, Any],
        rate_budget_scope: str | None,
    ) -> dict[str, Any]:
        """POST until it succeeds or the attempts run out; return the decoded body.

        Split out from `chat_messages` so the retry policy is readable on its own and the
        surrounding function is left doing one thing: recording what happened.
        """
        for attempt in range(_MAX_ATTEMPTS):
            last_attempt = attempt == _MAX_ATTEMPTS - 1
            try:
                # Benchmarking runs many calls at once, so it books capacity against a shared
                # budget before sending. Ordinary calls are not throttled here.
                if rate_budget_scope == "benchmark":
                    usage = await self._benchmark_limiter().acquire()
                    logger.warning(
                        "benchmark mistral request scope=%s per_second=%s per_minute=%s per_day=%s",
                        rate_budget_scope, usage.per_second_count, usage.per_minute_count,
                        usage.per_day_count,
                    )

                response = await client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {self.settings.mistral_api_key}"},
                )
                if response.status_code < 400:
                    return response.json()

                logger.warning(
                    "mistral request failed status=%s scope=%s model=%s body=%s",
                    response.status_code, rate_budget_scope, self.settings.mistral_model,
                    response.text[:800],
                )
                if response.status_code == 429 and rate_budget_scope == "benchmark":
                    await self._benchmark_limiter().note_rate_limited()

                if response.status_code in _RETRYABLE_STATUSES and not last_attempt:
                    await asyncio.sleep(
                        _retry_delay(response.status_code, attempt,
                                     response.headers.get("Retry-After", ""))
                    )
                    continue

                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning(
                    "mistral transport failure scope=%s model=%s attempt=%s/%s error=%s",
                    rate_budget_scope, self.settings.mistral_model, attempt + 1,
                    _MAX_ATTEMPTS, exc,
                )
                if last_attempt:
                    raise
                await asyncio.sleep(_TRANSPORT_BACKOFF_BASE * (2 ** attempt))

        raise RuntimeError("Mistral request failed after retries.")

    async def chat_messages(
        self,
        messages: list[dict[str, str]],
        *,
        rate_budget_scope: str | None = None,
    ) -> str:
        import time

        from app.services.observability.llm_metrics import log_llm_call

        start = time.monotonic()
        url = self.settings.mistral_base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.mistral_model,
            "temperature": self.settings.llm_temperature,
            "messages": messages,
        }
        if self.settings.llm_max_tokens is not None:
            payload["max_tokens"] = self.settings.llm_max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
                data = await self._post_with_retries(client, url, payload, rate_budget_scope)
        except Exception as exc:
            # Record the failed call for the error-rate charts, then let it propagate unchanged.
            log_llm_call(
                provider="mistral", model=self.settings.mistral_model, ok=False,
                error=str(exc), latency_ms=int((time.monotonic() - start) * 1000),
                input_messages=messages,
            )
            raise

        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        log_llm_call(
            provider="mistral", model=self.settings.mistral_model, ok=True,
            latency_ms=int((time.monotonic() - start) * 1000),
            usage=data.get("usage"), input_messages=messages, output_text=content,
        )
        return content


def build_mistral_gateway(settings: Settings) -> MistralGateway:
    return MistralGateway(settings=settings)
