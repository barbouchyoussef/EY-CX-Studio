"""Per-provider rate limiting: a rolling token budget, bounded concurrency, jittered backoff.

Sized from measurement rather than guesswork. Mistral served 32,650 tokens in 43 s before
returning 429 (~45k tokens/minute), and lost 9 of 20 calls when four requests ran concurrently;
at concurrency 1 under a 30k budget it completed 15/15. Every rate-limit failure observed while
building the issue-log pipeline came from our own throughput, never from provider instability.

Generic on purpose: any module that fans out LLM calls should route through ``guarded``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Statuses worth retrying. A 400/401/404 will never succeed on a second attempt, so retrying
# them only delays the failover to a provider that might work.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}

# Some 429s are permanent. An exhausted balance and an exceeded rate limit share a status code,
# but waiting helps only one of them: an unfunded key returned 429 on every call, and each call
# then burned four retries with backoff before failing over -- turning a run into ten wasted
# minutes. These markers in the error body mean "stop asking".
_PERMANENT_MARKERS = (
    "no credits remaining",
    "insufficient_quota",
    "insufficient quota",
    "exceeded your current quota",
    "billing_hard_limit_reached",
    "account is not active",
    "payment required",
)


def is_permanent(status: int, error: str) -> bool:
    """A failure that will still be a failure in sixty seconds."""
    if status and status not in RETRYABLE_STATUS:
        return True
    body = (error or "").casefold()
    return any(marker in body for marker in _PERMANENT_MARKERS)


@dataclass
class TokenBucket:
    """Rolling-window token budget. Callers reserve *before* dispatching, so a burst of parallel
    requests cannot collectively overshoot the window."""

    capacity: int
    window: float = 60.0
    _events: list[tuple[float, int]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def reserve(self, tokens: int) -> float:
        """Block until ``tokens`` fit inside the window. Returns the seconds spent waiting."""
        waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                self._events = [(t, n) for t, n in self._events if now - t < self.window]
                used = sum(n for _, n in self._events)
                # The `not self._events` arm lets a single oversized request through rather than
                # deadlocking forever on a payload larger than the whole budget.
                if used + tokens <= self.capacity or not self._events:
                    self._events.append((now, tokens))
                    return waited
                oldest = min(t for t, _ in self._events)
                sleep_for = max(0.25, self.window - (now - oldest) + 0.1)
            await asyncio.sleep(sleep_for)
            waited += sleep_for


@dataclass
class ProviderLimits:
    tokens_per_min: int
    max_concurrent: int
    bucket: TokenBucket = field(init=False)
    sem: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.bucket = TokenBucket(capacity=self.tokens_per_min)
        self.sem = asyncio.Semaphore(self.max_concurrent)


def _limits_from_env() -> dict[str, ProviderLimits]:
    """Budgets are env-tunable so a plan upgrade does not need a code change."""

    def _int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, "").strip() or default)
        except ValueError:
            return default

    return {
        "openai": ProviderLimits(_int("OPENAI_TOKENS_PER_MIN", 900_000),
                                 _int("OPENAI_MAX_CONCURRENT", 6)),
        "mistral": ProviderLimits(_int("MISTRAL_TOKENS_PER_MIN", 30_000),
                                  _int("MISTRAL_MAX_CONCURRENT", 1)),
        "gemini": ProviderLimits(_int("GEMINI_TOKENS_PER_MIN", 120_000),
                                 _int("GEMINI_MAX_CONCURRENT", 2)),
    }


_LIMITS: dict[str, ProviderLimits] | None = None


def limits_for(provider: str) -> ProviderLimits:
    global _LIMITS
    if _LIMITS is None:
        _LIMITS = _limits_from_env()
    if provider not in _LIMITS:
        _LIMITS[provider] = ProviderLimits(600_000, 4)
    return _LIMITS[provider]


def reset_limits() -> None:
    """Drop cached budgets. Tests use this after changing the environment."""
    global _LIMITS
    _LIMITS = None


@dataclass
class Attempt:
    """What happened, in enough detail to debug a slow or failing run after the fact."""
    provider: str
    model: str
    ok: bool
    status: int = 0
    retries: int = 0
    waited_s: float = 0.0
    elapsed_s: float = 0.0
    error: str = ""


async def guarded(
    provider: str,
    model: str,
    est_tokens: int,
    call: Callable[[], Awaitable[T]],
    *,
    is_ok: Callable[[T], bool],
    status_of: Callable[[T], int],
    error_of: Callable[[T], str],
    attempts: int = 4,
    label: str = "",
) -> tuple[T | None, Attempt]:
    """Run ``call`` inside the provider's budget and concurrency cap, retrying transient errors.

    Backoff is exponential with full jitter. A fixed schedule synchronises every worker onto the
    same retry instant, which reproduces the rate limit that caused the retry in the first place.
    """
    lim = limits_for(provider)
    started = time.monotonic()
    waited = 0.0
    made = 0                      # actual attempts, so the run record is not fiction
    last: T | None = None
    last_status = 0
    last_error = "no attempt made"

    for attempt in range(attempts):
        waited += await lim.bucket.reserve(est_tokens)
        made += 1
        async with lim.sem:
            try:
                result = await call()
            except Exception as exc:  # a transport error is retryable like a 5xx
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("%s: %s/%s raised %s", label, provider, model, last_error)
                if attempt < attempts - 1:
                    await asyncio.sleep(random.uniform(0.5, min(60.0, 5.0 * 2 ** attempt)))
                    continue
                break

        last = result
        if is_ok(result):
            return result, Attempt(provider, model, True, status_of(result), made - 1, waited,
                                   time.monotonic() - started)

        last_status = status_of(result)
        last_error = error_of(result)
        if is_permanent(last_status, last_error):
            # Fail over immediately. Retrying a dead key or a rejected request only delays the
            # provider that might actually work.
            logger.warning("%s: %s/%s failed permanently (%s); failing over without retry",
                           label, provider, model, last_error[:120])
            break
        if attempt < attempts - 1:
            delay = min(60.0, 5.0 * 2 ** attempt)
            await asyncio.sleep(random.uniform(0.5 * delay, delay))

    return last, Attempt(provider, model, False, last_status, max(0, made - 1), waited,
                         time.monotonic() - started, last_error[:300])
