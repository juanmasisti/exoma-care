from datetime import date, timedelta
from typing import Any, Protocol
from uuid import uuid4

from app.domain.entities.roles import UserRole
from app.domain.entities.study import BIOINFORMATICS_STATUSES
from app.domain.interfaces.study_repository import StudyRepository

RESULT_AVAILABLE_STATUS = "resultado_disponible"
RESULT_NOTIFICATION_MESSAGE = (
    "Hay un resultado de estudio disponible en EXOMA CARE. "
    "Inicia sesion para consultarlo de forma segura."
)


class ApigenBioinformaticsGateway(Protocol):
    async def buscar_variantes(
        self, gen: str, hgvs_c: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def resultado_diagnostico(
        self, patologia: str, variantes: list[str]
    ) -> Any: ...

    async def hallazgos_secundarios(
        self, variantes: list[str], excluir_patologias: list[str]
    ) -> Any: ...


class CDSSCatalogGateway(Protocol):
    async def obtener_patologias(self) -> list[dict[str, str]]: ...


class ResultNotificationGateway(Protocol):
    async def enviar_aviso_resultado(
        self,
        *,
        study_id: int,
        asunto: str,
        mensaje: str,
        destinatarios: list[dict[str, str]],
        idempotency_key: str | None = None,
    ) -> int: ...


class BioinformaticsStudyNotFoundError(LookupError):
    pass


class BioinformaticsResultNotAvailableError(LookupError):
    pass


class BioinformaticsStudyConflictError(RuntimeError):
    pass


class NotificationRecipientsUnavailableError(RuntimeError):
    pass


class ApigenResponseError(RuntimeError):
    pass


class ObtenerCatalogoPatologiasUseCase:
    def __init__(self, cdss_client: CDSSCatalogGateway):
        self._cdss = cdss_client

    async def execute(self) -> list[dict[str, str]]:
        return await self._cdss.obtener_patologias()


class ListarEstudiosBioinformaticaUseCase:
    def __init__(self, study_repository: StudyRepository):
        self._studies = study_repository

    def execute(self) -> list[dict[str, Any]]:
        return self._studies.list_bioinformatics_studies()


class ListarHistorialEstudiosUseCase:
    def __init__(self, study_repository: StudyRepository):
        self._studies = study_repository

    def execute(self, query: str = "") -> list[dict[str, Any]]:
        return self._studies.list_study_history(query)


class ObtenerResultadoEstudioUseCase:
    def __init__(self, study_repository: StudyRepository):
        self._studies = study_repository

    def execute(
        self, study_id: int, actor_id: int, actor_role: UserRole
    ) -> dict[str, Any]:
        study = self._studies.bioinformatics_study(study_id)
        if study is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        if study["status"] != RESULT_AVAILABLE_STATUS:
            raise BioinformaticsResultNotAvailableError(
                "El resultado del estudio todavía no está disponible."
            )
        if (
            actor_role == UserRole.TREATING_PHYSICIAN
            and not self._studies.physician_owns_study(study_id, actor_id)
        ):
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        if (
            actor_role == UserRole.BIOINFORMATICIAN
            and self._studies.analysis_owner(study_id) != actor_id
        ):
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        return study


class ReenviarAvisoResultadoUseCase:
    def __init__(
        self,
        study_repository: StudyRepository,
        notification_service: ResultNotificationGateway,
    ):
        self._studies = study_repository
        self._notifications = notification_service

    async def execute(self, study_id: int) -> int:
        status = self._studies.status(study_id)
        if status is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        if status != RESULT_AVAILABLE_STATUS:
            raise BioinformaticsStudyConflictError(
                "Solo se puede reenviar el aviso de un estudio con resultado disponible."
            )

        recipients = self._studies.notification_recipients(study_id)
        if len(recipients) < 2:
            raise NotificationRecipientsUnavailableError(
                "El estudio necesita un correo válido del paciente y del médico tratante."
            )

        return await self._notifications.enviar_aviso_resultado(
            study_id=study_id,
            asunto="Resultado de estudio disponible",
            mensaje=RESULT_NOTIFICATION_MESSAGE,
            destinatarios=recipients,
            idempotency_key=f"resultado-{study_id}-reenvio-{uuid4()}",
        )


class IniciarAnalisisEstudioUseCase:
    def __init__(self, study_repository: StudyRepository):
        self._studies = study_repository

    def execute(self, study_id: int, analyst_id: int) -> dict[str, Any]:
        current_status = self._studies.status(study_id)
        if current_status is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        if current_status != "en_area_bioinformatica":
            raise BioinformaticsStudyConflictError(
                f"El estudio no está disponible para iniciar (estado: {current_status})."
            )
        if not self._studies.start_analysis(study_id, analyst_id):
            raise BioinformaticsStudyConflictError(
                "Otro bioinformático inició el análisis o cambió el estado del estudio."
            )
        study = self._studies.bioinformatics_study(study_id)
        if study is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        return study


class BuscarVariantesApigenUseCase:
    def __init__(self, apigen_client: ApigenBioinformaticsGateway):
        self._apigen = apigen_client

    async def execute(
        self,
        gen: str,
        hgvs_c: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        items, total = await self._apigen.buscar_variantes(
            gen=gen, hgvs_c=hgvs_c, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}


class FinalizarAnalisisBioinformaticoUseCase:
    def __init__(
        self,
        study_repository: StudyRepository,
        apigen_client: ApigenBioinformaticsGateway,
        notification_service: ResultNotificationGateway,
    ):
        self._studies = study_repository
        self._apigen = apigen_client
        self._notifications = notification_service

    async def execute(
        self,
        study_id: int,
        analyst_id: int,
        codigo_patologia: str,
        variantes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current_status = self._studies.status(study_id)
        if current_status is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        if current_status == RESULT_AVAILABLE_STATUS:
            if self._studies.analysis_owner(study_id) != analyst_id:
                raise BioinformaticsStudyConflictError(
                    "El resultado ya fue publicado o pertenece a otro bioinformático."
                )
            study = self._studies.bioinformatics_study(study_id)
            if study is None:
                raise BioinformaticsStudyNotFoundError("El estudio no existe.")
            await self._notify_result(study_id)
            return study
        if current_status not in BIOINFORMATICS_STATUSES:
            raise BioinformaticsStudyConflictError(
                f"El estudio no se puede finalizar desde el estado {current_status}."
            )

        variants_hgvs = [_variant_hgvs(variant) for variant in variantes]
        if current_status == "en_area_bioinformatica":
            if not self._studies.start_analysis(study_id, analyst_id):
                raise BioinformaticsStudyConflictError(
                    "Otro bioinformático tomó el estudio o su estado cambió."
                )
        elif not self._studies.claim_unassigned_analysis(study_id, analyst_id):
            assigned_analyst = self._studies.analysis_owner(study_id)
            if assigned_analyst != analyst_id:
                raise BioinformaticsStudyConflictError(
                    "El estudio está asignado a otro bioinformático."
                )

        diagnosis = await self._apigen.resultado_diagnostico(
            codigo_patologia, variants_hgvs
        )
        if not isinstance(diagnosis, str) or diagnosis not in {
            "positivo",
            "portador",
            "negativo",
        }:
            raise ApigenResponseError(
                "Apigen devolvió un resultado diagnóstico no reconocido."
            )
        findings = await self._apigen.hallazgos_secundarios(
            variants_hgvs, [codigo_patologia]
        )
        if not isinstance(findings, list):
            raise ApigenResponseError(
                "Apigen devolvió una lista de hallazgos secundarios inválida."
            )

        has_pathogenic_variant = any(
            variant["clasificacion"].casefold() == "patogenica"
            for variant in variantes
        )
        if diagnosis == "positivo" and not has_pathogenic_variant:
            diagnosis = "negativo"

        reassessment_date = None
        if diagnosis != "positivo" and any(
            variant["clasificacion"].casefold()
            in {"probablemente_patogenica", "vus"}
            for variant in variantes
        ):
            reassessment_date = date.today() + timedelta(days=365)

        if not self._studies.save_bioinformatics_result(
            study_id=study_id,
            analyst_id=analyst_id,
            variantes_detectadas=variantes,
            resultado_diagnostico=diagnosis,
            hallazgos_secundarios=findings,
            fecha_reevaluacion=reassessment_date,
            codigo_patologia=codigo_patologia,
        ):
            raise BioinformaticsStudyConflictError(
                "No se pudo guardar el resultado porque cambió la asignación del estudio."
            )
        study = self._studies.bioinformatics_study(study_id)
        if study is None:
            raise BioinformaticsStudyNotFoundError("El estudio no existe.")
        await self._notify_result(study_id)
        return study

    async def _notify_result(self, study_id: int) -> None:
        recipients = self._studies.notification_recipients(study_id)
        if len(recipients) < 2:
            raise NotificationRecipientsUnavailableError(
                "El estudio necesita un correo válido del paciente y del médico tratante."
            )
        await self._notifications.enviar_aviso_resultado(
            study_id=study_id,
            asunto="Resultado de estudio disponible",
            mensaje=RESULT_NOTIFICATION_MESSAGE,
            destinatarios=recipients,
        )


def _variant_hgvs(variant: dict[str, Any]) -> str:
    gene = str(variant["gen"]).strip()
    hgvs_c = str(variant["hgvs_c"]).strip()
    if not gene or not hgvs_c.startswith("c."):
        raise ValueError("Cada variante debe incluir gen y HGVS en formato c.")
    return f"{gene}:{hgvs_c}"
