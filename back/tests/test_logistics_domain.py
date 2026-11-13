from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.domain.entities.logistics import (
    TIMEZONE, AppointmentStatus, SampleStatus, _easter, available_slots, can_change_appointment, can_change_sample,
    daily_slots, fixed_national_holidays, is_valid_slot, sample_is_usable, study_code, study_id_from_code,
)

MONDAY = date(2026, 11, 2)
HOLIDAYS_2026 = fixed_national_holidays(2026)


def test_business_day_has_36_slots_from_9_to_17_45():
    slots = daily_slots(MONDAY, HOLIDAYS_2026)
    assert len(slots) == 36
    assert slots[0] == datetime(2026, 11, 2, 9, 0, tzinfo=TIMEZONE)
    assert slots[-1] == datetime(2026, 11, 2, 17, 45, tzinfo=TIMEZONE)


@pytest.mark.parametrize("day", [date(2026, 10, 31), date(2026, 11, 1), date(2026, 12, 25)])
def test_no_slots_on_weekends_or_holidays(day):
    assert daily_slots(day, HOLIDAYS_2026) == []


def test_available_slots_skip_the_ones_already_started():
    now = datetime(2026, 11, 2, 12, 5, tzinfo=TIMEZONE)
    assert available_slots(MONDAY, HOLIDAYS_2026, now)[0].time() == time(12, 15)


def test_slot_starting_right_now_is_not_available():
    now = datetime(2026, 11, 2, 12, 15, tzinfo=TIMEZONE)
    assert available_slots(MONDAY, HOLIDAYS_2026, now)[0].time() == time(12, 30)


def test_available_slots_require_timezone():
    with pytest.raises(ValueError):
        available_slots(MONDAY, HOLIDAYS_2026, datetime(2026, 11, 2, 12, 5))


def test_available_slots_skip_booked_ones():
    now = datetime(2026, 11, 1, 10, tzinfo=TIMEZONE)
    booked = [datetime(2026, 11, 2, 9, 0, tzinfo=TIMEZONE), datetime(2026, 11, 2, 12, 15, tzinfo=TIMEZONE)]
    slots = available_slots(MONDAY, HOLIDAYS_2026, now, booked)
    assert len(slots) == 34 and not set(booked) & set(slots)


@pytest.mark.parametrize("starts_at", [
    datetime(2026, 11, 7, 10, 0, tzinfo=TIMEZONE),   # sábado
    datetime(2026, 12, 8, 10, 0, tzinfo=TIMEZONE),   # feriado
    datetime(2026, 11, 2, 18, 0, tzinfo=TIMEZONE),   # cierre
    datetime(2026, 11, 2, 8, 45, tzinfo=TIMEZONE),   # antes de abrir
    datetime(2026, 11, 2, 9, 10, tzinfo=TIMEZONE),   # fuera de los 15 minutos
    datetime(2026, 11, 2, 9, 15, 30, tzinfo=TIMEZONE),
])
def test_invalid_slots(starts_at):
    assert not is_valid_slot(starts_at, HOLIDAYS_2026)


def test_valid_slots_in_any_timezone():
    assert is_valid_slot(datetime(2026, 11, 2, 9, 0, tzinfo=TIMEZONE), HOLIDAYS_2026)
    assert is_valid_slot(datetime(2026, 11, 2, 17, 45, tzinfo=TIMEZONE), HOLIDAYS_2026)
    # 20:45 UTC son las 17:45 en Buenos Aires.
    assert is_valid_slot(datetime.fromisoformat("2026-11-02T20:45:00+00:00"), HOLIDAYS_2026)


def test_valid_slot_requires_timezone():
    with pytest.raises(ValueError):
        is_valid_slot(datetime(2026, 11, 2, 10, 0), HOLIDAYS_2026)


def test_only_booked_appointments_change_status():
    booked = AppointmentStatus.BOOKED
    assert all(can_change_appointment(booked, new) for new in
               (AppointmentStatus.CANCELLED, AppointmentStatus.ATTENDED, AppointmentStatus.ABSENT))
    assert not can_change_appointment(booked, booked)
    for final in (AppointmentStatus.CANCELLED, AppointmentStatus.ATTENDED, AppointmentStatus.ABSENT):
        assert not any(can_change_appointment(final, new) for new in AppointmentStatus)


def test_study_code_has_six_digits():
    assert study_code(1) == "EST-000001"
    assert study_code(123456) == "EST-123456"


def test_study_id_from_code_is_the_inverse_of_study_code():
    assert study_id_from_code(study_code(42)) == 42
    assert study_id_from_code("EST-1234567") == 1234567


@pytest.mark.parametrize("code", ["EST-1", "EST-000000", "EST-0000001", "EST-١٢٣٤٥٦",
                                  "est-000001", "EST-00000A", "EST-000001 ", "000001", ""])
def test_study_id_from_invalid_code_is_none(code):
    assert study_id_from_code(code) is None


@pytest.mark.parametrize("volume, usable", [("1.9", False), ("1.99", False), ("2.0", True), ("2", True), ("5.5", True)])
def test_sample_needs_at_least_2_ml(volume, usable):
    assert sample_is_usable(Decimal(volume)) is usable


def test_sample_moves_forward_in_order():
    path = [SampleStatus.READY_FOR_PICKUP, SampleStatus.WITH_TRANSPORTER, SampleStatus.RECEIVED,
            SampleStatus.IN_SAMPLE_SET, SampleStatus.IN_TRANSIT_TO_KOREA]
    assert all(can_change_sample(current, new) for current, new in zip(path, path[1:]))
    assert not can_change_sample(SampleStatus.RECEIVED, SampleStatus.WITH_TRANSPORTER)
    assert not can_change_sample(SampleStatus.READY_FOR_PICKUP, SampleStatus.RECEIVED)


def test_sample_is_discarded_only_from_the_remuestreo_states():
    allowed = {SampleStatus.READY_FOR_PICKUP, SampleStatus.RECEIVED, SampleStatus.IN_TRANSIT_TO_KOREA}
    for status in SampleStatus:
        assert can_change_sample(status, SampleStatus.DISCARDED) is (status in allowed)
    assert not any(can_change_sample(SampleStatus.DISCARDED, new) for new in SampleStatus)


def test_easter_based_holidays_2026():
    assert _easter(2026) == date(2026, 4, 5)
    assert HOLIDAYS_2026[date(2026, 4, 3)] == "Viernes Santo"
    assert HOLIDAYS_2026[date(2026, 2, 16)] == "Carnaval"
    assert HOLIDAYS_2026[date(2026, 2, 17)] == "Carnaval"
    assert date(2026, 8, 17) not in HOLIDAYS_2026
