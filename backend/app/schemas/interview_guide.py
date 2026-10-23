from pydantic import BaseModel, Field, field_validator
from typing import Any

class GenerateInterviewGuideRequest(BaseModel):
    assessment_id: int | None = Field(default=None, description="Optional link to past assessment history")
    company_name: str = Field(min_length=1, max_length=255)
    sector: str | None = Field(default=None, min_length=1, max_length=120)
    size: str | None = Field(default=None, min_length=1, max_length=50)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    language: str = Field(default="fr", min_length=2, max_length=10)
    profile: str = Field(default="CEO", min_length=2, max_length=100, description="Target stakeholder profile (CEO, Marketing, Call Center, IT Lead, or a custom profile name)")
    custom_context: str | None = Field(default=None, max_length=5000, description="Remarks regarding the client / things to include")
    custom_profile_description: str | None = Field(default=None, max_length=5000, description="Specifications/persona of this profile if custom")

class InterviewGuideQuestionItem(BaseModel):
    id: str | None = Field(default=None, description="Unique ID for the question item")
    question: str = Field(description="The open-ended interview question text")
    rationale: str = Field(description="The context or reason why the consultant should ask this question")
    follow_up: str = Field(description="Specific follow-up notes pointing back to client's past responses or gaps")
    isAnswered: bool | None = Field(default=False, description="Whether the question is answered")
    answerNote: str | None = Field(default=None, description="Notes written by the consultant for this question")

    @field_validator("question", "rationale", mode="before")
    @classmethod
    def coerce_to_string(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("follow_up", mode="before")
    @classmethod
    def coerce_follow_up(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            # Join multiple follow-up probes with bullet points and newlines
            return "\n".join(f"- {str(item).strip()}" for item in v if item)
        return str(v).strip()

class InterviewGuideResponse(BaseModel):
    id: int | None = Field(default=None, description="The saved database guide ID if stored")
    assessment_id: int | None = Field(default=None, description="Linked assessment ID (if generated from history)")
    # Persisted cross-reference briefing {markdown, generated_at, generated_by}, when it was run.
    insights: dict | None = Field(default=None, description="Saved insights briefing, if generated")
    company_name: str
    # Who the guide is for. Optional only because guides saved before this was returned have no
    # profile in their stored payload; the GET fills it from the guide's own column, which is the
    # authoritative value. Without it the client had nothing to send back on save and fell back to
    # its form default, silently relabelling every non-CEO interview as "CEO".
    profile: str | None = Field(default=None, description="Target stakeholder profile")
    language: str
    executive_summary: str = Field(description="Executive summary of the client's current status and remarks")
    unanswered_areas: list[str] = Field(description="Key capabilities or areas of focus that remain unclear")
    
    # Detailed section split
    introduction_questions: list[InterviewGuideQuestionItem] = Field(description="Section 1: Warm-up and general state questions")
    manage_questions: list[InterviewGuideQuestionItem] = Field(description="Section 2: Detailed Manage axis questions")
    analyze_questions: list[InterviewGuideQuestionItem] = Field(description="Section 3: Detailed Analyze axis questions")
    improve_questions: list[InterviewGuideQuestionItem] = Field(description="Section 4: Detailed Improve axis questions")
    closure_questions: list[InterviewGuideQuestionItem] = Field(description="Section 5: Closure and wrap-up questions")

    @field_validator("executive_summary", mode="before")
    @classmethod
    def coerce_summary(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("unanswered_areas", mode="before")
    @classmethod
    def coerce_unanswered_areas(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item).strip() for item in v if item]
        return [str(v).strip()]

class SaveInterviewGuideRequest(BaseModel):
    id: int | None = Field(default=None, description="Optional ID if updating an existing guide")
    assessment_id: int | None = Field(default=None, description="Linked assessment ID")
    company_name: str
    profile: str
    language: str
    payload: dict

class InterviewGuideListItem(BaseModel):
    id: int
    assessment_id: int | None
    company_name: str
    profile: str
    language: str
    created_at: Any
    updated_at: Any
    has_insights: bool = False
    owned: bool = True  # false when the guide is only visible because it was shared with the caller
    owner_name: str | None = None  # the consultant who created it
    question_count: int = 0  # total questions across all sections of the guide

    class Config:
        from_attributes = True
