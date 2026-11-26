"""Reglas puras de logística: días hábiles, feriados, horarios y estados de turnos, muestras, recorridos y lotes."""
import calendar
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")
OPENING = time(9)
CLOSING = time(18)
SLOT_MINUTES = 15


def is_business_day(day: date, holidays) -> bool:
    return day.weekday() < 5 and day not in holidays


def _easter(year: int) -> date:
    # Algoritmo gregoriano de Meeus/Jones/Butcher.
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def fixed_national_holidays(year: int) -> dict[date, str]:
    """Feriados inamovibles (Ley 27.399), incluidos los que dependen de Pascua.

    No calcula los trasladables (17/6, 17/8, 12/10 y 20/11) ni los puentes turísticos:
    dependen de un decreto anual y se cargan aparte. Tampoco el Jueves Santo, que es
    día no laborable y no feriado.
    """
    easter = _easter(year)
    return {
        date(year, 1, 1): "Año Nuevo",
        easter - timedelta(days=48): "Carnaval",
        easter - timedelta(days=47): "Carnaval",
        date(year, 3, 24): "Día Nacional de la Memoria por la Verdad y la Justicia",
        date(year, 4, 2): "Día del Veterano y de los Caídos en la Guerra de Malvinas",
        easter - timedelta(days=2): "Viernes Santo",
        date(year, 5, 1): "Día del Trabajador",
        date(year, 5, 25): "Día de la Revolución de Mayo",
        date(year, 6, 20): "Paso a la Inmortalidad del General Manuel Belgrano",
        date(year, 7, 9): "Día de la Independencia",
        date(year, 12, 8): "Inmaculada Concepción de María",
        date(year, 12, 25): "Navidad",
    }


def daily_slots(day: date, holidays) -> list[datetime]:
    if not is_business_day(day, holidays):
        return []
    slot = datetime.combine(day, OPENING, tzinfo=TIMEZONE)
    closing = datetime.combine(day, CLOSING, tzinfo=TIMEZONE)
    slots = []
    while slot < closing:
        slots.append(slot)
        slot += timedelta(minutes=SLOT_MINUTES)
    return slots


def available_slots(day: date, holidays, now: datetime, booked=()) -> list[datetime]:
    if now.tzinfo is None:
        raise ValueError("La hora actual debe indicar la zona horaria.")
    booked = set(booked)
    # Un turno que empieza justo ahora ya no se puede reservar.
    return [slot for slot in daily_slots(day, holidays) if slot > now and slot not in booked]


def is_valid_slot(starts_at: datetime, holidays) -> bool:
    """Día hábil, entre 9 y 17:45 y en punto de un turno de 15 minutos. No mira si es pasado."""
    if starts_at.tzinfo is None:
        raise ValueError("La fecha y hora del turno debe indicar la zona horaria.")
    local = starts_at.astimezone(TIMEZONE)
    return local in daily_slots(local.date(), holidays)


def study_code(study_id: int) -> str:
    """PROVISORIO (decisión abierta 4 del dominio): código del estudio impreso para el paciente."""
    return f"EST-{study_id:06d}"


def study_id_from_code(code: str) -> int | None:
    """Inversa de `study_code`; None si el código no tiene esa forma."""
    # [0-9] y no \d: el código llega de afuera y \d acepta dígitos de cualquier alfabeto.
    match = re.fullmatch(r"EST-([0-9]{6,})", code)
    if match is None:
        return None
    study_id = int(match.group(1))
    # Regenerarlo descarta ceros de más (EST-0000001) y EST-000000.
    return study_id if study_id > 0 and study_code(study_id) == code else None


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    ABSENT = "absent"


# Solo un turno reservado cambia; cancelado, asistido y ausente son finales.
APPOINTMENT_TRANSITIONS = {
    AppointmentStatus.BOOKED: {AppointmentStatus.CANCELLED, AppointmentStatus.ATTENDED, AppointmentStatus.ABSENT},
}


def can_change_appointment(current: AppointmentStatus, new: AppointmentStatus) -> bool:
    return new in APPOINTMENT_TRANSITIONS.get(current, set())


class SampleStatus(str, Enum):
    READY_FOR_PICKUP = "ready_for_pickup"
    WITH_TRANSPORTER = "with_transporter"
    RECEIVED = "received"
    IN_SAMPLE_SET = "in_sample_set"
    IN_TRANSIT_TO_SEQUENCING_LAB = "in_transit_to_sequencing_lab"
    DISCARDED = "discarded"


# En orden; se descarta para remuestrear desde lista para retirar, recibida o en viaje al laboratorio
# de secuenciación. Cuando se defina el estado de la vuelta del resultado, se suma al enum y acá.
SAMPLE_TRANSITIONS = {
    SampleStatus.READY_FOR_PICKUP: {SampleStatus.WITH_TRANSPORTER, SampleStatus.DISCARDED},
    SampleStatus.WITH_TRANSPORTER: {SampleStatus.RECEIVED},
    SampleStatus.RECEIVED: {SampleStatus.IN_SAMPLE_SET, SampleStatus.DISCARDED},
    SampleStatus.IN_SAMPLE_SET: {SampleStatus.IN_TRANSIT_TO_SEQUENCING_LAB},
    SampleStatus.IN_TRANSIT_TO_SEQUENCING_LAB: {SampleStatus.DISCARDED},
}


def can_change_sample(current: SampleStatus, new: SampleStatus) -> bool:
    return new in SAMPLE_TRANSITIONS.get(current, set())


MIN_SAMPLE_VOLUME_ML = Decimal("2")


def sample_is_usable(volume_ml: Decimal) -> bool:
    """Menos de 2 ml obliga a remuestrear."""
    return volume_ml >= MIN_SAMPLE_VOLUME_ML


def initial_sample_status(volume_ml: Decimal) -> SampleStatus:
    """Estado con el que nace la muestra al llegar el aviso de extracción.

    Crearla no es una transición: con menos de 2 ml nace descartada, sin pasar por
    ready_for_pickup. SAMPLE_TRANSITIONS solo rige los cambios de una muestra que ya existe.
    """
    return SampleStatus.READY_FOR_PICKUP if sample_is_usable(volume_ml) else SampleStatus.DISCARDED


class DailyRouteStatus(str, Enum):
    PENDING = "pending"
    ARRIVED = "arrived"


# La llegada al laboratorio central cierra la orden del día. Cada retiro queda en su parada.
ROUTE_TRANSITIONS = {DailyRouteStatus.PENDING: {DailyRouteStatus.ARRIVED}}


def can_change_route(current: DailyRouteStatus, new: DailyRouteStatus) -> bool:
    return new in ROUTE_TRANSITIONS.get(current, set())


def next_stop_sequence(picked_sequences, total: int) -> int | None:
    """La primera parada sin retirar: el orden es fijo y no se saltea. None si ya se retiraron todas."""
    picked = set(picked_sequences)
    return next((sequence for sequence in range(1, total + 1) if sequence not in picked), None)


class SampleSetStatus(str, Enum):
    ASSEMBLING = "assembling"
    CLOSED = "closed"
    AWAITING_PICKUP = "awaiting_pickup"
    IN_TRANSIT_TO_SEQUENCING_LAB = "in_transit_to_sequencing_lab"


# En orden y sin vuelta atrás: un lote cerrado no cambia de muestras.
SAMPLE_SET_TRANSITIONS = {
    SampleSetStatus.ASSEMBLING: {SampleSetStatus.CLOSED},
    SampleSetStatus.CLOSED: {SampleSetStatus.AWAITING_PICKUP},
    SampleSetStatus.AWAITING_PICKUP: {SampleSetStatus.IN_TRANSIT_TO_SEQUENCING_LAB},
}


def can_change_sample_set(current: SampleSetStatus, new: SampleSetStatus) -> bool:
    return new in SAMPLE_SET_TRANSITIONS.get(current, set())


SAMPLE_SET_SIZE = 10


def sample_set_must_close(count: int, has_urgent_pompe: bool) -> bool:
    """Se cierra con 10 o con un Pompe urgente.

    Con un Pompe urgente sale aunque tenga una sola muestra: propuesta pendiente de confirmar
    con el profesor (decisión abierta 6 del dominio).
    """
    return count >= SAMPLE_SET_SIZE or has_urgent_pompe


# Código de la patología en el catálogo (Apigen), no su nombre. El catálogo DEMO usa minúsculas.
POMPE_PATHOLOGY_CODE = "POMPE"
URGENT_POMPE_MAX_MONTHS = 4


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def is_urgent_pompe(pathology_codes, birth_date: date, reference_date: date) -> bool:
    """Pompe en menor de 4 meses. La fecha de referencia la elige quien llama (decisión abierta 5)."""
    is_pompe = any(code.upper() == POMPE_PATHOLOGY_CODE for code in pathology_codes)
    return is_pompe and reference_date < _add_months(birth_date, URGENT_POMPE_MAX_MONTHS)


def is_valid_pickup_time(at: datetime, holidays) -> bool:
    """Retiro de FedEx: día hábil, desde las 9 y antes de las 18 (como los turnos). No mira si es pasado."""
    if at.tzinfo is None:
        raise ValueError("La fecha y hora del retiro debe indicar la zona horaria.")
    local = at.astimezone(TIMEZONE)
    return is_business_day(local.date(), holidays) and OPENING <= local.time() < CLOSING
