"""HTTP surface of the maturity assessment: the diagnostic conversation and its report.

The largest router in the application, because the assessment has the most stages. It stays thin
on purpose -- each endpoint resolves a service, checks access, and delegates. The real logic lives
in `app/services/assessment/`.

Three things are handled here rather than in a service, because they are HTTP concerns:

  * `require_assessment_access` -- the single authorisation gate for everything addressed by
    assessment id, including the passwordless client link;
  * `_http_500_with_dev_detail` -- returns the exception detail only outside production, so a
    developer sees the cause while a client sees nothing;
  * the `get_*_service` dependencies, which bind a request-scoped database session into each
    service.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies.db import get_db
from app.domain.errors import AssessmentStateConflictError
from app.schemas.assessment import (
    AnswerRequest,
    AnswerResponse,
    AssessmentResponse,
    NextQuestionResponse,
    StartAssessmentRequest,
    StartAssessmentResponse,
)
from app.schemas.assessment_memory import AssessmentMemoryResponse
from app.schemas.admin import AssessmentsListResponse
from app.schemas.conversation import MessagesResponse
from app.schemas.capability_status import CapabilitiesStatusResponse, CapabilityHighlightsResponse
from app.schemas.final_report import FinalReportResponse
from app.schemas.recommendations import (
    BatchRecommendationGenerateRequest,
    BatchRecommendationGenerateResponse,
    AssessmentRecommendationsResponse,
    AssessmentTraceResponse,
    RecommendationOutputsResponse,
)
from app.schemas.interview_guide import (
    InterviewGuideResponse,
    GenerateInterviewGuideRequest,
    SaveInterviewGuideRequest,
    InterviewGuideListItem,
)
from app.services.assessment import (
    AssessmentConversationService,
    AssessmentReportingService,
    AssessmentService,
    build_assessment_conversation_service,
    build_assessment_reporting_service,
    build_assessment_service,
)
from app.services.platform import AsyncUnitOfWork

from sqlalchemy import select, update

from fastapi import Response

import logging
from datetime import datetime

from pydantic import ConfigDict, EmailStr

from app.db.models.assessment import Assessment
from app.db.models.interview_guide import InterviewGuide
from app.db.models.user import User
from app.dependencies.auth import get_current_user, require_admin
from app.services.auth import access
from app.services.assessment import client_link_service
from app.services.email import sender as email_sender
from app.services.projects import project_service as project_svc

logger = logging.getLogger(__name__)

# Every assessment route requires a signed-in user. (Phase 5 will add a separate respondent
# path for client magic-links; until then these are consultant-only.)
router = APIRouter(prefix="/assessments", dependencies=[Depends(get_current_user)])


def get_reporting_service(db: AsyncSession = Depends(get_db)) -> AssessmentReportingService:
    return build_assessment_reporting_service(db)


def get_assessment_service(db: AsyncSession = Depends(get_db)) -> AssessmentService:
    return build_assessment_service(db)


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> AssessmentConversationService:
    return build_assessment_conversation_service(db)


async def require_assessment_access(
    assessment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Authorize access to one assessment: owner, or shared/attached-to-your-project.

    Applied as a route dependency on every /{assessment_id} endpoint so a signed-in consultant
    cannot read or act on another's assessment by guessing its id. Returns 404 (not 403) so the
    existence of others' assessments is never confirmed.
    """
    a = await db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if a.owner_id != user.id and not await access.can_view_via_project_or_share(
        db, user.id, "assessment", assessment_id
    ):
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment_id


def _http_500_with_dev_detail(exc: Exception) -> HTTPException:
    settings = get_settings()
    detail = "Internal server error"
    if settings.app_env != "production":
        detail = f"{type(exc).__name__}: {exc}"
    return HTTPException(status_code=500, detail=detail)


@router.post("", response_model=StartAssessmentResponse)
async def start_assessment(
    req: StartAssessmentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AssessmentService = Depends(get_assessment_service),
) -> StartAssessmentResponse:
    try:
        assessment = await service.start_assessment(
            company_name=req.company_name,
            sector_label=req.sector,
            company_size_label=req.size,
            region=req.region,
            prompt_profile=req.prompt_profile,
            language=req.language,
        )
        # Stamp ownership on the freshly created assessment (same request-scoped session).
        await db.execute(
            update(Assessment).where(Assessment.id == assessment.id).values(owner_id=user.id)
        )
        await db.commit()
        return StartAssessmentResponse(assessment_id=assessment.id)
    except (ValueError, RuntimeError) as e:
        # If auto-classification fails, the client can retry with explicit sector/size.
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{assessment_id}", response_model=AssessmentResponse, dependencies=[Depends(require_assessment_access)])
async def get_assessment(
    assessment_id: int,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    data = await service.get_assessment(assessment_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return data


@router.get("/{assessment_id}/next-question", response_model=NextQuestionResponse, dependencies=[Depends(require_assessment_access)])
async def next_question(
    assessment_id: int,
    service: AssessmentConversationService = Depends(get_conversation_service),
) -> NextQuestionResponse:
    try:
        result = await service.next_question(assessment_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_500_with_dev_detail(exc)


@router.post("/{assessment_id}/answers", response_model=AnswerResponse, dependencies=[Depends(require_assessment_access)])
async def submit_answer(
    assessment_id: int,
    req: AnswerRequest,
    service: AssessmentConversationService = Depends(get_conversation_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AnswerResponse:
    try:
        result = await service.submit_answer(
            assessment_id,
            req.answer,
            idempotency_key=idempotency_key,
            expected_axis=req.expected_axis,
            expected_version=req.expected_version,
        )
    except AssessmentStateConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as exc:
        raise _http_500_with_dev_detail(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/memory", response_model=AssessmentMemoryResponse, dependencies=[Depends(require_assessment_access)])
async def get_assessment_memory(
    assessment_id: int,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentMemoryResponse:
    try:
        result = await service.get_memory(assessment_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_500_with_dev_detail(exc)


@router.get("", response_model=AssessmentsListResponse)
async def list_assessments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    region_code: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentsListResponse:
    resp = await service.list_assessments(limit=limit, offset=offset, region_code=region_code)
    # Scope to what the user may see: owned, plus shared/attached-to-their-projects.
    # (Filtered after the query for now; fine at current scale, revisit for strict pagination.)
    owned = set(
        (await db.execute(select(Assessment.id).where(Assessment.owner_id == user.id))).scalars()
    )
    visible = {int(r) for r in await access.visible_refs(db, user.id, "assessment") if r.isdigit()}
    allowed = owned | visible
    resp.items = [it for it in resp.items if it.id in allowed]
    # Annotate each with its latest client link (status + who it was sent to), if any,
    # and flag whether the caller owns it (vs. it being shared with them).
    recipients = await client_link_service.latest_recipient_by_assessment(db, [it.id for it in resp.items])
    for it in resp.items:
        it.owned = it.id in owned
        rec = recipients.get(it.id)
        if rec is not None:
            it.recipient_status = rec.status
            it.recipient_name = rec.client_name
            it.recipient_role = rec.client_role
    return resp


@router.get("/{assessment_id}/messages", response_model=MessagesResponse, dependencies=[Depends(require_assessment_access)])
async def list_messages(
    assessment_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: AssessmentService = Depends(get_assessment_service),
) -> MessagesResponse:
    result = await service.get_messages(assessment_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/capabilities", response_model=CapabilitiesStatusResponse, dependencies=[Depends(require_assessment_access)])
async def capabilities_status(
    assessment_id: int,
    axis: str | None = None,
    service: AssessmentService = Depends(get_assessment_service),
) -> CapabilitiesStatusResponse:
    try:
        result = await service.get_capabilities_status(assessment_id, axis=axis)
        if result is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_500_with_dev_detail(exc)


@router.get("/{assessment_id}/capabilities/highlights", response_model=CapabilityHighlightsResponse, dependencies=[Depends(require_assessment_access)])
async def capability_highlights(
    assessment_id: int,
    axis: str | None = None,
    limit: int = Query(default=6, ge=1, le=20),
    service: AssessmentService = Depends(get_assessment_service),
) -> CapabilityHighlightsResponse:
    try:
        result = await service.get_capability_highlights(assessment_id=assessment_id, axis=axis, limit=limit)
        if result is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_500_with_dev_detail(exc)


@router.get("/{assessment_id}/criteria", response_model=CapabilitiesStatusResponse, dependencies=[Depends(require_assessment_access)])
async def criteria_status_legacy(
    assessment_id: int,
    axis: str | None = None,
    service: AssessmentService = Depends(get_assessment_service),
) -> CapabilitiesStatusResponse:
    # Backward-compatible alias for older clients.
    result = await service.get_capabilities_status(assessment_id, axis=axis)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/recommendations", response_model=AssessmentRecommendationsResponse, dependencies=[Depends(require_assessment_access)])
async def recommendations(
    assessment_id: int,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> AssessmentRecommendationsResponse:
    result = await reporting.get_recommendations(assessment_id=assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.post("/{assessment_id}/recommendations/batch-generate", response_model=BatchRecommendationGenerateResponse, dependencies=[Depends(require_assessment_access)])
async def recommendations_batch_generate(
    assessment_id: int,
    req: BatchRecommendationGenerateRequest,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> BatchRecommendationGenerateResponse:
    result = await reporting.generate_recommendations_batch(
        assessment_id=assessment_id,
        language=req.language,
        max_actions_per_capability=req.max_actions_per_capability,
        tone=req.tone,
        max_words_per_capability=req.max_words_per_capability,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/recommendation-outputs", response_model=RecommendationOutputsResponse, dependencies=[Depends(require_assessment_access)])
async def recommendation_outputs(
    assessment_id: int,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> RecommendationOutputsResponse:
    result = await reporting.get_recommendation_outputs(assessment_id=assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/final-report", response_model=FinalReportResponse, dependencies=[Depends(require_assessment_access)])
async def final_report(
    assessment_id: int,
    refresh_synthesis: bool = Query(default=False),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> FinalReportResponse:
    result = await reporting.get_final_report(
        assessment_id=assessment_id,
        refresh_synthesis=refresh_synthesis,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.post("/interview-guide/generate", response_model=InterviewGuideResponse)
async def generate_interview_guide(
    req: GenerateInterviewGuideRequest,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> InterviewGuideResponse:
    result = await reporting.get_interview_guide(req)
    if result is None:
        raise HTTPException(status_code=400, detail="Unable to generate interview guide. Verify parameters.")
    return result


@router.get("/{assessment_id}/competitive-first-layer-debug", dependencies=[Depends(require_assessment_access)])
async def competitive_first_layer_debug(
    assessment_id: int,
    competitor_name: str | None = Query(default=None),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    result = await reporting.debug_competitive_first_layer(
        assessment_id=assessment_id,
        competitor_name=competitor_name,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/telecom-semantic-leaders-debug", dependencies=[Depends(require_assessment_access)])
async def telecom_semantic_leaders_debug(
    assessment_id: int,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    result = await reporting.debug_telecom_semantic_leaders(assessment_id=assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/telecom-discovery-leaders-debug", dependencies=[Depends(require_assessment_access)])
async def telecom_discovery_leaders_debug(
    assessment_id: int,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    result = await reporting.debug_telecom_discovery_leaders(assessment_id=assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@router.get("/{assessment_id}/trace", response_model=AssessmentTraceResponse, dependencies=[Depends(require_assessment_access)])
async def trace(
    assessment_id: int,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> AssessmentTraceResponse:
    result = await reporting.get_trace(assessment_id=assessment_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


from pydantic import BaseModel

class BenchmarkTestRequest(BaseModel):
    sector: str
    company_name: str
    pain_points: list[dict] = []
    language: str = "fr"

# Admin-only: a development harness that runs the full leaders benchmark, so every call
# spends LangSearch and model budget. Nothing in the product calls it.
@router.post("/benchmark-test", dependencies=[Depends(require_admin)])
async def run_benchmark_test(
    req: BenchmarkTestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.llm.core.facade_service import build_llm_service
    from app.services.assessment.reporting.telecom_semantic_leaders_service import SemanticLeadersService

    settings = get_settings()
    llm = build_llm_service(settings=settings)

    pain_points = req.pain_points
    if not pain_points:
        # Default seeded pain points corresponding to common capabilities and rubrics
        pain_points = [
            {
                "capability": "Feedback collection",
                "capability_description": "Capturing customer feedback through listening channels, surveys, complaint capture, and regular review routines.",
                "action_hints": "Set one recurring feedback pulse and one weekly review routine.",
                "rubric_description": "Feedback is collected inconsistently or through a few isolated channels, with weak logging, ownership, and review rhythm.",
                "level3_action_hints": "Feedback becomes a normal input into service management, improving continuity between listening, decisions, and action."
            },
            {
                "capability": "Measurement and continuous improvement",
                "capability_description": "Tracking customer experience through dashboards, review cycles, owner linkage, and action-focused metrics.",
                "action_hints": "Pick a small set of CX measures and review them on a fixed cadence.",
                "rubric_description": "Measures are limited or disconnected from action, with little evidence of a regular improvement loop.",
                "level3_action_hints": "Improvement activity becomes easier to prioritize and govern through connected CX, operational, and business outcomes."
            },
            {
                "capability": "Decision-making",
                "capability_description": "Using customer evidence in decision forums, prioritization reviews, and action planning.",
                "action_hints": "Link customer decisions to named owners, actions, and follow-up checks.",
                "rubric_description": "Customer evidence influences some decisions, but the practice is partial, siloed, or inconsistent across teams.",
                "level3_action_hints": "Customer evidence has a stronger path into planning, helping teams prioritize resources around the highest-impact experience gaps."
            }
        ]

    service = SemanticLeadersService(settings=settings, llm_service=llm)

    try:
        snapshot = await service.build_leaders_snapshot(
            sector=req.sector,
            respondent_company_name=req.company_name,
            pain_points=pain_points,
            language=req.language,
            generation_mode="initial",
        )
        return snapshot
    except Exception:
        # The message can carry provider responses and internal paths, so it goes to the log,
        # not to the caller.
        logger.exception("benchmark-test failed")
        raise HTTPException(status_code=500, detail="Benchmark run failed")


@router.post("/interview-guide/save")
async def save_interview_guide(
    req: SaveInterviewGuideRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    result = await reporting.save_interview_guide(req)
    # Stamp ownership on first save; never overwrite an existing owner.
    gid = result.get("id")
    if gid is not None:
        await db.execute(
            update(InterviewGuide)
            .where(InterviewGuide.id == gid, InterviewGuide.owner_id.is_(None))
            .values(owner_id=user.id)
        )
        await db.commit()
    return result


_GUIDE_QUESTION_KEYS = (
    "introduction_questions",
    "manage_questions",
    "analyze_questions",
    "improve_questions",
    "closure_questions",
)


def _count_guide_questions(payload: object) -> int:
    """Total questions across all sections of a saved guide payload."""
    if not isinstance(payload, dict):
        return 0
    return sum(len(payload[k]) for k in _GUIDE_QUESTION_KEYS if isinstance(payload.get(k), list))


@router.get("/interview-guide/list", response_model=list[InterviewGuideListItem])
async def list_interview_guides(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> list[InterviewGuideListItem]:
    guides = await reporting.list_interview_guides()
    visible = await access.visible_refs(db, user.id, "interview_guide")
    visible_guides = [g for g in guides if g.owner_id == user.id or str(g.id) in visible]
    # Resolve creator names in one query.
    owner_ids = {g.owner_id for g in visible_guides if g.owner_id is not None}
    names: dict[int, str] = {}
    if owner_ids:
        rows = (await db.execute(select(User.id, User.full_name).where(User.id.in_(owner_ids)))).all()
        names = {int(r.id): r.full_name for r in rows}
    return [
        InterviewGuideListItem(
            id=g.id,
            assessment_id=g.assessment_id,
            company_name=g.company_name,
            profile=g.profile,
            language=g.language,
            created_at=g.created_at,
            updated_at=g.updated_at,
            has_insights=g.insights is not None,
            owned=g.owner_id == user.id,
            owner_name=names.get(g.owner_id) if g.owner_id is not None else None,
            question_count=_count_guide_questions(g.payload),
        )
        for g in visible_guides
    ]


@router.get("/interview-guide/{guide_id}", response_model=InterviewGuideResponse)
async def get_saved_interview_guide(
    guide_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> InterviewGuideResponse:
    guide = await reporting.get_saved_interview_guide(guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail="Interview guide not found")
    # IDOR guard: only the owner (or someone it's shared with / a project member) may open it.
    # 404 rather than 403 so we don't confirm the existence of others' guides.
    if guide.owner_id != user.id and not await access.can_view_via_project_or_share(
        db, user.id, "interview_guide", guide.id
    ):
        raise HTTPException(status_code=404, detail="Interview guide not found")

    # Expose the payload parsed as InterviewGuideResponse
    # The payload is stored as JSONB which matches the InterviewGuideResponse schema structure
    # We inject the saved guide ID into the payload so the frontend knows its DB primary key
    payload = dict(guide.payload)
    payload["id"] = guide.id
    payload["insights"] = guide.insights  # persisted cross-reference briefing (or null)
    # The COLUMN is the authoritative profile, not whatever the stored payload happens to hold:
    # older payloads predate it entirely. Returning it is what lets the client send the same value
    # back on save instead of falling back to its form default and relabelling the interview.
    payload["profile"] = guide.profile
    return payload


async def _resolve_interview_guide(
    guide_id: int | None,
    guide_payload: "InterviewGuideResponse | None",
    reporting: AssessmentReportingService,
) -> "tuple[InterviewGuideResponse | None, int | None]":
    """Load the guide from the DB (autosaved source of truth), falling back to the client's copy
    for an unsaved guide. Returns (guide, guide_id)."""
    gid = guide_id or (guide_payload.id if guide_payload else None)
    guide: InterviewGuideResponse | None = None
    if gid is not None:
        row = await reporting.get_saved_interview_guide(gid)
        if row is not None:
            payload = dict(row.payload)
            payload["id"] = row.id
            try:
                guide = InterviewGuideResponse.model_validate(payload)
            except Exception:
                guide = None
    return (guide or guide_payload), gid


class _InterviewChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    text: str = ""


class InterviewGuideChatRequest(BaseModel):
    # The guide's saved id. The backend reloads the guide from the DB (the source of truth the
    # editor autosaves to), so the assistant sees the latest saved edits/answers without relying
    # on the chat request to carry them correctly.
    guide_id: int | None = None
    # Fallback only: the client's current guide, used when it has not been saved yet (no id / not
    # yet in the DB) so a brand-new guide can still be chatted with.
    guide: InterviewGuideResponse | None = None
    query: str = Field(..., description="User question about the interview guide")
    history: list[_InterviewChatMessage] = Field(default_factory=list)


@router.post("/interview-guide/chat")
async def chat_interview_guide(
    req: InterviewGuideChatRequest,
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    """Chat about an interview guide, reading the guide from the DB (autosaved source of truth).

    Injects the guide into the shared agentic engine to interpret answers, flag gaps, and suggest
    follow-ups. Falls back to the guide sent in the request only when it isn't saved yet."""
    guide, guide_id = await _resolve_interview_guide(req.guide_id, req.guide, reporting)
    if guide is None:
        raise HTTPException(status_code=400, detail="No interview guide available to chat about.")

    # Give the assistant the client's prior Orion self-assessment too, when the guide came from one.
    orion_items = None
    if guide.assessment_id is not None:
        trace = await reporting.get_trace(guide.assessment_id)
        orion_items = getattr(trace, "items", None) if trace else None

    from app.services.assessment import interview_chat_store
    from app.services.assessment.interview_chat import chat_with_guide

    result = await chat_with_guide(
        guide,
        req.query,
        orion_trace_items=orion_items,
        history=[m.model_dump() for m in req.history],
    )

    if guide_id is not None:
        import time
        from uuid import uuid4

        now = time.time() * 1000
        interview_chat_store.append_chat(guide_id, [
            {"id": uuid4().hex[:12], "role": "user", "text": req.query, "ts": now},
            {"id": uuid4().hex[:12], "role": "assistant",
             "text": result.get("answer", ""), "sources": result.get("sources", []), "ts": now + 1},
        ])
    return result


@router.get("/interview-guide/{guide_id}/chat")
async def get_interview_guide_chat(
    guide_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a saved guide's persisted chat history (for restoring the conversation on open).

    Same IDOR guard as the guide itself: the chat is the consultant's discussion of a client's
    interview answers, so it follows the guide's visibility exactly. 404 rather than 403 so the
    existence of another consultant's guide is not confirmed.
    """
    from app.services.assessment import interview_chat_store

    guide = await db.get(InterviewGuide, guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail="Interview guide not found")
    if guide.owner_id != user.id and not await access.can_view_via_project_or_share(
        db, user.id, "interview_guide", guide.id
    ):
        raise HTTPException(status_code=404, detail="Interview guide not found")

    return {"messages": interview_chat_store.load_chat(guide_id)}


class InterviewInsightsRequest(BaseModel):
    guide_id: int | None = None
    guide: InterviewGuideResponse | None = None


@router.post("/interview-guide/insights")
async def interview_guide_insights(
    req: InterviewInsightsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reporting: AssessmentReportingService = Depends(get_reporting_service),
) -> dict:
    """Cross-reference the Orion self-assessment against the interview answers, and PERSIST the
    briefing on the guide so history can show it without regenerating.

    Only available when the guide was generated from an assessment that has an Orion
    conversation -- otherwise there is nothing to cross-reference and status says so."""
    guide, guide_id = await _resolve_interview_guide(req.guide_id, req.guide, reporting)
    if guide is None:
        raise HTTPException(status_code=400, detail="No interview guide available.")

    # IDOR guard for a saved guide: only owner / shared / project member may run + store insights.
    if guide_id is not None:
        row = await db.get(InterviewGuide, guide_id)
        if row is None or (
            row.owner_id != user.id
            and not await access.can_view_via_project_or_share(db, user.id, "interview_guide", guide_id)
        ):
            raise HTTPException(status_code=404, detail="Interview guide not found")

    assessment_id = guide.assessment_id
    if assessment_id is None:
        return {"status": "no_assessment", "insights": None}

    trace = await reporting.get_trace(assessment_id)
    if not trace or not getattr(trace, "items", None):
        return {"status": "no_history", "insights": None}

    from datetime import datetime, timezone

    from app.services.assessment.interview_insights import generate_insights

    insights = await generate_insights(guide, trace.items)

    # Persist onto the saved guide so history shows it AND the Issue Log reuses it token-free.
    # We also derive + store the structured issue-log findings here (one extra LLM pass now), so
    # the Issue Log module doesn't have to spend tokens re-extracting them at collect time.
    if guide_id is not None and insights:
        from app.services.assessment.interview_findings import extract_interview_findings

        row = await db.get(InterviewGuide, guide_id)  # session-cached from the IDOR guard above
        cx_findings = await extract_interview_findings(dict(row.payload or {}), insights)
        await db.execute(
            update(InterviewGuide)
            .where(InterviewGuide.id == guide_id)
            .values(
                insights={
                    "markdown": insights,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "generated_by": user.id,
                },
                cx_findings=cx_findings,
            )
        )
        await db.commit()

    return {"status": "success", "insights": insights}



@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an assessment for good (owner only). Cascades to its answers/scores/insights via
    FK, and cleans up any project links + shares that pointed at it. Detaching from a project
    (keeping the assessment) is a different endpoint: DELETE /projects/{id}/artifacts/{aid}."""
    row = await db.get(Assessment, assessment_id)
    if row is None or row.owner_id != user.id:
        # 404 (not 403): never confirm the existence of another owner's assessment.
        raise HTTPException(status_code=404, detail="Assessment not found")
    await db.delete(row)
    await db.commit()
    await project_svc.cleanup_analysis_links(db, "assessment", str(assessment_id))
    return Response(status_code=204)


@router.delete("/interview-guide/{guide_id}", status_code=204)
async def delete_interview_guide(
    guide_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved interview guide for good (owner only) + its chat history + project/share links."""
    row = await db.get(InterviewGuide, guide_id)
    if row is None or row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Interview guide not found")
    await db.delete(row)
    await db.commit()
    await project_svc.cleanup_analysis_links(db, "interview_guide", str(guide_id))
    from app.services.assessment import interview_chat_store

    interview_chat_store.delete_chat(guide_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Client assessment links (magic link to send an assessment to a client)        #
# --------------------------------------------------------------------------- #

class CreateRecipientRequest(BaseModel):
    client_name: str | None = None
    client_role: str | None = None
    email: EmailStr | None = None  # optional: email the link straight to the client


class RecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_name: str | None = None
    client_role: str | None = None
    status: str
    created_at: "datetime"
    expires_at: "datetime | None" = None


class RecipientCreatedResponse(BaseModel):
    recipient: RecipientOut
    link: str
    token: str


async def _owned_assessment_or_404(db: AsyncSession, user: User, assessment_id: int) -> Assessment:
    a = await db.get(Assessment, assessment_id)
    if a is None or a.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.post("/{assessment_id}/recipients", response_model=RecipientCreatedResponse, status_code=201)
async def create_assessment_recipient(
    assessment_id: int,
    body: CreateRecipientRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipientCreatedResponse:
    """Create a passwordless client link for this assessment (owner only). Optionally emails it."""
    await _owned_assessment_or_404(db, user, assessment_id)
    rec, raw = await client_link_service.create_recipient(
        db,
        assessment_id=assessment_id,
        client_name=body.client_name,
        client_role=body.client_role,
        created_by=user.id,
    )
    link = f"{get_settings().app_base_url}/a/{raw}"
    if body.email and email_sender.is_configured():
        try:
            subject, text, html = email_sender.build_assessment_invite_email(
                link, body.client_name, user.full_name
            )
            await email_sender.send_email(str(body.email), subject, text, html)
        except Exception:
            logger.exception("Assessment invite email to %s failed", body.email)
    return RecipientCreatedResponse(
        recipient=RecipientOut.model_validate(rec), link=link, token=raw
    )


@router.get("/{assessment_id}/recipients", response_model=list[RecipientOut])
async def list_assessment_recipients(
    assessment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecipientOut]:
    await _owned_assessment_or_404(db, user, assessment_id)
    return [RecipientOut.model_validate(r) for r in await client_link_service.list_for_assessment(db, assessment_id)]


@router.delete("/{assessment_id}/recipients/{recipient_id}", status_code=204)
async def revoke_assessment_recipient(
    assessment_id: int,
    recipient_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_assessment_or_404(db, user, assessment_id)
    if not await client_link_service.revoke(db, recipient_id, assessment_id):
        raise HTTPException(status_code=404, detail="Recipient not found")
    return Response(status_code=204)
