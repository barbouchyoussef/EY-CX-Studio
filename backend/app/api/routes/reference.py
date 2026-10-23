from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.reference import ReferenceOptionsResponse
from app.repositories.company_size_repository import CompanySizeRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.sector_repository import SectorRepository

router = APIRouter(prefix="/reference")


@router.get("/options", response_model=ReferenceOptionsResponse)
async def get_reference_options(db: AsyncSession = Depends(get_db)) -> ReferenceOptionsResponse:
    sectors = await SectorRepository(db).list_options()
    sizes = await CompanySizeRepository(db).list_options()
    regions = await RegionRepository(db).list_options()
    return ReferenceOptionsResponse(
        sectors=[{"code": s.code, "label": s.name} for s in sectors],
        company_sizes=[{"code": cs.code, "label": cs.name} for cs in sizes],
        regions=[{"code": r.name, "label": r.name} for r in regions],
    )
