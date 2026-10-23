from pydantic import BaseModel, Field


class AxisBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    question_guidelines: str | None = None
    sort_order: int = Field(ge=1)


class AxisCreate(AxisBase):
    pass


class AxisUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    question_guidelines: str | None = None
    sort_order: int | None = Field(default=None, ge=1)


class AxisRead(AxisBase):
    id: int


class SectorBase(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class SectorCreate(SectorBase):
    pass


class SectorUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class SectorRead(SectorBase):
    id: int


class CompanySizeBase(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class CompanySizeCreate(CompanySizeBase):
    pass


class CompanySizeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class CompanySizeRead(CompanySizeBase):
    id: int


class RegionBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class RegionCreate(RegionBase):
    pass


class RegionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class RegionRead(RegionBase):
    id: int


class MaturityLevelBase(BaseModel):
    level_number: int = Field(ge=1, le=99)
    label: str = Field(min_length=1, max_length=50)
    description: str | None = None


class MaturityLevelCreate(MaturityLevelBase):
    pass


class MaturityLevelUpdate(BaseModel):
    level_number: int | None = Field(default=None, ge=1, le=99)
    label: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None


class MaturityLevelRead(MaturityLevelBase):
    id: int
