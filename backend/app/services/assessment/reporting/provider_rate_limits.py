from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings

logger = logging.getLogger(__name__)


class BenchmarkProviderUnavailable(RuntimeError):
    """Raised when benchmark provider calls should stop for the current job."""


@dataclass(frozen=True)
class ProviderUsageSnapshot:
    provider: str
    per_second_count: int
    per_minute_count: int
    per_day_count: int


class ProviderRateLimiter:
    def __init__(
        self,
        *,
        provider: str,
        max_requests_per_second: int,
        max_requests_per_minute: int,
        max_requests_per_day: int,
        cooldown_seconds: float,
    ) -> None:
        self.provider = provider
        self.max_requests_per_second = max_requests_per_second
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        self.cooldown_seconds = cooldown_seconds
        self._lock = asyncio.Lock()
        self._recent_second: deque[float] = deque()
        self._recent_minute: deque[float] = deque()
        self._day_key = datetime.now(timezone.utc).date().isoformat()
        self._day_count = 0
        self._cooldown_until = 0.0

    async def acquire(self) -> ProviderUsageSnapshot:
        while True:
            wait_seconds = 0.0
            async with self._lock:
                now = time.monotonic()
                self._reset_day_if_needed()
                self._prune(now)

                if self._cooldown_until > now:
                    raise BenchmarkProviderUnavailable(
                        f"{self.provider} cooling down for {self._cooldown_until - now:.2f}s"
                    )
                if self._day_count >= self.max_requests_per_day:
                    raise BenchmarkProviderUnavailable(
                        f"{self.provider} daily request budget exhausted"
                    )

                second_count = len(self._recent_second)
                minute_count = len(self._recent_minute)
                if second_count < self.max_requests_per_second and minute_count < self.max_requests_per_minute:
                    self._recent_second.append(now)
                    self._recent_minute.append(now)
                    self._day_count += 1
                    return ProviderUsageSnapshot(
                        provider=self.provider,
                        per_second_count=second_count + 1,
                        per_minute_count=minute_count + 1,
                        per_day_count=self._day_count,
                    )

                second_wait = 0.0
                minute_wait = 0.0
                if second_count >= self.max_requests_per_second and self._recent_second:
                    second_wait = max(0.0, 1.0 - (now - self._recent_second[0]))
                if minute_count >= self.max_requests_per_minute and self._recent_minute:
                    minute_wait = max(0.0, 60.0 - (now - self._recent_minute[0]))
                wait_seconds = max(second_wait, minute_wait, 0.05)

            logger.warning(
                "benchmark provider wait provider=%s wait_seconds=%.2f",
                self.provider,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    async def note_rate_limited(self) -> None:
        async with self._lock:
            self._cooldown_until = max(self._cooldown_until, time.monotonic() + self.cooldown_seconds)
            self._reset_day_if_needed()
            logger.warning(
                "benchmark provider cooldown entered provider=%s cooldown_seconds=%.2f per_second=%s per_minute=%s per_day=%s",
                self.provider,
                self.cooldown_seconds,
                len(self._recent_second),
                len(self._recent_minute),
                self._day_count,
            )

    def _prune(self, now: float) -> None:
        while self._recent_second and now - self._recent_second[0] >= 1.0:
            self._recent_second.popleft()
        while self._recent_minute and now - self._recent_minute[0] >= 60.0:
            self._recent_minute.popleft()

    def _reset_day_if_needed(self) -> None:
        day_key = datetime.now(timezone.utc).date().isoformat()
        if day_key != self._day_key:
            self._day_key = day_key
            self._day_count = 0


_langsearch_limiter: ProviderRateLimiter | None = None
_mistral_limiter: ProviderRateLimiter | None = None


def get_langsearch_limiter(settings: Settings) -> ProviderRateLimiter:
    global _langsearch_limiter
    if _langsearch_limiter is None:
        _langsearch_limiter = ProviderRateLimiter(
            provider="langsearch",
            max_requests_per_second=settings.benchmark_langsearch_max_requests_per_second,
            max_requests_per_minute=settings.benchmark_langsearch_max_requests_per_minute,
            max_requests_per_day=settings.benchmark_langsearch_max_requests_per_day,
            cooldown_seconds=settings.benchmark_provider_cooldown_seconds,
        )
    return _langsearch_limiter


def get_mistral_limiter(settings: Settings) -> ProviderRateLimiter:
    global _mistral_limiter
    if _mistral_limiter is None:
        _mistral_limiter = ProviderRateLimiter(
            provider="mistral",
            max_requests_per_second=settings.benchmark_mistral_max_requests_per_second,
            max_requests_per_minute=settings.benchmark_mistral_max_requests_per_minute,
            max_requests_per_day=settings.benchmark_mistral_max_requests_per_day,
            cooldown_seconds=settings.benchmark_provider_cooldown_seconds,
        )
    return _mistral_limiter
