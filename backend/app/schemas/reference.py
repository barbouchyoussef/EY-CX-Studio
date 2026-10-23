from pydantic import BaseModel, Field


class ReferenceOption(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)


class ReferenceOptionsResponse(BaseModel):
    sectors: list[ReferenceOption]
    company_sizes: list[ReferenceOption]
    regions: list[ReferenceOption] = []
