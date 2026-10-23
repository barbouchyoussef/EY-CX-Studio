"""Runs issue-log generation as a background job instead of inside the HTTP request.

A run reads every selected source in its own LLM call, plus a completeness sweep on each, plus
one recommendations pass per client. Eight sources is ~20 calls and several minutes; thirty
sources is far more. That is well past what a reverse proxy holds open (nginx and ALB default
to 60 s), and losing the connection used to discard work already paid for in tokens.

Same shape as the social-scraping job runner: the row is created first so a fast failure has
somewhere to report itself, the task owns its own short-lived sessions, and the browser polls.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_log import IssueLog
from app.db.session import SessionLocal
from app.services.issue_log import correlate as correlate_service
from app.services.issue_log import pipeline, recommend, resolve

logger = logging.getLogger(__name__)

# Each run holds many concurrent LLM calls of its own, already bounded per provider by the
# throttle. Two simultaneous runs is the point where a shared token budget starts to hurt.
_MAX_CONCURRENT_JOBS = 2
_job_semaphore: asyncio.Semaphore | None = None

# asyncio keeps only weak references to tasks, so a task nothing holds can be collected
# mid-run. This set is what keeps them alive.
_running_tasks: set[asyncio.Task] = set()


def _semaphore() -> asyncio.Semaphore:
    global _job_semaphore
    if _job_semaphore is None:
        _job_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_JOBS)
    return _job_semaphore


async def create_job(db: AsyncSession, *, name: str, owner_id: int, project_id: int | None,
                     selections: list[dict], focus: str | None, sweep: bool,
                     correlate: bool, recommendations: bool, max_issues: int) -> IssueLog:
    """Persist the queued run. Nothing else is committed here -- the row has to exist before
    the task starts, so that even an immediate failure is visible to the consultant."""
    row = IssueLog(
        owner_id=owner_id,
        project_id=project_id,
        name=(name or "").strip() or "Issue Log",
        status="pending",
        progress="Queued",
        request={"selections": selections, "focus": focus, "sweep": sweep,
                 "correlate": correlate, "recommendations": recommendations,
                 "max_issues": max_issues},
        findings=[], recommendations=[], run={}, kpis={}, sources=[],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _update(job_id: int, **fields) -> None:
    """Write progress from inside the task, on its own short-lived session.

    The request's session is long gone by the time this runs, and holding one open for the
    whole run would pin a pooled connection for minutes.
    """
    try:
        async with SessionLocal() as db:
            row = await db.get(IssueLog, job_id)
            if row is None:
                logger.warning("issue-log job %s vanished mid-run", job_id)
                return
            for key, value in fields.items():
                setattr(row, key, value)
            await db.commit()
    except Exception:
        # A bookkeeping failure must never kill the run itself.
        logger.exception("could not update issue-log job %s", job_id)


async def _run(job_id: int, owner_id: int) -> None:
    async with _semaphore():
        try:
            request = {}
            async with SessionLocal() as db:
                row = await db.get(IssueLog, job_id)
                if row is None:
                    return
                request = dict(row.request or {})

            await _update(job_id, status="running", progress="Reading the selected analyses")

            async with SessionLocal() as db:
                resolution = await resolve.resolve_selections(
                    db, owner_id, request.get("selections") or [])

            chunks = resolution.bundle.chunks
            if not chunks:
                await _update(job_id, status="failed", progress=None,
                              sources=resolution.statuses,
                              error="None of the selected analyses could be read.",
                              finished_at=datetime.now(timezone.utc))
                return

            await _update(job_id, progress=f"Analysing {len(chunks)} sources",
                          sources=resolution.statuses)

            issues, record = await pipeline.generate_issues(
                chunks,
                focus=request.get("focus"),
                sweep=bool(request.get("sweep", True)),
                max_issues=int(request.get("max_issues") or 200),
            )

            # Cross-source correlation. Generation reads each source alone, so nothing until
            # now can see that two stakeholders agree -- or contradict each other.
            conflicts: list[dict] = []
            run_payload = record.as_dict()
            if request.get("correlate", True) and len(issues) > 1:
                await _update(job_id, progress="Comparing what each source said",
                              findings=issues, run=run_payload)
                conflicts, corr_record = await correlate_service.correlate(
                    issues, pipeline.DEFAULT_CHAIN)
                record.warnings.extend(corr_record.warnings)
                run_payload = record.as_dict()
                run_payload["correlation"] = corr_record.as_dict()

            recs: list[dict] = []
            if request.get("recommendations", True) and issues:
                await _update(job_id, progress=f"Writing recommendations for {len(issues)} issues",
                              findings=issues, run=run_payload)
                recs, rec_record = await recommend.build_recommendations(
                    issues, pipeline.DEFAULT_CHAIN)
                record.warnings.extend(rec_record.warnings)
                correlation_stats = run_payload.get("correlation")
                run_payload = record.as_dict()
                if correlation_stats:
                    run_payload["correlation"] = correlation_stats

            run_payload["conflicts"] = conflicts

            await _update(job_id, status="completed", progress=None, error=None,
                          findings=issues, recommendations=recs, run=run_payload,
                          sources=resolution.statuses,
                          finished_at=datetime.now(timezone.utc))
            logger.info("issue-log job %s finished: %d issues, %d recommendations, "
                        "%d conflict(s) flagged", job_id, len(issues), len(recs), len(conflicts))

        except asyncio.CancelledError:
            # Server shutting down. Mark it so the row does not sit on "running" forever.
            await _update(job_id, status="failed", progress=None,
                          error="The server restarted while this run was in progress.",
                          finished_at=datetime.now(timezone.utc))
            raise
        except Exception as exc:
            logger.exception("issue-log job %s failed", job_id)
            await _update(job_id, status="failed", progress=None,
                          error=f"{type(exc).__name__}: {exc}"[:2000],
                          finished_at=datetime.now(timezone.utc))


def start_job(job_id: int, owner_id: int) -> None:
    """Launch the run and return immediately."""
    task = asyncio.create_task(_run(job_id, owner_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def to_status(row: IssueLog) -> dict:
    """The polling payload. Findings ride along only once the run is finished, so a poll every
    few seconds stays cheap while a large log is still being written."""
    payload = {
        "id": row.id,
        "name": row.name,
        "status": row.status,
        "progress": row.progress,
        "error": row.error,
        "project_id": row.project_id,
        "sources": row.sources or [],
        "findings_count": len(row.findings or []),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }
    if row.status == "completed":
        payload["issues"] = row.findings or []
        payload["recommendations"] = row.recommendations or []
        payload["run"] = row.run or {}
        payload["conflicts"] = (row.run or {}).get("conflicts") or []
    return payload
