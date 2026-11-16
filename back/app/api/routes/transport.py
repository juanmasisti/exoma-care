from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import ExtractionCenterResponse
from app.config import get_settings
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.route_optimizer import RouteOptimizer, RouteOptimizerError
from app.infrastructure.adapters.route_optimizer_client import RouteOptimizerClient
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.use_cases.routes import RoutePreviewService

router = APIRouter(prefix="/api/transport", tags=["transporte"])
# PROVISORIO (decisión 009): administrativo hasta que exista el rol transporter (Camila, EC-03).
transporter = require_roles(UserRole.LAB_ADMINISTRATOR)


def get_route_optimizer() -> RouteOptimizer:
    return RouteOptimizerClient(get_settings().recorridos_api_url)


def get_service(session: Session = Depends(get_database_session),
                optimizer: RouteOptimizer = Depends(get_route_optimizer)) -> RoutePreviewService:
    settings = get_settings()
    return RoutePreviewService(SQLAlchemyExtractionCenterRepository(session), optimizer,
                               (settings.central_lab_latitude, settings.central_lab_longitude))


class RoutePreviewRequest(BaseModel):
    center_ids: list[PositiveInt] = Field(max_length=100)


# PROVISORIO para la demo: en T04 los centros salen de la orden del día, no del pedido.
@router.post("/route-preview", response_model=list[ExtractionCenterResponse])
def route_preview(payload: RoutePreviewRequest, _actor: AuthenticatedUser = Depends(transporter),
                  service: RoutePreviewService = Depends(get_service)):
    try:
        return service.order_centers(payload.center_ids)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except RouteOptimizerError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
