from datetime import datetime

from pydantic import BaseModel, Field


class AxisMemoryItem(BaseModel):
    axis: str = Field(min_length=1, max_length=50)
    summary: str
    updated_at: datetime


class AssessmentMemoryResponse(BaseModel):
    assessment_id: int
    items: list[AxisMemoryItem]
