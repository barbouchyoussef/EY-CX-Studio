from pydantic import BaseModel, Field, field_validator


class BookConsultationRequest(BaseModel):
    assessment_id: int = Field(gt=0)
    client_name: str = Field(min_length=1, max_length=255)

    @field_validator("client_name")
    @classmethod
    def client_name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Client name is required")
        return cleaned


class BookConsultationResponse(BaseModel):
    gmail_url: str
