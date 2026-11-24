import datetime as dt
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.logistics_dependencies import lab_administrator
from app.config import get_settings
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.route_optimizer import RouteOptimizer, RouteOptimizerError
from app.infrastructure.adapters.route_optimizer_client import RouteOptimizerClient
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_route_repository import SQLAlchemyRouteRepository
from app.use_cases.routes import RoutePreviewService
from app.use_cases.transport import InvalidDay, TransportService

router = APIRouter(prefix="/api/transport", tags=["transporte"])


def get_route_optimizer() -> RouteOptimizer:
    return RouteOptimizerClient(get_settings().recorridos_api_url)


def get_service(session: Session = Depends(get_database_session),
                optimizer: RouteOptimizer = Depends(get_route_optimizer)) -> TransportService:
    settings = get_settings()
    centers = SQLAlchemyExtractionCenterRepository(session)
    route_preview = RoutePreviewService(centers, optimizer,
                                        (settings.central_lab_latitude, settings.central_lab_longitude))
    return TransportService(SQLAlchemyRouteRepository(session), centers, route_preview)


@contextmanager
def http_errors():
    try:
        yield
    except InvalidDay as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except LookupError as exc:  # un centro se dio de baja mientras se generaba la orden
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
