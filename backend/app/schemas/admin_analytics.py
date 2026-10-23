from datetime import date

from pydantic import BaseModel


class AnalyticsFilterSet(BaseModel):
    sector_code: str | None = None
    company_size_code: str | None = None
    status: str | None = None


class AnalyticsWindow(BaseModel):
    from_date: date
    to_date: date


class AnalyticsOverviewCounts(BaseModel):
    assessments: int
    completed: int
    active: int


class AnalyticsOverviewResponse(BaseModel):
    window: AnalyticsWindow
    filters: AnalyticsFilterSet
    counts: AnalyticsOverviewCounts
    maturity_distribution: dict[str, int]
    axis_avg_score_percent: dict[str, float]


class MaturityByCapabilityItem(BaseModel):
    capability_code: str
    capability_name: str
    axis: str
    n: int
    basic: int
    established: int
    advanced: int
    avg_confidence: float | None = None


class MaturityByCapabilityResponse(BaseModel):
    items: list[MaturityByCapabilityItem]


class TopSignalItem(BaseModel):
    capability_code: str
    capability_name: str
    axis: str
    count: int
    share_percent: float


class TopSignalsResponse(BaseModel):
    items: list[TopSignalItem]


class RecommendationThemeItem(BaseModel):
    theme: str
    count: int


class RecommendationThemesResponse(BaseModel):
    items: list[RecommendationThemeItem]


class SectorTrendItem(BaseModel):
    period: str
    assessments: int
    overall_avg_score: float
    basic: int
    established: int
    advanced: int


class SectorTrendsResponse(BaseModel):
    sector_code: str
    series: list[SectorTrendItem]


class MetabaseEmbedResponse(BaseModel):
    enabled: bool
    url: str | None = None
    token: str | None = None
    instance_url: str | None = None
