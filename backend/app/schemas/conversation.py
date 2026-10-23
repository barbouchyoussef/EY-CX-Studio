from datetime import datetime

from pydantic import BaseModel, Field


class MessageItem(BaseModel):
    id: int
    role: str = Field(min_length=1, max_length=30)
    axis: str | None = Field(default=None, max_length=50)
    content: str
    created_at: datetime


class MessagesResponse(BaseModel):
    assessment_id: int
    items: list[MessageItem]
