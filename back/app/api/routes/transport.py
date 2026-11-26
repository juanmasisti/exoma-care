import datetime as dt
from contextlib import contextmanager
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.logistics_dependencies import lab_administrator, transporter
from app.api.routes.extraction_centers import get_clock
from app.api.routes.sample_sets import get_sample_set_assigner
from app.config import get_settings
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.route_optimizer import RouteOptimizer, RouteOptimizerError
from app.domain.interfaces.sample_set_hooks import SampleSetAssigner
from app.infrastructure.adapters.route_optimizer_client import RouteOptimizerClient
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_route_repository import SQLAlchemyRouteRepository
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.use_cases.routes import RoutePreviewService
from app.use_cases.transport import Conflict, InvalidDay, NotFound, TransportService

router = APIRouter(prefix="/api/transport", tags=["transporte"])


def get_route_optimizer() -> RouteOptimizer:
    return RouteOptimizerClient(get_settings().recorridos_api_url)


def get_service(session: Session = Depends(get_database_session),
                optimizer: RouteOptimizer = Depends(get_route_optimizer)) -> TransportService:
    settings = get_settings()
    centers = SQLAlchemyExtractionCenterRepository(session)
    route_preview = RoutePreviewService(centers, optimizer,
                                        (settings.central_lab_latitude, settings.central_lab_longitude))
    return TransportService(SQLAlchemyRouteRepository(session), SQLAlchemySampleRepository(session), centers,
                            route_preview)


@contextmanager
def http_errors():
    try:
        yield
    except InvalidDay as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except NotFound as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except RouteOptimizerError as exc:
        raise HTTPException(502, detail=str(exc)) from exc


class DailyRouteRequest(BaseModel):
    date: dt.date


class DailyRouteSummary(BaseModel):
    id: int
    date: dt.date
    province_id: int
    province: str
    status: str
    arrived_at: dt.datetime | None
    stops: int
    picked_up: int


class CenterSummary(BaseModel):
    id: int
    name: str
    address: str
    city: str


class StopCenter(CenterSummary):
    latitude: float
    longitude: float


class StopSample(BaseModel):
    code: str
    volume_ml: Decimal
    taken_at: dt.datetime | None


class StopResponse(BaseModel):
    id: int
    sequence: int
    center: StopCenter
    picked_up_at: dt.datetime | None
    sample_codes: list[str]
    samples: list[StopSample]


class CentralLab(BaseModel):
    address: str
    latitude: float
    longitude: float


class RouteDetailResponse(BaseModel):
    id: int
    date: dt.date
    province_id: int
    province: str
    status: str
    arrived_at: dt.datetime | None
    stops: list[StopResponse]
    next_stop_id: int | None
    on_board: list[str]
    # Partida y destino del recorrido, para el mapa de la orden.
    central_lab: CentralLab


class PickupReceipt(BaseModel):
    route_id: int
    stop_id: int
    center: CenterSummary
    picked_up_at: dt.datetime
    sample_codes: list[str]


class ArrivalReceipt(BaseModel):
    route_id: int
    arrived_at: dt.datetime
    received_codes: list[str]


@router.post("/daily-routes", status_code=201, response_model=list[DailyRouteSummary])
def generate_daily_routes(payload: DailyRouteRequest, response: Response,
                          _admin: AuthenticatedUser = Depends(lab_administrator),
                          service: TransportService = Depends(get_service)):
    with http_errors():
        created, routes = service.generar_orden_del_dia(payload.date)
    if not created:
        response.status_code = 200
    return routes


@router.get("/daily-routes", response_model=list[DailyRouteSummary])
def list_daily_routes(date: dt.date, _admin: AuthenticatedUser = Depends(lab_administrator),
                      service: TransportService = Depends(get_service)):
    return service.listar(date)


# PROVISORIO (decisión 016): `province_id` va en el pedido hasta que el rol transporter tenga provincia.
@router.get("/my-route", response_model=RouteDetailResponse)
def my_route(date: dt.date, province_id: int, _actor: AuthenticatedUser = Depends(transporter),
             service: TransportService = Depends(get_service)):
    with http_errors():
        route = service.mi_recorrido(date, province_id)
    settings = get_settings()
    return {**route, "central_lab": {"address": settings.central_lab_address,
                                     "latitude": settings.central_lab_latitude,
                                     "longitude": settings.central_lab_longitude}}


@router.post("/daily-routes/{route_id}/stops/{stop_id}/pickup", response_model=PickupReceipt)
def pick_up(route_id: int, stop_id: int, actor: AuthenticatedUser = Depends(transporter),
            service: TransportService = Depends(get_service), now: dt.datetime = Depends(get_clock)):
    with http_errors():
        return service.retirar(route_id, stop_id, actor.id, now)


@router.post("/daily-routes/{route_id}/arrival", response_model=ArrivalReceipt)
def arrival(route_id: int, actor: AuthenticatedUser = Depends(transporter),
            service: TransportService = Depends(get_service), now: dt.datetime = Depends(get_clock),
            assigner: SampleSetAssigner = Depends(get_sample_set_assigner)):
    with http_errors():
        return service.registrar_llegada(route_id, actor.id, now, assigner)
