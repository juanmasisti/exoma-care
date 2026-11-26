"""Avisos del circuito de estudios: siempre después de confirmar y sin romper la operación."""

import logging
from collections.abc import Awaitable, Callable

from app.domain.entities.study_request import StudyRequest

logger = logging.getLogger(__name__)


class NoStudyNotifications:
    """Sin avisos (tests y entornos sin servicio de avisos)."""

    async def reanalisis_solicitado(self, study: StudyRequest) -> None:
        return None

    async def estudio_habilitado(self, study: StudyRequest) -> None:
        return None


async def notify(send: Callable[[StudyRequest], Awaitable[None]], study: StudyRequest) -> None:
    """El aviso es best effort: si falla, se registra y la operación ya confirmada sigue en pie."""
    try:
        await send(study)
    except Exception:  # noqa: BLE001
        logger.exception("Falló el aviso del estudio %s.", study.id)
