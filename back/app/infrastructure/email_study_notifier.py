"""Avisos por mail de solicitudes y pagos (EC-13/EC-14) con el servicio común de avisos."""

import logging
from collections.abc import Callable
from typing import Protocol

from app.domain.dtos.notification_dto import NotificacionInput, NotificacionResultado
from app.domain.entities.logistics import study_code
from app.domain.entities.roles import UserRole
from app.domain.entities.study import StudyStatus
from app.domain.entities.study_request import StudyRequest
from app.domain.interfaces.study_request_repository import StudyRequestRepository

logger = logging.getLogger(__name__)

APP_NAME = "Exoma Care"


class Avisos(Protocol):
    """Lo que se usa de EnviarNotificacionUseCase, sin importar casos de uso desde infraestructura."""

    async def execute(self, datos: NotificacionInput) -> NotificacionResultado: ...


class EmailStudyNotifier:
    """Arma y manda los mails. Cada destinatario con su texto y su Idempotency-Key, así un
    reintento no duplica el aviso. Si falla un envío se registra y se sigue con el resto."""

    def __init__(
        self, repo: StudyRequestRepository, crear_avisos: Callable[[], Avisos]
    ):
        self._repo = repo
        # Se arma al avisar: sin clave de avisos configurada, el pago funciona igual.
        self._crear_avisos = crear_avisos

    async def reanalisis_solicitado(self, study: StudyRequest) -> None:
        code = study_code(study.id)
        origin = study_code(study.original_study_id) if study.original_study_id else "-"
        await self._send(
            [self._repo.patient_email(study.patient_id)],
            asunto=f"Se pidió un reanálisis de tu estudio {origin}",
            mensaje=(
                f"Tu médico pidió un reanálisis del exoma del estudio {origin}. "
                f"El reanálisis quedó registrado como {code}.\n\n"
                "No hace falta una nueva extracción de sangre. Cuando administración emita el "
                f"presupuesto lo vas a ver en {APP_NAME}, en Mis estudios."
            ),
            key=f"reanalisis-{study.id}-solicitado-paciente",
            study_id=study.id,
        )
        await self._send(
            self._repo.emails_for_role(UserRole.LAB_ADMINISTRATOR),
            asunto=f"Reanálisis para presupuestar: {code}",
            mensaje=(
                f"Se pidió el reanálisis {code} sobre el estudio {origin} "
                f"({self._patient(study)}).\n\n"
                f"Emití el presupuesto desde {APP_NAME}, en Solicitudes de estudio. "
                "El reanálisis tiene un 30 % de descuento y no lleva turno de extracción."
            ),
            key=f"reanalisis-{study.id}-solicitado-administracion",
            study_id=study.id,
        )

    async def estudio_habilitado(self, study: StudyRequest) -> None:
        code = study_code(study.id)
        covered = study.status == StudyStatus.AUTHORIZED
        acreditado = (
            "La obra social autorizó la cobertura total" if covered else "Se acreditó el pago"
        )
        if study.is_reanalysis:
            next_step = (
                "Al ser un reanálisis no hace falta una nueva extracción: el estudio pasa "
                "directo al análisis bioinformático."
            )
        else:
            next_step = f"Ya podés reservar el turno de extracción desde {APP_NAME}."
        await self._send(
            [self._repo.patient_email(study.patient_id)],
            asunto=f"{acreditado} del estudio {code}",
            mensaje=f"{acreditado} del estudio {code}.\n\n{next_step}",
            key=f"estudio-{study.id}-habilitado-paciente",
            study_id=study.id,
        )
        if study.physician_id is not None:
            await self._send(
                [self._repo.user_email(study.physician_id)],
                asunto=f"{acreditado} del estudio {code}",
                mensaje=(
                    f"{acreditado} del estudio {code} de {self._patient(study)}."
                    + (" Pasa directo a bioinformática." if study.is_reanalysis else "")
                ),
                key=f"estudio-{study.id}-habilitado-medico",
                study_id=study.id,
            )

    def _patient(self, study: StudyRequest) -> str:
        return self._repo.patient_full_name(study.patient_id) or f"paciente {study.patient_id}"

    async def _send(
        self,
        recipients: list[str | None],
        *,
        asunto: str,
        mensaje: str,
        key: str,
        study_id: int,
    ) -> None:
        # La API de avisos acepta hasta 50 destinatarios por aviso.
        destinatarios = list(dict.fromkeys(email for email in recipients if email))[:50]
        if not destinatarios:
            logger.warning("Aviso %s sin destinatarios con mail: no se envía.", key)
            return
        try:
            await self._crear_avisos().execute(
                NotificacionInput(
                    asunto=asunto,
                    mensaje=mensaje,
                    destinatarios=destinatarios,
                    idempotency_key=key,
                    referencia=str(study_id),
                )
            )
        except Exception:  # noqa: BLE001 - un aviso nunca debe romper la operación
            logger.exception("No se pudo enviar el aviso %s.", key)
