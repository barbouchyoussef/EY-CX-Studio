from datetime import date, datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies.auth import require_admin
from app.dependencies.db import get_db
from app.schemas.admin_analytics import (
    AnalyticsOverviewResponse,
    MetabaseEmbedResponse,
    MaturityByCapabilityResponse,
    RecommendationThemesResponse,
    SectorTrendsResponse,
    TopSignalsResponse,
)
from app.services.analytics import AdminAnalyticsService

# Every route here is admin-only, enforced on the router so a new endpoint added below
# is protected by default rather than by remembering to annotate it.
router = APIRouter(prefix="/admin/analytics", dependencies=[Depends(require_admin)])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _build_metabase_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url(signature)}"


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def analytics_overview(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOverviewResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).overview(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            company_size_code=company_size_code,
            status=status,
        )
    )


@router.get("/maturity-by-capability", response_model=MaturityByCapabilityResponse)
async def maturity_by_capability(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    axis: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> MaturityByCapabilityResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).maturity_by_capability(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            company_size_code=company_size_code,
            axis=axis,
        )
    )


@router.get("/top-pain-points", response_model=TopSignalsResponse)
async def top_pain_points(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TopSignalsResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).top_signals(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            company_size_code=company_size_code,
            limit=limit,
            signal="pain",
        )
    )


@router.get("/top-strengths", response_model=TopSignalsResponse)
async def top_strengths(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TopSignalsResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).top_signals(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            company_size_code=company_size_code,
            limit=limit,
            signal="strength",
        )
    )


@router.get("/recommendation-themes", response_model=RecommendationThemesResponse)
async def recommendation_themes(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    axis: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> RecommendationThemesResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).recommendation_themes(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            company_size_code=company_size_code,
            axis=axis,
            limit=limit,
        )
    )


@router.get("/sector-trends", response_model=SectorTrendsResponse)
async def sector_trends(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str = Query(...),
    group_by: str = Query(default="month", pattern="^(month|quarter)$"),
    db: AsyncSession = Depends(get_db),
) -> SectorTrendsResponse:
    return await db.run_sync(
        lambda sync_db: AdminAnalyticsService(sync_db).sector_trends(
            from_date=from_date,
            to_date=to_date,
            sector_code=sector_code,
            group_by=group_by,
        )
    )


@router.get("/metabase-embed", response_model=MetabaseEmbedResponse)
def metabase_embed_url(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    sector_code: str | None = Query(default=None),
    company_size_code: str | None = Query(default=None),
    region_code: str | None = Query(default=None),
) -> MetabaseEmbedResponse:
    settings = get_settings()
    if not settings.metabase_site_url or not settings.metabase_embed_secret or not settings.metabase_dashboard_id:
        return MetabaseEmbedResponse(enabled=False, url=None, token=None, instance_url=None)

    now = datetime.now(timezone.utc)
    params: dict[str, str] = {}
    if sector_code:
        params["sector"] = sector_code
    if company_size_code:
        params["company_size"] = company_size_code
    if region_code:
        params["region"] = region_code

    payload = {
        "resource": {"dashboard": settings.metabase_dashboard_id},
        "params": params,
        "_embedding_params": {
            "date": "enabled",
            "sector": "enabled",
            "company_size": "enabled",
            "region": "enabled",
        },
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    token = _build_metabase_jwt(payload, settings.metabase_embed_secret)
    site_url = settings.metabase_site_url.rstrip("/")
    url = f"{site_url}/embed/dashboard/{quote(token)}#bordered=true&titled=false&theme=light"
    return MetabaseEmbedResponse(enabled=True, url=url, token=token, instance_url=site_url)
