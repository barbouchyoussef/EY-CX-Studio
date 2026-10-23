from pydantic import BaseModel, Field


class StartAssessmentRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    # Optional: if omitted, the backend will try to infer them via the LLM using values in DB.
    sector: str | None = Field(default=None, min_length=1, max_length=120)
    size: str | None = Field(default=None, min_length=1, max_length=50)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_profile: str | None = Field(default=None, min_length=1, max_length=40)
    language: str = Field(default="fr", min_length=2, max_length=10)


class StartAssessmentResponse(BaseModel):
    assessment_id: int


class CompanyInfo(BaseModel):
    id: int
    name: str
    sector: str
    size: str
    region: str | None = None


class AxisProgress(BaseModel):
    axis: str
    covered: int
    total: int


class AssessmentResponse(BaseModel):
    id: int
    status: str
    current_axis: str | None
    state_version: int
    overall_maturity_band: str | None = None
    company: CompanyInfo
    progress: list[AxisProgress]


class NextQuestionResponse(BaseModel):
    status: str
    axis: str | None = None
    question: str | None = None
    message: str | None = None
    options: list[str] | None = None


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)
    expected_axis: str | None = Field(default=None, min_length=1, max_length=100)
    expected_version: int | None = Field(default=None, ge=1)


class AnswerResponse(BaseModel):
    status: str
    axis: str | None
    covered: list[int]
    confidence: float | None = None
