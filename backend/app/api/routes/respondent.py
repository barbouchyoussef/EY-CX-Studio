"""Public, passwordless respondent path for client assessment links.

A client opens `/a/<token>` (no login). The SPA sends the token as `X-Respondent-Token` on every
call here. The token resolves to EXACTLY ONE assessment; these endpoints let the client drive that
assessment's chat and see nothing else. NO `get_current_user` — access is the token alone.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment import Assessment
from app.db.models.assessment_recipient import AssessmentRecipient
from app.db.models.company import Company
from app.dependencies.db import get_db
from app.repositories.company_size_repository import CompanySizeRepository
from app.repositories.sector_repository import SectorRepository
from app.schemas.assessment import AnswerRequest, AnswerResponse, NextQuestionResponse
from app.services.assessment import (
    build_assessment_conversation_service,
    build_assessment_reporting_service,
    build_assessment_service,
    client_link_service,
)

router = APIRouter(prefix="/respondent", tags=["respondent"])


async def _ctx(
    x_respondent_token: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> tuple[int, AssessmentRecipient]:
    """Resolve the link token → (assessment_id, recipient). 401 if invalid/expired/revoked."""
    if not x_respondent_token:
        raise HTTPException(status_code=401, detail="Missing link token")
    rec = await client_link_service.resolve(db, x_respondent_token)
    if rec is None:
        raise HTTPException(status_code=401, detail="This link is invalid or has expired.")
    await client_link_service.mark_opened(db, rec)
    return rec.assessment_id, rec


@router.get("/context")
async def respondent_context(
    ctx: Annotated[tuple[int, AssessmentRecipient], Depends(_ctx)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Who this link is for + the assessment's current state, so the client shell can start."""
    assessment_id, rec = ctx
    service = build_assessment_service(db)
    try:
        state = await service.get_assessment(assessment_id)
    except Exception:
        state = None  # never 500 the client on a state-building hiccup
    return {
        "client_name": rec.client_name,
        "client_role": rec.client_role,
        "status": rec.status,
        "assessment": state.model_dump() if state is not None else None,
    }


class ProfileRequest(BaseModel):
    sector: str  # reference code, e.g. "telecom"
    size: str  # reference code, e.g. "medium"
    company_name: str | None = None  # the client can correct their company name


@router.post("/profile")
async def respondent_set_profile(
    body: ProfileRequest,
    ctx: Annotated[tuple[int, AssessmentRecipient], Depends(_ctx)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The client sets their own company name, sector + size before starting the questions.

    This overwrites whatever placeholder was inferred when the link was created, so the client
    fills in their real context rather than us guessing it. Must be called before answering.
    """
    assessment_id, _ = ctx
    assessment = await db.get(Assessment, assessment_id)
    if assessment is None or assessment.company_id is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    company = await db.get(Company, assessment.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    sector = await SectorRepository(db).get_by_code(body.sector)
    size = await CompanySizeRepository(db).get_by_code(body.size)
    if sector is None or size is None:
        raise HTTPException(status_code=422, detail="Unknown sector or company size")
    company.sector_id = sector.id
    company.size_id = size.id
    if body.company_name and body.company_name.strip():
        company.name = body.company_name.strip()[:255]
    await db.commit()
    return {"ok": True}


@router.get("/next-question", response_model=NextQuestionResponse)
async def respondent_next_question(
    ctx: Annotated[tuple[int, AssessmentRecipient], Depends(_ctx)],
    db: AsyncSession = Depends(get_db),
) -> NextQuestionResponse:
    assessment_id, _ = ctx
    conv = build_assessment_conversation_service(db)
    result = await conv.next_question(assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.post("/answers", response_model=AnswerResponse)
async def respondent_answer(
    body: AnswerRequest,
    ctx: Annotated[tuple[int, AssessmentRecipient], Depends(_ctx)],
    db: AsyncSession = Depends(get_db),
) -> AnswerResponse:
    assessment_id, _ = ctx
    conv = build_assessment_conversation_service(db)
    result = await conv.submit_answer(
        assessment_id,
        body.answer,
        expected_axis=body.expected_axis,
        expected_version=body.expected_version,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/final-report")
async def respondent_final_report(
    ctx: Annotated[tuple[int, AssessmentRecipient], Depends(_ctx)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the report once the client finishes, and mark the link completed."""
    assessment_id, _ = ctx
    reporting = build_assessment_reporting_service(db)
    result = await reporting.get_final_report(assessment_id=assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not ready")
    await client_link_service.mark_completed(db, assessment_id)
    return result.model_dump()
