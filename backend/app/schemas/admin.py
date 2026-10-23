from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentListItem(BaseModel):
    id: int
    status: str = Field(min_length=1, max_length=30)
    current_axis: str | None = Field(default=None, max_length=50)
    company_name: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=255)
    size: str = Field(min_length=1, max_length=255)
    region: str | None = Field(default=None, max_length=120)
    overall_maturity_band: str | None = Field(default=None, max_length=40)
    # Latest passwordless client link for this assessment (if any). status ∈ sent|opened|completed;
    # recipient_name/role identify who it was sent to. All None when never sent to a client.
    recipient_status: str | None = Field(default=None, max_length=20)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_role: str | None = Field(default=None, max_length=200)
    # False when the row is visible only because it was shared with the caller (not their own).
    owned: bool = True
    created_at: datetime
    updated_at: datetime


class AssessmentsListResponse(BaseModel):
    items: list[AssessmentListItem]
    limit: int
    offset: int
