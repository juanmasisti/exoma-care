"""Reglas puras de logística: días hábiles, feriados fijos, horarios, estados de turnos y de muestras."""
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
    IN_TRANSIT_TO_KOREA = "in_transit_to_korea"
    DISCARDED = "discarded"


# En orden; se descarta para remuestrear desde lista para retirar, recibida o en viaje a Corea.
SAMPLE_TRANSITIONS = {
    SampleStatus.READY_FOR_PICKUP: {SampleStatus.WITH_TRANSPORTER, SampleStatus.DISCARDED},
    SampleStatus.WITH_TRANSPORTER: {SampleStatus.RECEIVED},
    SampleStatus.RECEIVED: {SampleStatus.IN_SAMPLE_SET, SampleStatus.DISCARDED},
    SampleStatus.IN_SAMPLE_SET: {SampleStatus.IN_TRANSIT_TO_KOREA},
    SampleStatus.IN_TRANSIT_TO_KOREA: {SampleStatus.DISCARDED},
}


def can_change_sample(current: SampleStatus, new: SampleStatus) -> bool:
    return new in SAMPLE_TRANSITIONS.get(current, set())


MIN_SAMPLE_VOLUME_ML = Decimal("2")


def sample_is_usable(volume_ml: Decimal) -> bool:
    """Menos de 2 ml obliga a remuestrear."""
    return volume_ml >= MIN_SAMPLE_VOLUME_ML
