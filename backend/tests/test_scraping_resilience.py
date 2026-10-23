"""Covers transient-failure handling and credential redaction in the scrapers.

Two real incidents motivated these:
  - a 500 from Apify's status endpoint aborted an entire run that was still executing
    (and already billed) on Apify's side;
  - the API token was passed as a query parameter, so httpx put it in the exception text,
    which is persisted to the report JSON, the job row and the browser.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services.scraping import scraping_service
from app.services.scraping.scraping_service import _redact, _request_with_retry, _run_actor


# --------------------------------------------------------------------------- #
# Redaction                                                                     #
# --------------------------------------------------------------------------- #

def test_the_reported_error_message_no_longer_leaks_the_token():
    leaked = (
        "Server error '500 Internal Server Error' for url "
        "'https://api.apify.com/v2/actor-runs/3lblIu4NbWoXdZA6l"
        "?token=apify_api_dummyToken1234567890abcdef'"
    )
    safe = _redact(leaked)
    assert "apify_api_dummyToken1234567890abcdef" not in safe
    assert "***" in safe
    # The diagnostic value is preserved.
    assert "500" in safe and "actor-runs/3lblIu4NbWoXdZA6l" in safe


@pytest.mark.parametrize(
    "raw",
    [
        "https://x.com/a?token=supersecret123",
        "https://x.com/a?key=supersecret123",
        "https://x.com/a?b=1&api_key=supersecret123",
        "Authorization: Bearer supersecret123",
        "apify_api_supersecret123",
    ],
)
def test_credentials_are_stripped_in_every_shape(raw):
    assert "supersecret123" not in _redact(raw)


def test_redaction_leaves_ordinary_text_alone():
    msg = "Actor run abc123 finished with status: FAILED"
    assert _redact(msg) == msg
    assert _redact("") == ""


def test_the_token_is_never_placed_in_a_url():
    """Bearer auth is what makes the leak structurally impossible, not the regex."""
    headers = scraping_service._apify_headers("apify_api_secret")
    assert headers["Authorization"] == "Bearer apify_api_secret"


# --------------------------------------------------------------------------- #
# Retry behaviour                                                               #
# --------------------------------------------------------------------------- #

class _FakeClient:
    """Replays a scripted sequence of responses/exceptions."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def _next(self, url):
        self.calls += 1
        item = self.script.pop(0) if self.script else self.script_default
        if isinstance(item, Exception):
            raise item
        request = httpx.Request("GET", url)
        return httpx.Response(item[0], json=item[1], request=request)

    async def request(self, method, url, headers=None, json=None):
        return self._next(url)

    async def get(self, url, headers=None):
        return self._next(url)


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """Backoff is real; waiting for it in tests is not."""
    async def instant(_seconds):
        return None

    monkeypatch.setattr(scraping_service.asyncio, "sleep", instant)


def test_a_transient_500_is_retried_then_succeeds():
    client = _FakeClient([(500, {}), (503, {}), (200, {"ok": True})])
    resp = asyncio.run(_request_with_retry(client, "GET", "https://api/x", what="test"))
    assert resp.json() == {"ok": True}
    assert client.calls == 3


def test_a_network_error_is_retried():
    client = _FakeClient([httpx.ConnectError("boom"), (200, {"ok": True})])
    resp = asyncio.run(_request_with_retry(client, "GET", "https://api/x", what="test"))
    assert resp.json() == {"ok": True}


def test_a_client_error_fails_immediately_without_burning_retries():
    """Retrying a 401 or 404 only wastes time -- it will never start working."""
    client = _FakeClient([(404, {})])
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_request_with_retry(client, "GET", "https://api/x", what="test"))
    assert client.calls == 1


def test_persistent_failure_gives_up_with_a_redacted_message():
    client = _FakeClient([(500, {})] * 10)
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            _request_with_retry(
                client, "GET", "https://api/x?token=apify_api_secret123", what="test"
            )
        )
    assert client.calls == scraping_service._MAX_ATTEMPTS
    assert "apify_api_secret123" not in str(exc.value)


# --------------------------------------------------------------------------- #
# The actual incident: a 500 while polling a healthy run                         #
# --------------------------------------------------------------------------- #

class _ApifyClient:
    """Starts a run, fails the first status polls, then reports SUCCEEDED."""

    def __init__(self, poll_failures, poll_status=500):
        self.poll_failures = poll_failures
        self.poll_status = poll_status
        self.polls = 0

    async def request(self, method, url, headers=None, json=None):
        assert "token=" not in url, "the token must never appear in a URL"
        assert headers and headers.get("Authorization", "").startswith("Bearer ")
        request = httpx.Request(method, url)
        if "/acts/" in url:
            return httpx.Response(
                201, json={"data": {"id": "run1", "defaultDatasetId": "ds1"}}, request=request
            )
        if "/datasets/" in url:
            return httpx.Response(200, json=[{"text": "une vraie review"}], request=request)
        raise AssertionError(url)

    async def get(self, url, headers=None):
        assert "token=" not in url, "the token must never appear in a URL"
        request = httpx.Request("GET", url)
        if "/actor-runs/" in url:
            self.polls += 1
            if self.polls <= self.poll_failures:
                return httpx.Response(self.poll_status, json={}, request=request)
            return httpx.Response(200, json={"data": {"status": "SUCCEEDED"}}, request=request)
        if "/datasets/" in url:
            return httpx.Response(200, json=[{"text": "une vraie review"}], request=request)
        raise AssertionError(url)


def test_a_500_while_polling_does_not_discard_a_running_scrape():
    """The exact reported failure: the run is healthy, only our status call blipped."""
    client = _ApifyClient(poll_failures=3)
    items = asyncio.run(_run_actor(client, "some~actor", "apify_api_secret", {}, timeout=120))
    assert items == [{"text": "une vraie review"}]
    assert client.polls == 4  # three failures survived, fourth succeeded


def test_polling_survives_a_gateway_outage():
    client = _ApifyClient(poll_failures=6, poll_status=502)
    items = asyncio.run(_run_actor(client, "some~actor", "apify_api_secret", {}, timeout=300))
    assert items == [{"text": "une vraie review"}]


def test_an_auth_failure_while_polling_stops_immediately():
    """A 401 will not fix itself; failing fast beats polling for eight minutes."""
    client = _ApifyClient(poll_failures=1, poll_status=401)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_run_actor(client, "some~actor", "apify_api_secret", {}, timeout=120))
