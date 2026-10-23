"""Runs a social scrape as a background job instead of inside the HTTP request.

A full run takes up to 8 minutes: three Apify actors, then classification, then report
generation. Holding the request open for that long fails at any reverse proxy (nginx and
ALB default to 60s, Azure App Service to 230s) and throws away a run the client has already
paid Apify for, because nothing was persisted until the handler returned.

The job row is the unit of durability: `/run` creates it and returns immediately, the task
updates it as work lands, and the browser polls. Closing the tab no longer cancels anything.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models.company import Company
from app.db.models.company_size import CompanySize
from app.db.models.scraping_job import ScrapingJob
from app.db.session import SessionLocal
from app.schemas.scraping import ScrapeRequest, ScrapingResponse
from app.services.scraping.scraping_service import run_full_scrape

logger = logging.getLogger(__name__)

# Bounds concurrent scrapes per process. Each run holds three Apify actor runs plus several
# Mistral calls, so letting these pile up would exhaust rate limits and memory alike.
_MAX_CONCURRENT_JOBS = 2
_job_semaphore: asyncio.Semaphore | None = None

# Keeps a strong reference to in-flight tasks: asyncio only holds weak references, so a task
# that nothing references can be garbage-collected mid-run.
_running_tasks: set[asyncio.Task] = set()


def _get_semaphore() -> asyncio.Semaphore:
    global _job_semaphore
    if _job_semaphore is None:
        _job_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_JOBS)
    return _job_semaphore


async def create_job(db, req: ScrapeRequest, owner_id: int | None = None) -> ScrapingJob:
    """Persist a queued job. The caller commits nothing else -- the row must exist before
    the task starts, or a fast failure would have nowhere to report itself."""
    job = ScrapingJob(
        owner_id=owner_id,
        brand_name=req.brand_name.strip(),
        status="pending",
        progress="Queued",
        request=req.model_dump(mode="json"),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _update(job_id: int, **fields) -> None:
    """Write progress from inside the task, on its own short-lived session.

    The request's session is long gone by the time this runs, and a session held open for
    the whole 8 minutes would pin a pooled connection for no reason.
    """
    try:
        async with SessionLocal() as db:
            job = await db.get(ScrapingJob, job_id)
            if job is None:
                logger.warning("Scraping job %s vanished mid-run", job_id)
                return
            for key, value in fields.items():
                setattr(job, key, value)
            await db.commit()
    except Exception:
        # Never let a bookkeeping failure kill the scrape itself.
        logger.exception("Could not update scraping job %s", job_id)


def _determine_sector_id(brand: str) -> int:
    brand_lower = brand.lower()
    if any(k in brand_lower for k in ("telecom", "orange", "ooredoo", "telephony")):
        return 7  # Telecom
    if any(k in brand_lower for k in ("bank", "banque", "finance")):
        return 5  # Banking
    if any(k in brand_lower for k in ("assur", "insur")):
        return 6  # Insurance
    if any(k in brand_lower for k in ("shop", "store", "retail")):
        return 3  # Retail
    if any(k in brand_lower for k in ("ecom", "online")):
        return 4  # E-commerce
    return 1  # Unknown


async def _archive_run(response: ScrapingResponse, owner_id: int | None = None) -> None:
    """Write the report to disk and register the company for the dropdown.

    Deliberately inside the task rather than on a poll: a consultant who closes the tab
    still gets the run archived, which is the whole reason the job exists. Failures here are
    logged and swallowed -- the run itself already succeeded and is safe in the job row.
    """
    if not (response.total_reviews > 0 or response.detailed_report is not None):
        return

    # Stamp a stable filename onto the response so it is carried in the job's `result` -- the UI
    # addresses the report by this name (list, chatbot, project links, sharing). No disk file is
    # written: the `scraping_jobs.result` JSONB is the single source of truth for the report.
    safe_brand = re.sub(r"[^a-zA-Z0-9_-]", "_", response.brand_name.strip().lower())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    response.report_filename = f"{safe_brand}_report_{timestamp}.json"

    try:
        async with SessionLocal() as db:
            existing = (
                await db.execute(select(Company).where(Company.name.ilike(response.brand_name.strip())))
            ).scalars().first()
            if not existing:
                # companies.size_id is NOT NULL in the schema even though the model marks it
                # optional. Omitting it made every insert here fail, and the swallowed error
                # meant scraped companies silently never reached the dropdown. A scrape does
                # not reveal headcount, so it is recorded as 'unknown'.
                size_id = (
                    await db.execute(select(CompanySize.id).where(CompanySize.code == "unknown"))
                ).scalar_one_or_none()
                db.add(
                    Company(
                        name=response.brand_name.strip(),
                        sector_id=_determine_sector_id(response.brand_name),
                        size_id=size_id,
                    )
                )
                await db.commit()
                logger.info("Registered new scraped company: %s", response.brand_name)
    except Exception:
        logger.exception("Failed to register scraped company '%s'", response.brand_name)


async def _run_job(
    job_id: int, req: ScrapeRequest, apify_token: str, owner_id: int | None = None
) -> None:
    async with _get_semaphore():
        await _update(job_id, status="running", progress="Collecting reviews")
        try:
            response = await run_full_scrape(
                req.brand_name,
                apify_token,
                req.facebook_url,
                req.manual_analysis,
                req.trustpilot_domain,
                req.trustpilot_period,
                req.google_location,
                req.keywords,
                req.instagram_url,
            )
            # Archiving is best-effort and must never turn a completed scrape into a failed
            # job: the result is already in hand, and the job row is what the browser reads.
            try:
                await _archive_run(response, owner_id)
            except Exception:
                logger.exception("Archiving failed for job %s; the result is still recorded", job_id)

            await _update(
                job_id,
                status="succeeded",
                progress="Done",
                result=response.model_dump(mode="json"),
                finished_at=datetime.now(timezone.utc),
            )
            logger.info(
                "Scraping job %s finished: %s reviews for '%s'",
                job_id, response.total_reviews, req.brand_name,
            )
        except Exception as exc:
            logger.exception("Scraping job %s failed", job_id)
            await _update(
                job_id,
                status="failed",
                progress=None,
                error=str(exc)[:2000],
                finished_at=datetime.now(timezone.utc),
            )


def start_job(job_id: int, req: ScrapeRequest, apify_token: str, owner_id: int | None = None) -> None:
    """Detach the work from the request that asked for it."""
    task = asyncio.create_task(_run_job(job_id, req, apify_token, owner_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def get_job(db, job_id: int) -> ScrapingJob | None:
    return await db.get(ScrapingJob, job_id)


async def reap_stale_jobs(db) -> int:
    """Fail jobs left 'running' by a process that died.

    Tasks live in memory, so a restart silently orphans anything in flight and the UI would
    poll a job that can never finish. Called at startup, before any new job can be created.
    """
    result = await db.execute(
        select(ScrapingJob).where(ScrapingJob.status.in_(("pending", "running")))
    )
    stale = result.scalars().all()
    for job in stale:
        job.status = "failed"
        job.error = "Interrupted by a server restart. Please run the analysis again."
        job.finished_at = datetime.now(timezone.utc)
    if stale:
        await db.commit()
        logger.warning("Marked %d interrupted scraping job(s) as failed", len(stale))
    return len(stale)


def job_to_status(job: ScrapingJob) -> dict:
    """Shape sent to the browser. The result is inlined only once it exists, so polling
    stays cheap while the job is still running."""
    payload: dict = {
        "job_id": job.id,
        "brand_name": job.brand_name,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
    if job.status == "succeeded" and job.result:
        payload["result"] = job.result
    return payload


def parse_job_result(job: ScrapingJob) -> ScrapingResponse | None:
    if job.status != "succeeded" or not job.result:
        return None
    return ScrapingResponse.model_validate(job.result)
