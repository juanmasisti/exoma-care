from contextlib import contextmanager
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.logistics_dependencies import lab_administrator
from app.api.routes.extraction_centers import get_clock
from app.config import get_settings
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.courier import Courier
from app.domain.interfaces.health_ministry import HealthMinistry
from app.domain.interfaces.sample_set_hooks import SampleSetClosedHandler
from app.infrastructure.adapters.fedex_client import FedExClient
from app.infrastructure.adapters.simulated_health_ministry import SimulatedHealthMinistry
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_shipment_repository import SQLAlchemyShipmentRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.use_cases.shipments import Conflict, ExternalServiceError, InvalidPickup, NotFound, ShipmentService
from app.use_cases.studies import StudyService

router = APIRouter(prefix="/api/shipments", tags=["envíos"])


def get_health_ministry() -> HealthMinistry:
    return SimulatedHealthMinistry()  # SIMULADO (decisión 012)


def get_shipment_service(session: Session = Depends(get_database_session),
                         ministry: HealthMinistry = Depends(get_health_ministry)) -> ShipmentService:
    settings = get_settings()
    return ShipmentService(SQLAlchemyShipmentRepository(session), SQLAlchemyPatientRepository(session),
                           SQLAlchemySampleRepository(session), StudyService(SQLAlchemyStudyRepository(session)),
                           ministry, SQLAlchemyExtractionCenterRepository(session), settings.shipment_files_dir,
                           settings.central_lab_address)


# Enganche que usa el armado de lotes (T05) con Depends: corre en la sesión del pedido de la llegada.
def get_sample_set_closed_handler(service: ShipmentService = Depends(get_shipment_service)) -> SampleSetClosedHandler:
    return service


def get_courier() -> Courier:
    settings = get_settings()
    password = settings.fedex_pass.get_secret_value() if settings.fedex_pass else ""
    if not (settings.fedex_url and settings.fedex_user and password):
        raise HTTPException(502, detail="FedEx no está configurado.")
    return FedExClient(settings.fedex_url, settings.fedex_user, password)


@contextmanager
def http_errors():
    try:
        yield
    except NotFound as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except InvalidPickup as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(502, detail=str(exc)) from exc


class PickupRequest(BaseModel):
    scheduled_at: AwareDatetime


class ShipmentResponse(BaseModel):
    id: int
    status: str
    has_csv: bool
    has_authorization: bool
    pickup_at: datetime | None
    courier_pickup_id: str | None


@router.get("/{sample_set_id}", response_model=ShipmentResponse)
def shipment(sample_set_id: int, _actor: AuthenticatedUser = Depends(lab_administrator),
             service: ShipmentService = Depends(get_shipment_service)):
    with http_errors():
        return service.envio(sample_set_id)


@router.post("/{sample_set_id}/authorization", response_model=ShipmentResponse)
def request_authorization(sample_set_id: int, _actor: AuthenticatedUser = Depends(lab_administrator),
                          service: ShipmentService = Depends(get_shipment_service)):
    with http_errors():
        return service.autorizar(sample_set_id)


@router.get("/{sample_set_id}/csv", response_class=FileResponse)
def download_csv(sample_set_id: int, _actor: AuthenticatedUser = Depends(lab_administrator),
                 service: ShipmentService = Depends(get_shipment_service)):
    with http_errors():
        path = service.archivo(sample_set_id, "csv_path")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("/{sample_set_id}/authorization.pdf", response_class=FileResponse)
def download_authorization(sample_set_id: int, _actor: AuthenticatedUser = Depends(lab_administrator),
                           service: ShipmentService = Depends(get_shipment_service)):
    with http_errors():
        path = service.archivo(sample_set_id, "authorization_pdf_path")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.post("/{sample_set_id}/pickup", response_model=ShipmentResponse)
def schedule_pickup(sample_set_id: int, payload: PickupRequest, _actor: AuthenticatedUser = Depends(lab_administrator),
                    service: ShipmentService = Depends(get_shipment_service), courier: Courier = Depends(get_courier),
                    now: datetime = Depends(get_clock)):
    with http_errors():
        return service.programar_retiro(sample_set_id, payload.scheduled_at, now, courier)


@router.post("/{sample_set_id}/refresh", response_model=ShipmentResponse)
def refresh_pickup(sample_set_id: int, actor: AuthenticatedUser = Depends(lab_administrator),
                   service: ShipmentService = Depends(get_shipment_service), courier: Courier = Depends(get_courier),
                   now: datetime = Depends(get_clock)):
    with http_errors():
        return service.actualizar_estado(sample_set_id, now, courier, actor.id)
