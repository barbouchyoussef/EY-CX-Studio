"""Covers the scraping job lifecycle.

The behaviour that matters: a run must survive the request that started it. Previously the
report was written only after `run_full_scrape` returned inside the HTTP handler, so a
closed tab or a proxy timeout discarded a scrape that had already been paid for on Apify.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.schemas.scraping import PlatformResult, ScrapeRequest, ScrapingResponse
from app.services.scraping import job_service


class FakeJob:
    """Stands in for the ScrapingJob row without needing a database."""

    def __init__(self, job_id: int = 1):
        self.id = job_id
        self.brand_name = "Orange"
        self.status = "pending"
        self.progress = "Queued"
        self.request = {}
        self.result = None
        self.error = None
        self.created_at = datetime.now(timezone.utc)
        self.finished_at = None


def _response(total: int = 5) -> ScrapingResponse:
    return ScrapingResponse(
        brand_name="Orange",
        scraped_at=datetime.now(timezone.utc).isoformat(),
        platforms=[PlatformResult(platform="Google Maps", status="success", review_count=total)],
        total_reviews=total,
    )


@pytest.fixture
def job(monkeypatch) -> FakeJob:
    """Route every _update call onto one in-memory job object."""
    fake = FakeJob()

    async def fake_update(job_id, **fields):
        assert job_id == fake.id
        for key, value in fields.items():
            setattr(fake, key, value)

    monkeypatch.setattr(job_service, "_update", fake_update)
    monkeypatch.setattr(job_service, "_job_semaphore", None)
    return fake


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Job execution                                                                 #
# --------------------------------------------------------------------------- #

def test_a_successful_run_is_archived_and_recorded(monkeypatch, job):
    archived: list[ScrapingResponse] = []

    async def fake_scrape(*_args, **_kwargs):
        return _response(7)

    async def fake_archive(response, owner_id=None):
        archived.append(response)

    monkeypatch.setattr(job_service, "run_full_scrape", fake_scrape)
    monkeypatch.setattr(job_service, "_archive_run", fake_archive)

    _run(job_service._run_job(job.id, ScrapeRequest(brand_name="Orange"), "token"))

    assert job.status == "succeeded"
    assert job.result["total_reviews"] == 7
    assert job.finished_at is not None
    assert job.error is None
    assert len(archived) == 1, "the report must be archived by the task, not by a poll"


def test_archiving_happens_even_though_nobody_is_polling(monkeypatch, job):
    """The consultant closing the tab is exactly the case the job exists to survive."""
    archived: list[str] = []

    async def fake_scrape(*_args, **_kwargs):
        return _response()

    async def fake_archive(response, owner_id=None):
        archived.append(response.brand_name)

    monkeypatch.setattr(job_service, "run_full_scrape", fake_scrape)
    monkeypatch.setattr(job_service, "_archive_run", fake_archive)

    # No polling of any kind occurs in this test.
    _run(job_service._run_job(job.id, ScrapeRequest(brand_name="Orange"), "token"))
    assert archived == ["Orange"]


def test_a_failed_scrape_is_recorded_not_swallowed(monkeypatch, job):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("Apify actor timed out")

    monkeypatch.setattr(job_service, "run_full_scrape", boom)

    _run(job_service._run_job(job.id, ScrapeRequest(brand_name="Orange"), "token"))

    assert job.status == "failed"
    assert "Apify actor timed out" in job.error
    assert job.finished_at is not None
    assert job.result is None


def test_an_archiving_failure_does_not_fail_the_job(monkeypatch, job):
    """The scrape already succeeded; a full disk must not throw that away.

    Eight minutes of Apify billing is not worth discarding because a log directory was
    unwritable, so the job still reports success and still carries the result.
    """

    async def fake_scrape(*_args, **_kwargs):
        return _response(6)

    async def broken_archive(_response, owner_id=None):
        raise OSError("disk full")

    monkeypatch.setattr(job_service, "run_full_scrape", fake_scrape)
    monkeypatch.setattr(job_service, "_archive_run", broken_archive)

    _run(job_service._run_job(job.id, ScrapeRequest(brand_name="Orange"), "token"))

    assert job.status == "succeeded"
    assert job.result["total_reviews"] == 6
    assert job.error is None


def test_the_job_reports_progress_while_running(monkeypatch, job):
    seen: list[str] = []

    async def fake_scrape(*_args, **_kwargs):
        seen.append(job.status)
        seen.append(job.progress)
        return _response()

    monkeypatch.setattr(job_service, "run_full_scrape", fake_scrape)
    monkeypatch.setattr(job_service, "_archive_run", lambda _r, owner_id=None: asyncio.sleep(0))

    _run(job_service._run_job(job.id, ScrapeRequest(brand_name="Orange"), "token"))
    assert seen[0] == "running"
    assert seen[1]  # a progress line is set before the work starts


# --------------------------------------------------------------------------- #
# Status payload                                                                #
# --------------------------------------------------------------------------- #

def test_status_omits_the_result_until_the_job_succeeds():
    job = FakeJob()
    job.status = "running"
    job.result = {"total_reviews": 3}
    payload = job_service.job_to_status(job)
    assert "result" not in payload, "polling should stay cheap while the job runs"
    assert payload["status"] == "running"
    assert payload["job_id"] == job.id


def test_status_inlines_the_result_once_it_exists():
    job = FakeJob()
    job.status = "succeeded"
    job.result = _response(4).model_dump(mode="json")
    payload = job_service.job_to_status(job)
    assert payload["result"]["total_reviews"] == 4


def test_parse_job_result_round_trips_the_response():
    job = FakeJob()
    job.status = "succeeded"
    job.result = _response(9).model_dump(mode="json")
    parsed = job_service.parse_job_result(job)
    assert isinstance(parsed, ScrapingResponse)
    assert parsed.total_reviews == 9


def test_parse_job_result_is_none_while_unfinished():
    job = FakeJob()
    job.status = "running"
    assert job_service.parse_job_result(job) is None


# --------------------------------------------------------------------------- #
# Concurrency + reference safety                                                #
# --------------------------------------------------------------------------- #

def test_concurrent_jobs_are_capped(monkeypatch):
    monkeypatch.setattr(job_service, "_job_semaphore", None)
    monkeypatch.setattr(job_service, "_MAX_CONCURRENT_JOBS", 2)

    peak = {"now": 0, "max": 0}

    async def slow_scrape(*_args, **_kwargs):
        peak["now"] += 1
        peak["max"] = max(peak["max"], peak["now"])
        await asyncio.sleep(0.02)
        peak["now"] -= 1
        return _response()

    async def noop_update(_job_id, **_fields):
        return None

    monkeypatch.setattr(job_service, "run_full_scrape", slow_scrape)
    monkeypatch.setattr(job_service, "_update", noop_update)
    monkeypatch.setattr(job_service, "_archive_run", lambda _r, owner_id=None: asyncio.sleep(0))

    async def main():
        await asyncio.gather(*(
            job_service._run_job(i, ScrapeRequest(brand_name=f"B{i}"), "token") for i in range(6)
        ))

    _run(main())
    assert peak["max"] <= 2, f"ran {peak['max']} scrapes at once"


def test_started_tasks_are_strongly_referenced(monkeypatch):
    """asyncio holds only weak references; an unreferenced task can be collected mid-run."""
    monkeypatch.setattr(job_service, "_job_semaphore", None)

    async def fake_scrape(*_args, **_kwargs):
        await asyncio.sleep(0.01)
        return _response()

    async def noop_update(_job_id, **_fields):
        return None

    monkeypatch.setattr(job_service, "run_full_scrape", fake_scrape)
    monkeypatch.setattr(job_service, "_update", noop_update)
    monkeypatch.setattr(job_service, "_archive_run", lambda _r, owner_id=None: asyncio.sleep(0))

    async def main():
        job_service.start_job(1, ScrapeRequest(brand_name="Orange"), "token")
        assert len(job_service._running_tasks) == 1
        await asyncio.sleep(0.05)
        # The done callback clears the set once the task finishes.
        assert len(job_service._running_tasks) == 0

    _run(main())
