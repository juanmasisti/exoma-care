"""Regla de precio del presupuesto de un estudio (EC-11); sin dependencias externas."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CURRENCY = "USD"
BASE_PRICE = 500
INCLUDED_GENES = 5
EXTRA_GENE_PRICE = 30


def normalize_gene(symbol: str) -> str:
    """Los símbolos de gen se comparan en mayúsculas y sin espacios."""
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("El símbolo del gen no puede estar vacío.")
    return normalized


def combine_genes(*groups: Iterable[str]) -> tuple[str, ...]:
    """Une grupos de genes sin repetir ninguno, conservando el orden de aparición.

    Un gen compartido por dos patologías, o pedido además como adicional, se
    cuenta una sola vez. No infiere relaciones médicas: solo unifica símbolos.
    """
    seen: dict[str, None] = {}
    for group in groups:
        for symbol in group:
            seen.setdefault(normalize_gene(symbol), None)
    return tuple(seen)


# Reanálisis (EC-14): mismo cálculo que un estudio nuevo con un 30 % de descuento.
REANALYSIS_DISCOUNT_PERCENT = 30


@dataclass(frozen=True, slots=True)
class Budget:
    gene_count: int
    base_amount: int
    extra_genes: int
    extra_amount: int
    total: int
    currency: str = CURRENCY


def calculate_budget(genes: Iterable[str]) -> Budget:
    """USD 500 hasta 5 genes; desde el sexto, USD 30 por cada gen adicional."""
    unique = combine_genes(genes)
    if not unique:
        raise ValueError("El estudio necesita al menos un gen para presupuestarse.")
    extra_genes = max(0, len(unique) - INCLUDED_GENES)
    extra_amount = extra_genes * EXTRA_GENE_PRICE
    return Budget(
        gene_count=len(unique),
        base_amount=BASE_PRICE,
        extra_genes=extra_genes,
        extra_amount=extra_amount,
        total=BASE_PRICE + extra_amount,
    )


# --- Reparto del importe (EC-13): obra social, cupón y lo que paga el paciente ---
# Los importes se manejan en centavos enteros para no acumular errores de redondeo.
CENTS_PER_UNIT = 100


def to_cents(amount: int) -> int:
    """Pasa un importe entero en USD a centavos."""
    return amount * CENTS_PER_UNIT


def normalize_percent(value: int | float | str | Decimal) -> Decimal:
    """Valida un porcentaje entre 0 y 100 (ambos incluidos)."""
    if isinstance(value, bool):
        raise ValueError("El porcentaje no es válido.")
    try:
        percent = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("El porcentaje no es válido.") from exc
    if not percent.is_finite() or not Decimal(0) <= percent <= Decimal(100):
        raise ValueError("El porcentaje debe estar entre 0 y 100.")
    return percent


def _percent_of(cents: int, percent: Decimal) -> int:
    return int(
        (Decimal(cents) * percent / Decimal(100)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def reanalysis_discount_cents(gross_cents: int) -> int:
    """Descuento del reanálisis sobre el precio de lista (base + genes adicionales)."""
    return _percent_of(gross_cents, Decimal(REANALYSIS_DISCOUNT_PERCENT))


@dataclass(frozen=True, slots=True)
class PaymentSplit:
    total_cents: int
    insurer_cents: int  # lo que cubre la obra social
    patient_gross_cents: int  # lo que queda a cargo del paciente antes del cupón
    discount_cents: int  # descuento del cupón, aplicado sobre lo del paciente
    patient_cents: int  # lo que efectivamente paga el paciente


def split_amounts(
    total_cents: int,
    coverage_percent: int | float | str | Decimal = 0,
    coupon_percent: int | float | str | Decimal = 0,
) -> PaymentSplit:
    """Primero la cobertura de la obra social; el cupón se aplica solo a lo del paciente.

    Siempre se cumple: insurer + discount + patient == total.
    """
    if total_cents < 0:
        raise ValueError("El importe total no puede ser negativo.")
    insurer = _percent_of(total_cents, normalize_percent(coverage_percent))
    patient_gross = total_cents - insurer
    discount = _percent_of(patient_gross, normalize_percent(coupon_percent))
    return PaymentSplit(
        total_cents=total_cents,
        insurer_cents=insurer,
        patient_gross_cents=patient_gross,
        discount_cents=discount,
        patient_cents=patient_gross - discount,
    )
