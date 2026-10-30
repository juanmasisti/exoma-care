from datetime import date, datetime, time

import pytest

from app.domain.entities.logistics import (
    TIMEZONE, _easter, available_slots, daily_slots, fixed_national_holidays,
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


def test_easter_based_holidays_2026():
    assert _easter(2026) == date(2026, 4, 5)
    assert HOLIDAYS_2026[date(2026, 4, 3)] == "Viernes Santo"
    assert HOLIDAYS_2026[date(2026, 2, 16)] == "Carnaval"
    assert HOLIDAYS_2026[date(2026, 2, 17)] == "Carnaval"
    assert date(2026, 8, 17) not in HOLIDAYS_2026
