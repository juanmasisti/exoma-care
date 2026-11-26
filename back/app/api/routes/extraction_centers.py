from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.domain.entities.logistics import TIMEZONE
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.use_cases.extraction_centers import ExtractionCenterService

router = APIRouter(prefix="/api", tags=["centros de extracción y horarios"])
patient = require_roles(UserRole.PATIENT)


def get_service(session: Session = Depends(get_database_session)):
    return ExtractionCenterService(SQLAlchemyExtractionCenterRepository(session))


def get_clock() -> datetime:
    return datetime.now(TIMEZONE)


class ProvinceResponse(BaseModel):
    id: int
    name: str
    active_centers: int


class ExtractionCenterResponse(BaseModel):
    id: int
    name: str
    address: str
    city: str
    province_id: int
    latitude: float
    longitude: float
    phone: str | None


class SlotsResponse(BaseModel):
    center_id: int
    date: date
    business_day: bool
    holiday: str | None
    slots: list[datetime]


@router.get("/provinces", response_model=list[ProvinceResponse])
def list_provinces(_actor: AuthenticatedUser = Depends(patient),
                   service: ExtractionCenterService = Depends(get_service)):
    return service.centers.provinces()


@router.get("/extraction-centers", response_model=list[ExtractionCenterResponse])
def list_extraction_centers(province_id: PositiveInt | None = None, q: str = Query(default="", max_length=100),
                            _actor: AuthenticatedUser = Depends(patient),
                            service: ExtractionCenterService = Depends(get_service)):
    return service.centers.active_centers(province_id, q)


@router.get("/extraction-centers/{center_id}/slots", response_model=SlotsResponse)
def center_slots(center_id: PositiveInt, day: date = Query(alias="date"),
                 _actor: AuthenticatedUser = Depends(patient),
                 service: ExtractionCenterService = Depends(get_service), now: datetime = Depends(get_clock)):
    try:
        return service.slots(center_id, day, now)
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
