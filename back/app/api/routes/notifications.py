from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_notification_service
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.notification_client import (
    TTPSNotificationClient,
)

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])
super_admin = require_roles(UserRole.SUPER_ADMIN)


@router.get("/health")
async def notification_health(
    _actor: AuthenticatedUser = Depends(super_admin),
    service: TTPSNotificationClient = Depends(get_notification_service),
) -> dict[str, Any]:
    try:
        return await service.verificar_conexion()
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/pendientes")
async def list_pending_notifications(
    limite: int = Query(default=25, ge=1, le=100),
    _actor: AuthenticatedUser = Depends(super_admin),
    service: TTPSNotificationClient = Depends(get_notification_service),
) -> dict[str, Any]:
    try:
        return await service.listar_pendientes(limite)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{aviso_id}")
async def get_notification_status(
    aviso_id: UUID,
    _actor: AuthenticatedUser = Depends(super_admin),
    service: TTPSNotificationClient = Depends(get_notification_service),
) -> dict[str, Any]:
    try:
        return await service.consultar_estado(str(aviso_id))
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
