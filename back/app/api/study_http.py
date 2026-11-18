"""Traduce los errores de los casos de uso de solicitudes/pagos/cupones a respuestas HTTP."""

from fastapi import HTTPException

from app.infrastructure.external_services.errors import ExternalServiceError
from app.use_cases.study_request_errors import StudyRequestConflictError

# Códigos de la API externa que se informan tal cual; el resto (401, 403, 5xx) es un problema
# de configuración o de disponibilidad del servicio y se informa como 502.
_PASS_THROUGH = frozenset({400, 404, 409, 422, 503})


def to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, StudyRequestConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, ExternalServiceError):
        status = exc.status_code if exc.status_code in _PASS_THROUGH else 502
        return HTTPException(status_code=status, detail=str(exc))
    raise exc


HANDLED_ERRORS = (
    PermissionError,
    LookupError,
    StudyRequestConflictError,
    ValueError,
    ExternalServiceError,
)
