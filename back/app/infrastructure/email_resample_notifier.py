import asyncio
import logging
from collections.abc import Callable
from typing import Protocol

from app.domain.dtos.notification_dto import NotificacionInput, NotificacionResultado
from app.domain.entities.logistics import study_code
from app.domain.interfaces.study_repository import StudyRepository

logger = logging.getLogger(__name__)


class Avisos(Protocol):
    """Lo que se usa de EnviarNotificacionUseCase (Camila), sin importar casos de uso desde infraestructura."""

    async def execute(self, datos: NotificacionInput) -> NotificacionResultado: ...


class EmailResampleNotifier:
    """Manda el aviso de remuestreo con el servicio de avisos de Camila (decisión 014)."""

    def __init__(self, studies: StudyRepository, crear_avisos: Callable[[], Avisos]):
        self.studies = studies
        # Se arma al avisar: sin clave de avisos, el webhook y el seguimiento siguen andando.
        self.crear_avisos = crear_avisos

    def avisar_remuestreo(self, study_id: int, sample_id: int, motivo: str) -> None:
        destinatarios = self.studies.notification_recipients(study_id)
        if not destinatarios:
            logger.warning("El estudio %s no tiene mail del paciente: no se avisa el remuestreo.", study_id)
            return
        code = study_code(study_id)
        datos = NotificacionInput(
            asunto=f"Hay que repetir la extracción del estudio {code}",
            mensaje=(f"La muestra del estudio {code} no se pudo usar. Motivo: {motivo}\n\n"
                     "Hay que sacar un turno nuevo para repetir la extracción desde Exoma Care, en el "
                     "seguimiento del estudio. No hace falta volver a pagar."),
            destinatarios=[destinatario["destino"] for destinatario in destinatarios],
            idempotency_key=f"remuestreo-{study_id}-{sample_id}",
            referencia=str(study_id),
        )
        # Lo llama un endpoint sync desde el threadpool, sin event loop: asyncio.run deja el envío y el
        # log de avisos en el mismo hilo que la sesión, sin bloquear el loop de la app.
        asyncio.run(self.crear_avisos().execute(datos))
