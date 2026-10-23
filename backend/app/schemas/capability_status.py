from datetime import datetime

from pydantic import BaseModel, Field


class CapabilityStatusItem(BaseModel):
    id: int
    axis: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    maturity_level_id: int | None = None
    assessed: bool
    assessment_status: str = "not_assessed"
    covered: bool | None = None
    confidence: float
    evidence_text: str | None = None
    rationale: str | None = None
    updated_at: datetime | None = None


class CapabilitiesStatusResponse(BaseModel):
    assessment_id: int
    axis: str | None = None
    items: list[CapabilityStatusItem]


class CapabilityHighlightsResponse(BaseModel):
    assessment_id: int
    axis: str | None = None
    total_highlights: int
    items: list[CapabilityStatusItem]
