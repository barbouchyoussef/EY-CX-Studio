from pydantic import BaseModel, Field


class CapabilityBase(BaseModel):
    axis_id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(
        default=None,
        title="Capability definition",
        description=(
            "Defines what this capability means. Used by the LLM to understand the business intent "
            "and separate it from adjacent capabilities."
        ),
    )
    evidence_required: str | None = Field(
        default=None,
        title="Evidence signals",
        description="Examples of concrete proof the LLM should recognize. These are semantic signals, not strict keywords.",
    )
    question_guidelines: str | None = Field(
        default=None,
        title="Question strategy",
        description=(
            "Internal guidance used by the LLM to generate the next question. "
            "Describe the discovery goal, probing approach, and maturity signals to test. "
            "This is not a fixed script shown to the client."
        ),
    )
    sort_order: int = Field(ge=1)


class CapabilityCreate(CapabilityBase):
    pass


class CapabilityUpdate(BaseModel):
    axis_id: int | None = Field(default=None, ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(
        default=None,
        title="Capability definition",
        description="Defines what this capability means for LLM scoring and adjacent-capability separation.",
    )
    evidence_required: str | None = Field(
        default=None,
        title="Evidence signals",
        description="Examples of concrete proof the LLM should recognize. These are semantic signals, not strict keywords.",
    )
    question_guidelines: str | None = Field(
        default=None,
        title="Question strategy",
        description=(
            "Internal guidance used by the LLM to generate the next question. "
            "Describe the discovery goal, probing approach, and maturity signals to test."
        ),
    )
    sort_order: int | None = Field(default=None, ge=1)


class CapabilityRead(CapabilityBase):
    id: int


class CapabilityMaturityRubricBase(BaseModel):
    capability_id: int = Field(ge=1)
    maturity_level_id: int = Field(ge=1)
    description: str = Field(min_length=1)
    card_summary: str | None = None


class CapabilityMaturityRubricCreate(CapabilityMaturityRubricBase):
    pass


class CapabilityMaturityRubricUpdate(BaseModel):
    capability_id: int | None = Field(default=None, ge=1)
    maturity_level_id: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, min_length=1)
    card_summary: str | None = None


class CapabilityMaturityRubricRead(CapabilityMaturityRubricBase):
    id: int


class CapabilityQuickWinTemplateBase(BaseModel):
    capability_id: int = Field(ge=1)
    maturity_level_id: int = Field(ge=1)
    quick_win_guideline: str = Field(
        min_length=1,
        title="Quick win guideline",
        description="Admin-managed quick-win action direction used by the final report quick-win layer.",
    )
    after_text: str | None = Field(
        default=None,
        title="After text",
        description="Admin-managed target state shown as the quick-win after text.",
    )
    owner_hint: str | None = Field(
        default=None,
        title="Owner hint",
        description="Suggested owner role for this quick win.",
    )
    timeline_hint: str | None = Field(
        default=None,
        title="Timeline hint",
        description="Suggested quick-win timing or sequencing hint.",
    )
    active: bool = Field(default=True)


class CapabilityQuickWinTemplateCreate(CapabilityQuickWinTemplateBase):
    pass


class CapabilityQuickWinTemplateUpdate(BaseModel):
    capability_id: int | None = Field(default=None, ge=1)
    maturity_level_id: int | None = Field(default=None, ge=1)
    quick_win_guideline: str | None = Field(default=None, min_length=1)
    after_text: str | None = None
    owner_hint: str | None = None
    timeline_hint: str | None = None
    active: bool | None = None


class CapabilityQuickWinTemplateRead(CapabilityQuickWinTemplateBase):
    id: int
