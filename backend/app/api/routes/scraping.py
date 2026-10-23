from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
import json
import re
from datetime import datetime, timezone
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.dependencies.db import get_db
from app.db.models.company import Company
from app.db.models.scraping_job import ScrapingJob
from app.db.models.user import User
from app.services.auth import access
from app.schemas.manual_analysis import ManualAnalysisParseResponse
from app.schemas.scraping import CompanyOption, DetailedSocialReport, ScrapeRequest
from app.services.scraping.job_service import (
    create_job,
    get_job,
    job_to_status,
    start_job,
)
from app.services.scraping.manual_analysis_parser import parse_manual_analysis_workbook

logger = logging.getLogger(__name__)

from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/scraping", dependencies=[Depends(get_current_user)])

_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "static" / "templates" / "SM_Website_Analysis_TEMPLATE.xlsx"


@router.get("/manual-analysis/template")
async def download_manual_analysis_template() -> FileResponse:
    """Serve the blank 'Social Media & Website Analysis' Excel template for the consultant to fill in."""
    if not _TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="Template file not found on the server.")
    return FileResponse(
        path=_TEMPLATE_PATH,
        filename="SM_Website_Analysis_TEMPLATE.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/manual-analysis/parse", response_model=ManualAnalysisParseResponse)
async def parse_manual_analysis(file: UploadFile) -> ManualAnalysisParseResponse:
    """Parse a consultant-filled analysis workbook and return the structured data for review before scraping."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Please upload the .xlsx workbook (not .xls, .csv, etc.).")

    content = await file.read()
    try:
        return parse_manual_analysis_workbook(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/companies", response_model=list[CompanyOption])
async def list_companies(db: AsyncSession = Depends(get_db)) -> list[CompanyOption]:
    """Return distinct company names for the dropdown selector."""
    result = await db.execute(
        select(Company.id, Company.name).order_by(Company.name.asc())
    )
    rows = result.all()
    return [CompanyOption(id=r.id, name=r.name) for r in rows]


@router.get("/reports")
async def list_reports(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    """List saved scraping reports the user may see (owned, shared, or in their projects).

    Reports live in ``scraping_jobs.result`` (JSONB) -- the single source of truth. Each report is
    addressed by the ``report_filename`` carried inside that result."""
    visible = await access.visible_refs(db, user.id, "social_report")
    rows = (await db.execute(
        select(ScrapingJob)
        .where(ScrapingJob.result.isnot(None))
        .order_by(ScrapingJob.created_at.desc())
    )).scalars().all()

    reports = []
    for row in rows:
        r = row.result or {}
        fname = r.get("report_filename")
        if not fname:
            continue
        is_owner = row.owner_id == user.id
        # Owner-scope: keep only reports the user owns, was shared, or that sit in their project.
        if not is_owner and fname not in visible:
            continue
        reports.append({
            "filename": fname,
            "brand_name": r.get("brand_name") or row.brand_name or "Unknown",
            "scraped_at": r.get("scraped_at"),
            "total_reviews": r.get("total_reviews", 0),
            "owned": is_owner,  # False when visible only via a share / project
        })

    reports.sort(key=lambda x: x.get("scraped_at") or "", reverse=True)
    return reports


async def _load_report_if_visible(
    filename: str, user: User, db: AsyncSession, *, owner_only: bool = False
) -> tuple[str, dict]:
    """Resolve a report by its filename to (filename, report_dict) from ``scraping_jobs.result``,
    enforcing access. 404 (not 403) so we don't confirm existence. The filename is matched inside
    the JSONB, so a hostile/guessed name simply finds no row -- no filesystem is touched."""
    row = (await db.execute(
        select(ScrapingJob).where(ScrapingJob.result["report_filename"].astext == filename)
    )).scalars().first()
    if row is None or not row.result:
        raise HTTPException(status_code=404, detail="Report not found")

    is_owner = row.owner_id == user.id
    if owner_only:
        if not is_owner:
            raise HTTPException(status_code=404, detail="Report not found")
    elif not is_owner and not await access.can_view_via_project_or_share(
        db, user.id, "social_report", filename
    ):
        raise HTTPException(status_code=404, detail="Report not found")

    data = dict(row.result)
    data.setdefault("owner_id", row.owner_id)  # column is authoritative; result may predate it
    # The inputs the run was launched with (brand, URLs, keywords, period...). The report itself
    # does not carry them, so without this the UI cannot repopulate the form to correct one field
    # and re-run. Absent on rows created before the column existed.
    data["scrape_request"] = row.request or {}
    return filename, data


@router.get("/reports/{filename}")
async def get_report(
    filename: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Retrieve details of a saved scraping report (if the user may see it)."""
    filepath, data = await _load_report_if_visible(filename, user, db)

    # Ensure the filename is present so the UI can address this report (e.g. its chatbot),
    # including older archives saved before the field existed.
    from app.services.scraping import report_chat

    data["report_filename"] = os.path.basename(filepath)
    data["chat_messages"] = report_chat.load_chat(os.path.basename(filepath))
    return data


class _ReportChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    text: str = ""


class ReportChatRequest(BaseModel):
    query: str = Field(..., description="User question about this social report")
    history: list[_ReportChatMessage] = Field(default_factory=list)


@router.post("/reports/{filename}/chat")
async def chat_report(
    filename: str,
    body: ReportChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Chat about one saved social report. Answers from the report's computed findings
    (KPI injection via the shared agentic engine) -- no vector search needed."""
    filepath, data = await _load_report_if_visible(filename, user, db)

    detailed = data.get("detailed_report")
    if not detailed:
        raise HTTPException(status_code=400, detail="This report has no detailed analysis to chat about.")

    report = DetailedSocialReport.model_validate(detailed)
    from app.services.scraping import report_chat
    from app.services.scraping.social_chat import chat_with_report

    report_name = os.path.basename(filepath)
    result = await chat_with_report(
        report,
        body.query,
        report_id=report_name,
        history=[m.model_dump() for m in body.history],
    )

    # Persist the turn so the conversation survives a reload.
    import time
    from uuid import uuid4

    now = time.time() * 1000
    report_chat.append_chat(report_name, [
        {"id": uuid4().hex[:12], "role": "user", "text": body.query, "ts": now},
        {"id": uuid4().hex[:12], "role": "assistant",
         "text": result.get("answer", ""), "sources": result.get("sources", []), "ts": now + 1},
    ])
    return result


@router.delete("/reports/{filename}", status_code=204)
async def delete_report(
    filename: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    """Delete one saved report from disk (owner only).

    Only the JSON archive is removed. The `scraping_jobs` row that produced it is left
    alone: it is the run history, and deleting a report is about tidying the list rather
    than erasing the fact that the run happened.
    """
    await _load_report_if_visible(filename, user, db, owner_only=True)  # access check (owner only)

    # Clear the report from its job row. The run-history row itself stays (brand, status, when) --
    # deleting a report tidies the list, it doesn't erase that the run happened.
    row = (await db.execute(
        select(ScrapingJob).where(ScrapingJob.result["report_filename"].astext == filename)
    )).scalars().first()
    if row is not None:
        row.result = None
        await db.commit()

    # Remove the report's chat history and any project links / shares that pointed at it.
    from app.services.scraping import report_chat
    from app.services.projects import project_service as project_svc

    report_chat.delete_chat(filename)
    await project_svc.cleanup_analysis_links(db, "social_report", filename)

    logger.info("Deleted saved report %s", filename)
    return Response(status_code=204)


@router.post("/run", status_code=202)
async def run_scraping(
    req: ScrapeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue a scrape and return its job id immediately.

    The work itself takes minutes; keeping the request open for it meant a closed tab or a
    proxy timeout destroyed a run that had already been paid for. Poll /scraping/jobs/{id}.
    """
    settings = get_settings()
    token = settings.apify_api_token
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Apify API token is not configured. Set APIFY_API_TOKEN in .env.",
        )
    if not req.brand_name.strip():
        raise HTTPException(status_code=400, detail="A company name is required.")

    job = await create_job(db, req, owner_id=user.id)
    start_job(job.id, req, token, owner_id=user.id)
    logger.info("Queued scraping job %s for '%s'", job.id, req.brand_name)
    return job_to_status(job)


@router.get("/jobs/{job_id}")
async def get_scraping_job(
    job_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Poll a queued scrape. Returns the full report once the job succeeds."""
    job = await get_job(db, job_id)
    if job is None or (job.owner_id is not None and job.owner_id != user.id):
        # Own jobs only; 404 rather than 403 so a job's existence isn't confirmed.
        raise HTTPException(status_code=404, detail="Scraping job not found.")

    return job_to_status(job)
