from typing import Protocol

from app.domain.entities.study_request import StudyRequest


class StudyNotifier(Protocol):
    """Avisos por mail del circuito de estudios (EC-13/EC-14). Los usa el caso de uso después de
    confirmar la operación: un aviso que falla nunca deshace un pago ni una solicitud."""

    async def reanalisis_solicitado(self, study: StudyRequest) -> None:
        """Al paciente y a administración: hay un reanálisis para presupuestar."""
        ...

    async def estudio_habilitado(self, study: StudyRequest) -> None:
        """Pago acreditado (o cobertura total): al paciente y al médico."""
        ...
