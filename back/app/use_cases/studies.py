"""PROVISORIO: contrato mínimo de estudios que usa logística; lo amplía el área de estudios (Tomás)."""
from app.domain.entities.study import ENABLED_STUDY_STATUSES, StudyStatus
from app.domain.interfaces.study_repository import StudyRepository


class StudyService:
    def __init__(self, studies: StudyRepository):
        self._studies = studies

    def estudio_habilitado(self, study_id: int) -> bool:
        status = self._studies.status(study_id)
        if status is None:
            raise LookupError("El estudio no existe.")
        return status in ENABLED_STUDY_STATUSES

    def cambiar_estado_estudio(
        self, study_id: int, nuevo_estado: StudyStatus | str
    ) -> None:
        """No confirma la transacción: el commit lo hace quien llama."""
        try:
            status = StudyStatus(nuevo_estado)
        except (TypeError, ValueError):
            raise ValueError(f"Estado de estudio inválido: {nuevo_estado}.")
        if not self._studies.set_status(study_id, status):
            raise LookupError("El estudio no existe.")
