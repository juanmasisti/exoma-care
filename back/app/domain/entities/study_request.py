"""Solicitud de estudio, presupuesto, cobertura y cupones (EC-10 a EC-13); dominio puro."""

from dataclasses import dataclass
from datetime import datetime

PAYMENT_MODES = ("particular", "obra_social")
GENE_ORIGINS = ("catalogo", "manual")
# Estados de la solicitud de cobertura (los define la API de obras sociales).
COVERAGE_STATUSES = ("pendiente", "autorizada", "rechazada", "demanda_en_curso")
COUPON_STATUSES = ("disponible", "medico", "paciente", "canjeando", "usado")
OPERATION_TYPES = ("cobro_paciente", "cobertura_obra_social")

# La modalidad de pago se elige una vez; solo se reabre si la obra social rechazó.
MODE_CHANGE_ALLOWED_STATUSES = frozenset({"creado", "rechazado"})

STUDY_ID_REFERENCE_PREFIX = "estudio-"


def status_after_mode_choice(mode: str) -> str:
    if mode == "particular":
        return "pendiente_pago"
    if mode == "obra_social":
        return "pendiente_autorizacion"
    raise ValueError(f"Modalidad de pago inválida: {mode}.")


def status_after_authorization(patient_gross_cents: int) -> str:
    """Con cobertura total no queda nada por pagar; si no, el paciente paga el resto."""
    return "autorizado" if patient_gross_cents == 0 else "pendiente_pago"


def status_after_patient_payment(mode: str) -> str:
    """Pago particular: pagado. Resto de una cobertura parcial: ya estaba autorizado."""
    if mode == "particular":
        return "pagado"
    if mode == "obra_social":
        return "autorizado"
    raise ValueError(f"Modalidad de pago inválida: {mode}.")


@dataclass(frozen=True, slots=True)
class PathologyRef:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class GeneRef:
    symbol: str
    origin: str  # "catalogo": viene de la patología; "manual": lo agregó el médico


@dataclass(frozen=True, slots=True)
class StudyRequest:
    id: int
    patient_id: int
    physician_id: int | None
    status: str
    include_secondary_findings: bool
    created_at: datetime
    pathologies: tuple[PathologyRef, ...]
    genes: tuple[GeneRef, ...]


@dataclass(frozen=True, slots=True)
class StudyBudget:
    id: int
    study_id: int
    gene_count: int
    base_cents: int
    extra_genes: int
    extra_cents: int
    total_cents: int
    currency: str
    issued_by_user_id: int
    issued_at: datetime
    payment_mode: str | None = None
    insurer_external_id: str | None = None
    insurer_name: str | None = None
    # Estimado hasta que la obra social autoriza; después es el porcentaje definitivo.
    coverage_percent: float | None = None
    insurer_cents: int | None = None
    patient_cents: int | None = None  # a cargo del paciente antes del cupón


@dataclass(frozen=True, slots=True)
class CoverageRequest:
    id: int
    budget_id: int
    study_id: int
    external_id: str
    insurer_external_id: str
    status: str
    authorize_url: str
    reject_url: str
    demands_count: int
    created_at: datetime
    rejection_reason: str | None = None
    resolved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Coupon:
    code: str
    percentage: float
    status: str
    generated_at: datetime
    medico_id: int | None = None
    patient_id: int | None = None
