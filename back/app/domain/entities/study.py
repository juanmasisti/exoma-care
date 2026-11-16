"""Study states and bioinformatics result data."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


STUDY_STATUSES = (
    "creado",
    "pendiente_pago",
    "pendiente_autorizacion",
    "pagado",
    "autorizado",
    "rechazado",
    "turno_sacado",
    "listo_para_retirar",
    "requiere_remuestreo",
    "en_viaje_a_corea",
    "en_area_bioinformatica",
    "en_analisis",
    "resultado_disponible",
)

# Estados que permiten sacar turno de extracción. requiere_remuestreo: turno nuevo para el
# mismo estudio, sin volver a pagar (EC-16, decisión 011).
ENABLED_STUDY_STATUSES = frozenset({"pagado", "autorizado", "requiere_remuestreo"})

BIOINFORMATICS_STATUSES = frozenset(
    {"en_area_bioinformatica", "en_analisis"}
)


@dataclass(frozen=True, slots=True)
class Study:
    id: int
    patient_id: int
    status: str
    analyst_id: int | None
    variantes_detectadas: list[dict[str, Any]] | None
    resultado_diagnostico: str | None
    hallazgos_secundarios: list[dict[str, Any]] | None
    fecha_reevaluacion: date | None
    created_at: datetime
