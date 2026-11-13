from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel

from app.api.catalog_dependencies import require_roles
from app.api.routes.extraction_centers import get_clock
from app.config import get_settings
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.courier import Courier, CourierError, PickupStatus
from app.infrastructure.adapters.fedex_client import FedExClient

# PROVISORIO para la demo (decisión 012): en T06 se reemplaza por el flujo del lote.
router = APIRouter(prefix="/api/shipments", tags=["envíos"])
lab_administrator = require_roles(UserRole.LAB_ADMINISTRATOR)


def get_courier() -> Courier:
    settings = get_settings()
    password = settings.fedex_pass.get_secret_value() if settings.fedex_pass else ""
    if not (settings.fedex_url and settings.fedex_user and password):
        raise HTTPException(502, detail="FedEx no está configurado.")
    return FedExClient(settings.fedex_url, settings.fedex_user, password)


class PickupRequest(BaseModel):
    scheduled_at: AwareDatetime


class PickupCreatedResponse(BaseModel):
    pickup_id: UUID


class PickupStatusResponse(BaseModel):
    pickup_id: UUID
    status: PickupStatus


@router.post("/pickups", status_code=201, response_model=PickupCreatedResponse)
def schedule_pickup(payload: PickupRequest, _actor: AuthenticatedUser = Depends(lab_administrator),
                    courier: Courier = Depends(get_courier), now: datetime = Depends(get_clock)):
    # Error nuestro: no se le manda a FedEx una fecha que ya pasó.
    if payload.scheduled_at <= now:
        raise HTTPException(422, detail="La fecha del retiro tiene que ser futura.")
    try:
        pickup_id = courier.programar_retiro(get_settings().central_lab_address, payload.scheduled_at)
    except CourierError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return {"pickup_id": pickup_id}


@router.get("/pickups/{pickup_id}", response_model=PickupStatusResponse)
def pickup_status(pickup_id: UUID, _actor: AuthenticatedUser = Depends(lab_administrator),
                  courier: Courier = Depends(get_courier)):
    try:
        status = courier.estado_retiro(str(pickup_id))
    except CourierError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return {"pickup_id": pickup_id, "status": status}
