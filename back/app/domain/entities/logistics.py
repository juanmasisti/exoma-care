"""Reglas puras de logística: días hábiles, feriados fijos y turnos de extracción."""
from datetime import date, datetime, time, timedelta
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


def available_slots(day: date, holidays, now: datetime) -> list[datetime]:
    if now.tzinfo is None:
        raise ValueError("La hora actual debe indicar la zona horaria.")
    # Un turno que empieza justo ahora ya no se puede reservar.
    return [slot for slot in daily_slots(day, holidays) if slot > now]
