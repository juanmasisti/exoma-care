from datetime import UTC, datetime
from typing import Any, Protocol

from app.domain.interfaces.study_repository import StudyRepository

AVAILABLE_STATUS = "en_area_bioinformatica"
RESULT_STATUS = "resultado_disponible"


class ApigenGateway(Protocol):
    async def consultar_diagnostico(
        self, patologia: str, variantes: list[dict[str, Any]]
    ) -> Any: ...

    async def consultar_hallazgos(
        self, variantes: list[dict[str, Any]], excluir_patologias: list[str]
    ) -> Any: ...


class NotificationGateway(Protocol):
    async def enviar_aviso_resultado(
        self,
        study_id: int,
        asunto: str,
        mensaje: str,
        destinatarios: list[dict[str, str]],
    ) -> int: ...


class StudyNotFoundError(LookupError):
    pass


class StudyStateConflictError(RuntimeError):
    pass


class MissingPatientEmailError(ValueError):
    pass


class ProcesarAnalisisUseCase:
    def __init__(
        self,
        study_repository: StudyRepository,
        apigen_client: ApigenGateway,
        notification_client: NotificationGateway,
    ):
        self._studies = study_repository
        self._apigen = apigen_client
        self._notifications = notification_client

    async def execute(
        self,
        study_id: int,
        analyst_id: int,
        codigo_patologia: str,
        variantes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current_status = self._studies.status(study_id)
        if current_status is None:
            raise StudyNotFoundError("El estudio no existe.")

        recipients = self._studies.notification_recipients(study_id)
        if not recipients:
            raise MissingPatientEmailError(
                "El paciente no tiene un correo válido para recibir el aviso."
            )

        if current_status == RESULT_STATUS:
            result = self._studies.result_for_analyst(study_id, analyst_id)
            if result is None:
                raise StudyStateConflictError(
                    "El resultado ya fue publicado o pertenece a otro bioinformático."
                )
            await self._notify(study_id, recipients)
            return result

        if current_status != AVAILABLE_STATUS:
            raise StudyStateConflictError(
                f"El estudio no está disponible para análisis (estado: {current_status})."
            )
        if not self._studies.claim_analysis(study_id, analyst_id):
            raise StudyStateConflictError(
                "Otro bioinformático tomó el estudio o su estado cambió."
            )

        try:
            diagnosis = await self._apigen.consultar_diagnostico(
                codigo_patologia, variantes
            )
            findings = await self._apigen.consultar_hallazgos(
                variantes, [codigo_patologia]
            )
            result = {
                "study_id": study_id,
                "codigo_patologia": codigo_patologia,
                "variantes": variantes,
                "diagnostico": diagnosis,
                "hallazgos_secundarios": findings,
                "published_at": datetime.now(UTC).isoformat(),
            }
            if not self._studies.complete_analysis(study_id, analyst_id, result):
                raise StudyStateConflictError(
                    "No se pudo publicar el resultado porque cambió la asignación del estudio."
                )
        except Exception as exc:
            if not self._studies.release_analysis(study_id, analyst_id):
                raise RuntimeError(
                    "Falló el análisis y no se pudo liberar el estudio para reintento."
                ) from exc
            raise

        await self._notify(study_id, recipients)
        return result

    async def _notify(
        self, study_id: int, recipients: list[dict[str, str]]
    ) -> None:
        await self._notifications.enviar_aviso_resultado(
            study_id=study_id,
            asunto="Resultado de exoma disponible",
            mensaje="Tu resultado está listo para ser consultado en la web",
            destinatarios=recipients,
        )
