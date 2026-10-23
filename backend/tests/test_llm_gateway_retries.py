"""The retry policy behind every language-model call in the platform.

`MistralGateway.chat_messages` has 24 call sites across the assessment, desk-research, scraping
and interview modules. Until now none of them were covered here: every existing test replaces the
gateway with a fake, so the real retry logic had never been executed by a test at all.

That is a bad place to have no coverage. What is checked below is the behaviour a failure depends
on — that a rate limit is retried and a bad request is not, that the provider's own `Retry-After`
is honoured, and that the loop gives up rather than hanging.

`asyncio.sleep` is patched throughout, so the tests assert on the delays that *would* have been
taken instead of waiting for them.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services.llm.core.gateway import (
    _BACKOFF_BASE_RATE_LIMIT,
    _MAX_ATTEMPTS,
    _MAX_BACKOFF_SECONDS,
    _MAX_RETRY_AFTER_SECONDS,
    MistralGateway,
    _retry_delay,
)


# ── the delay policy ────────────────────────────────────────────────────────────────────────


def test_a_rate_limit_backs_off_harder_than_a_server_error():
    """429 means "you are asking too fast"; 503 usually means "try again shortly"."""
    assert _retry_delay(429, 0, "") > _retry_delay(503, 0, "")


def test_backoff_doubles_each_attempt():
    delays = [_retry_delay(429, attempt, "") for attempt in range(4)]
    assert delays == [1.5, 3.0, 6.0, 12.0]
    assert delays == [_BACKOFF_BASE_RATE_LIMIT * 2 ** a for a in range(4)]


def test_backoff_is_capped():
    """Without a ceiling, attempt 6 would wait 96 seconds and hold a request open."""
    assert _retry_delay(429, 20, "") == _MAX_BACKOFF_SECONDS


def test_retry_after_wins_over_computed_backoff():
    """The provider knows when its own limit resets; we do not."""
    assert _retry_delay(429, 3, "2") == 2


def test_retry_after_is_capped_higher_than_computed_backoff():
    """Deliberate asymmetry: a number the provider sent is trusted further than one we invented."""
    assert _retry_delay(429, 0, "999") == _MAX_RETRY_AFTER_SECONDS
    assert _MAX_RETRY_AFTER_SECONDS > _MAX_BACKOFF_SECONDS


def test_a_non_numeric_retry_after_falls_back_to_backoff():
    """Retry-After may be an HTTP date, which this does not parse."""
    assert _retry_delay(429, 0, "Wed, 21 Oct 2026 07:28:00 GMT") == 1.5


# ── the retry loop ──────────────────────────────────────────────────────────────────────────


class _Response:
    def __init__(self, status_code: int, body: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}
        self.text = str(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"{self.status_code}", request=None, response=None)


class _Client:
    """Returns the queued responses in order, recording how many calls were made."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0

    async def post(self, *_args, **_kwargs):
        self.calls += 1
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def gateway():
    return MistralGateway(settings=SimpleNamespace(mistral_api_key="k", mistral_model="m"))


@pytest.fixture
def slept(monkeypatch):
    """Collect the delays instead of waiting for them."""
    recorded: list[float] = []

    async def _fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return recorded


def _run(coro):
    return asyncio.run(coro)


def test_a_successful_call_does_not_retry(gateway, slept):
    client = _Client(_Response(200, {"ok": True}))
    body = _run(gateway._post_with_retries(client, "u", {}, None))
    assert body == {"ok": True}
    assert client.calls == 1
    assert slept == []


def test_a_rate_limit_is_retried_then_succeeds(gateway, slept):
    client = _Client(_Response(429), _Response(200, {"ok": True}))
    body = _run(gateway._post_with_retries(client, "u", {}, None))
    assert body == {"ok": True}
    assert client.calls == 2
    assert slept == [1.5]


def test_retry_after_header_is_used(gateway, slept):
    client = _Client(_Response(429, headers={"Retry-After": "7"}), _Response(200, {"ok": True}))
    _run(gateway._post_with_retries(client, "u", {}, None))
    assert slept == [7]


def test_a_bad_request_is_not_retried(gateway, slept):
    """400 will fail identically every time; retrying wastes the caller's time."""
    client = _Client(_Response(400))
    with pytest.raises(httpx.HTTPStatusError):
        _run(gateway._post_with_retries(client, "u", {}, None))
    assert client.calls == 1
    assert slept == []


def test_it_gives_up_after_the_attempt_limit(gateway, slept):
    """The last attempt must not sleep -- there is nothing left to wait for."""
    client = _Client(*[_Response(503) for _ in range(_MAX_ATTEMPTS)])
    with pytest.raises(httpx.HTTPStatusError):
        _run(gateway._post_with_retries(client, "u", {}, None))
    assert client.calls == _MAX_ATTEMPTS
    assert len(slept) == _MAX_ATTEMPTS - 1


def test_a_timeout_is_retried(gateway, slept):
    client = _Client(httpx.TimeoutException("timed out"), _Response(200, {"ok": True}))
    body = _run(gateway._post_with_retries(client, "u", {}, None))
    assert body == {"ok": True}
    assert client.calls == 2


def test_a_persistent_timeout_propagates(gateway, slept):
    """The caller must see the transport error, not a generic failure."""
    client = _Client(*[httpx.TimeoutException("timed out") for _ in range(_MAX_ATTEMPTS)])
    with pytest.raises(httpx.TimeoutException):
        _run(gateway._post_with_retries(client, "u", {}, None))
    assert client.calls == _MAX_ATTEMPTS
