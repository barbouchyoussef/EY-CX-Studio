from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants import normalize_axis_code, normalize_axis_name
from app.db.models.axis import Axis
from app.db.models.company_size import CompanySize
from app.db.models.maturity_level import MaturityLevel
from app.db.models.region import Region
from app.db.models.sector import Sector
from app.dependencies.auth import require_admin
from app.dependencies.db import get_db
from app.schemas.admin_reference import (
    AxisCreate,
    AxisRead,
    AxisUpdate,
    CompanySizeCreate,
    CompanySizeRead,
    CompanySizeUpdate,
    MaturityLevelCreate,
    MaturityLevelRead,
    MaturityLevelUpdate,
    RegionCreate,
    RegionRead,
    RegionUpdate,
    SectorCreate,
    SectorRead,
    SectorUpdate,
)
from app.schemas.admin_ui_metadata import (
    AdminUiFieldMetadata,
    AdminUiMetadataResponse,
    AdminUiSectionMetadata,
)

# Every route here is admin-only, enforced on the router so a new endpoint added below
# is protected by default rather than by remembering to annotate it.
router = APIRouter(prefix="/admin/reference", dependencies=[Depends(require_admin)])


def _normalize(value: str) -> str:
    return value.strip().lower()


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


async def _handle_integrity_error(db: AsyncSession, entity_name: str) -> None:
    await db.rollback()
    raise HTTPException(status_code=409, detail=f"{entity_name} violates a unique or relational constraint.")


@router.get("/ui-metadata", response_model=AdminUiMetadataResponse)
def get_admin_ui_metadata() -> AdminUiMetadataResponse:
    return AdminUiMetadataResponse(
        capabilities=AdminUiSectionMetadata(
            title="Capabilities",
            help_text=(
                "Capability definition, evidence signals, and question strategy shape how the LLM understands, scores, and asks about each capability."
            ),
            fields={
                "description": AdminUiFieldMetadata(
                    label="Capability definition",
                    description=(
                        "Defines what this capability means. The LLM uses it to understand the business intent "
                        "and separate it from adjacent capabilities."
                    ),
                    button_label="Edit definition",
                    modal_title="Edit capability definition",
                    placeholder="Describe what this capability means and what business area it evaluates...",
                ),
                "evidence_required": AdminUiFieldMetadata(
                    label="Evidence signals",
                    description=(
                        "Examples of concrete proof the LLM should recognize. These are semantic signals, "
                        "not strict keywords."
                    ),
                    button_label="Edit signals",
                    modal_title="Edit evidence signals",
                    placeholder="List evidence signals separated by semicolons, for example: named owner; review cadence; action log...",
                ),
                "question_guidelines": AdminUiFieldMetadata(
                    label="Question strategy",
                    description=(
                        "Internal guidance for how the LLM should ask about this capability. "
                        "This is not a fixed client-facing script."
                    ),
                    button_label="Edit strategy",
                    modal_title="Edit question strategy",
                    placeholder="Write the internal questioning strategy used by the LLM...",
                )
            },
        ),
        axes=AdminUiSectionMetadata(
            title="Axes",
            help_text=(
                "Axis guidance defines the high-level meaning of Manage, Analyze, and Improve. "
                "The LLM uses it as context before focusing on the selected capability."
            ),
            fields={
                "description": AdminUiFieldMetadata(
                    label="Axis definition",
                    description="Defines what this axis means in the CX maturity model.",
                    button_label="Edit definition",
                    modal_title="Edit axis definition",
                    placeholder="Describe the scope and business meaning of this axis...",
                ),
                "question_guidelines": AdminUiFieldMetadata(
                    label="Axis question strategy",
                    description="Guides how the LLM should frame questions while it is inside this axis.",
                    button_label="Edit strategy",
                    modal_title="Edit axis question strategy",
                    placeholder="Write the questioning strategy for this axis...",
                ),
            },
        ),
        recommendations=AdminUiSectionMetadata(
            title="Quick win templates",
            help_text=(
                "Quick win templates are the single admin source for quick-win action direction, after text, owner hints, and sequencing hints. "
                "The before text is generated from assessment insights."
            ),
            fields={
                "quick_win_guideline": AdminUiFieldMetadata(
                    label="Quick win action",
                    description="The practical action the quick win should recommend in the final report.",
                    button_label="Edit action",
                    modal_title="Edit quick win action",
                    placeholder="Write the practical quick-win action...",
                ),
                "after_text": AdminUiFieldMetadata(
                    label="Expected outcome",
                    description="The improved state or business/customer outcome after this quick win is completed.",
                    button_label="Edit outcome",
                    modal_title="Edit expected outcome",
                    placeholder="Describe the expected outcome after this quick win...",
                ),
                "owner_hint": AdminUiFieldMetadata(
                    label="Suggested owner",
                    description="The role most likely to own this quick win.",
                    button_label="Edit owner",
                    modal_title="Edit suggested owner",
                    placeholder="Example: CX Lead, Insights Lead, Operations Lead...",
                ),
                "timeline_hint": AdminUiFieldMetadata(
                    label="Timing",
                    description="When this quick win should usually happen in the quick-win sequence.",
                    button_label="Edit timing",
                    modal_title="Edit timing",
                    placeholder="Example: earliest quick win, after first routine is in place...",
                ),
            },
        ),
    )


@router.get("/axes", response_model=list[AxisRead])
async def list_axes(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AxisRead]:
    result = await db.execute(select(Axis).order_by(Axis.sort_order.asc()).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [
        AxisRead(
            id=r.id,
            code=(normalize_axis_code(r.code) or r.code).lower(),
            name=normalize_axis_name(r.name) or r.name,
            description=r.description,
            question_guidelines=r.question_guidelines,
            sort_order=r.sort_order,
        )
        for r in rows
    ]


@router.get("/regions", response_model=list[RegionRead])
async def list_regions(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[RegionRead]:
    result = await db.execute(select(Region).order_by(Region.name.asc()).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [
        RegionRead(
            id=r.id,
            name=r.name,
        )
        for r in rows
    ]


@router.post("/regions", response_model=RegionRead)
async def create_region(payload: RegionCreate, db: AsyncSession = Depends(get_db)) -> RegionRead:
    row = Region(name=payload.name.strip())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Region")
    await db.refresh(row)
    return RegionRead(id=row.id, name=row.name)


@router.patch("/regions/{region_id}", response_model=RegionRead)
async def update_region(region_id: int, payload: RegionUpdate, db: AsyncSession = Depends(get_db)) -> RegionRead:
    result = await db.execute(select(Region).where(Region.id == region_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found")
    if payload.name is not None:
        row.name = payload.name.strip()
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Region")
    await db.refresh(row)
    return RegionRead(id=row.id, name=row.name)


@router.delete("/regions/{region_id}")
async def delete_region(region_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(Region).where(Region.id == region_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found")
    await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Region")
    return {"status": "deleted"}


@router.post("/axes", response_model=AxisRead)
async def create_axis(payload: AxisCreate, db: AsyncSession = Depends(get_db)) -> AxisRead:
    row = Axis(
        code=(normalize_axis_code(payload.code) or _normalize(payload.code)).lower(),
        name=normalize_axis_name(payload.name.strip()) or payload.name.strip(),
        description=_clean_optional_text(payload.description),
        question_guidelines=_clean_optional_text(payload.question_guidelines),
        sort_order=payload.sort_order,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Axis")
    await db.refresh(row)
    return AxisRead(
        id=row.id,
        code=(normalize_axis_code(row.code) or row.code).lower(),
        name=normalize_axis_name(row.name) or row.name,
        description=row.description,
        question_guidelines=row.question_guidelines,
        sort_order=row.sort_order,
    )


@router.patch("/axes/{axis_id}", response_model=AxisRead)
async def update_axis(axis_id: int, payload: AxisUpdate, db: AsyncSession = Depends(get_db)) -> AxisRead:
    result = await db.execute(select(Axis).where(Axis.id == axis_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Axis not found")

    if payload.code is not None:
        row.code = (normalize_axis_code(payload.code) or _normalize(payload.code)).lower()
    if payload.name is not None:
        row.name = normalize_axis_name(payload.name.strip()) or payload.name.strip()
    provided_fields = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    if "description" in provided_fields:
        row.description = _clean_optional_text(payload.description)
    if "question_guidelines" in provided_fields:
        row.question_guidelines = _clean_optional_text(payload.question_guidelines)
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Axis")
    await db.refresh(row)
    return AxisRead(
        id=row.id,
        code=(normalize_axis_code(row.code) or row.code).lower(),
        name=normalize_axis_name(row.name) or row.name,
        description=row.description,
        question_guidelines=row.question_guidelines,
        sort_order=row.sort_order,
    )


@router.delete("/axes/{axis_id}")
async def delete_axis(axis_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(Axis).where(Axis.id == axis_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Axis")
    return {"status": "deleted"}


@router.get("/sectors", response_model=list[SectorRead])
async def list_sectors(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[SectorRead]:
    result = await db.execute(select(Sector).order_by(Sector.name.asc()).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [SectorRead(id=r.id, code=r.code, name=r.name) for r in rows]


@router.post("/sectors", response_model=SectorRead)
async def create_sector(payload: SectorCreate, db: AsyncSession = Depends(get_db)) -> SectorRead:
    row = Sector(code=_normalize(payload.code), name=payload.name.strip())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Sector")
    await db.refresh(row)
    return SectorRead(id=row.id, code=row.code, name=row.name)


@router.patch("/sectors/{sector_id}", response_model=SectorRead)
async def update_sector(sector_id: int, payload: SectorUpdate, db: AsyncSession = Depends(get_db)) -> SectorRead:
    result = await db.execute(select(Sector).where(Sector.id == sector_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Sector not found")
    if payload.code is not None:
        row.code = _normalize(payload.code)
    if payload.name is not None:
        row.name = payload.name.strip()
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Sector")
    await db.refresh(row)
    return SectorRead(id=row.id, code=row.code, name=row.name)


@router.delete("/sectors/{sector_id}")
async def delete_sector(sector_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(Sector).where(Sector.id == sector_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Sector not found")
    await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Sector")
    return {"status": "deleted"}


@router.get("/company-sizes", response_model=list[CompanySizeRead])
async def list_company_sizes(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[CompanySizeRead]:
    result = await db.execute(select(CompanySize).order_by(CompanySize.name.asc()).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [CompanySizeRead(id=r.id, code=r.code, name=r.name) for r in rows]


@router.post("/company-sizes", response_model=CompanySizeRead)
async def create_company_size(payload: CompanySizeCreate, db: AsyncSession = Depends(get_db)) -> CompanySizeRead:
    row = CompanySize(code=_normalize(payload.code), name=payload.name.strip())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Company size")
    await db.refresh(row)
    return CompanySizeRead(id=row.id, code=row.code, name=row.name)


@router.patch("/company-sizes/{company_size_id}", response_model=CompanySizeRead)
async def update_company_size(company_size_id: int, payload: CompanySizeUpdate, db: AsyncSession = Depends(get_db)) -> CompanySizeRead:
    result = await db.execute(select(CompanySize).where(CompanySize.id == company_size_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Company size not found")
    if payload.code is not None:
        row.code = _normalize(payload.code)
    if payload.name is not None:
        row.name = payload.name.strip()
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Company size")
    await db.refresh(row)
    return CompanySizeRead(id=row.id, code=row.code, name=row.name)


@router.delete("/company-sizes/{company_size_id}")
async def delete_company_size(company_size_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(CompanySize).where(CompanySize.id == company_size_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Company size not found")
    await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Company size")
    return {"status": "deleted"}


@router.get("/maturity-levels", response_model=list[MaturityLevelRead])
async def list_maturity_levels(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MaturityLevelRead]:
    result = await db.execute(select(MaturityLevel).order_by(MaturityLevel.level_number.asc()).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [
        MaturityLevelRead(id=r.id, level_number=r.level_number, label=r.label, description=r.description)
        for r in rows
    ]


@router.post("/maturity-levels", response_model=MaturityLevelRead)
async def create_maturity_level(payload: MaturityLevelCreate, db: AsyncSession = Depends(get_db)) -> MaturityLevelRead:
    row = MaturityLevel(
        level_number=payload.level_number,
        label=payload.label.strip(),
        description=payload.description,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Maturity level")
    await db.refresh(row)
    return MaturityLevelRead(id=row.id, level_number=row.level_number, label=row.label, description=row.description)


@router.patch("/maturity-levels/{maturity_level_id}", response_model=MaturityLevelRead)
async def update_maturity_level(
    maturity_level_id: int,
    payload: MaturityLevelUpdate,
    db: AsyncSession = Depends(get_db),
) -> MaturityLevelRead:
    result = await db.execute(select(MaturityLevel).where(MaturityLevel.id == maturity_level_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Maturity level not found")
    if payload.level_number is not None:
        row.level_number = payload.level_number
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.description is not None:
        row.description = payload.description
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Maturity level")
    await db.refresh(row)
    return MaturityLevelRead(id=row.id, level_number=row.level_number, label=row.label, description=row.description)


@router.delete("/maturity-levels/{maturity_level_id}")
async def delete_maturity_level(maturity_level_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(MaturityLevel).where(MaturityLevel.id == maturity_level_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Maturity level not found")
    await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await _handle_integrity_error(db, "Maturity level")
    return {"status": "deleted"}
