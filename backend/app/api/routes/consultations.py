from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models.assessment import Assessment
from app.dependencies.db import get_db
from app.schemas.consultation import BookConsultationRequest, BookConsultationResponse

router = APIRouter(prefix="/consultations")


@router.post("/book", response_model=BookConsultationResponse)
async def book_consultation(
    req: BookConsultationRequest,
    db: AsyncSession = Depends(get_db),
) -> BookConsultationResponse:
    receiver = (get_settings().consultation_receiver_email or "").strip()
    if not receiver:
        raise HTTPException(status_code=503, detail="Consultation receiver email is not configured")

    result = await db.execute(
        select(Assessment)
        .options(selectinload(Assessment.company))
        .where(Assessment.id == req.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.company is None:
        raise HTTPException(status_code=422, detail="Assessment company is not available")

    company_name = (assessment.company.name or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Company name is not available")

    subject = f"Demande de consultation CX - {company_name}"
    body = (
        "Bonjour,\n\n"
        "Je souhaite réserver une consultation CX suite à mon évaluation de maturité CX.\n\n"
        f"Nom : {req.client_name}\n"
        f"Entreprise : {company_name}\n\n"
        "Merci de me contacter afin de fixer un créneau de consultation.\n\n"
        "Cordialement,\n"
        f"{req.client_name}"
    )
    gmail_url = (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&to={quote(receiver, safe='')}"
        f"&su={quote(subject, safe='')}"
        f"&body={quote(body, safe='')}"
    )
    return BookConsultationResponse(gmail_url=gmail_url)
