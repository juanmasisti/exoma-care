from typing import Protocol


class ResampleNotifier(Protocol):
    """Avisa a paciente y médico que el estudio requiere remuestreo. Quién es cada uno lo resuelve avisos (Camila)."""

    def avisar_remuestreo(self, study_id: int, motivo: str) -> None: ...
