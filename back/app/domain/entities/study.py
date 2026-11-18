"""Study states and bioinformatics result data."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class StudyStatus(str, Enum):
    CREATED = "creado"
    PENDING_PAYMENT = "pendiente_pago"
    PENDING_AUTHORIZATION = "pendiente_autorizacion"
    PAID = "pagado"
    AUTHORIZED = "autorizado"
    REJECTED = "rechazado"
    APPOINTMENT_BOOKED = "turno_sacado"
    READY_FOR_PICKUP = "listo_para_retirar"
    RESAMPLE_REQUIRED = "requiere_remuestreo"
    IN_TRANSIT_TO_KOREA = "en_viaje_a_corea"
    IN_BIOINFORMATICS = "en_area_bioinformatica"
    UNDER_ANALYSIS = "en_analisis"
    RESULT_AVAILABLE = "resultado_disponible"


STUDY_STATUSES = tuple(status.value for status in StudyStatus)

# Estados que permiten sacar turno de extracción. requiere_remuestreo: turno nuevo para el
# mismo estudio, sin volver a pagar (EC-16, decisión 011).
ENABLED_STUDY_STATUSES = frozenset(
    {
        StudyStatus.PAID,
        StudyStatus.AUTHORIZED,
        StudyStatus.RESAMPLE_REQUIRED,
    }
)

BIOINFORMATICS_STATUSES = frozenset(
    {StudyStatus.IN_BIOINFORMATICS, StudyStatus.UNDER_ANALYSIS}
)


@dataclass(frozen=True, slots=True)
class Study:
    id: int
    patient_id: int
    status: StudyStatus
    analyst_id: int | None
    variantes_detectadas: list[dict[str, Any]] | None
    resultado_diagnostico: str | None
    hallazgos_secundarios: list[dict[str, Any]] | None
    fecha_reevaluacion: date | None
    created_at: datetime
