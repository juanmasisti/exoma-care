from decimal import Decimal

import pytest

from app.domain.entities.budget import normalize_percent, split_amounts, to_cents
from app.domain.entities.study_request import (
    status_after_authorization,
    status_after_mode_choice,
    status_after_patient_payment,
)


def test_without_coverage_or_coupon_the_patient_pays_everything():
    split = split_amounts(to_cents(500))
    assert (split.insurer_cents, split.discount_cents, split.patient_cents) == (0, 0, 50000)


def test_partial_coverage_leaves_the_rest_to_the_patient():
    split = split_amounts(to_cents(500), coverage_percent=40)
    assert split.insurer_cents == 20000
    assert split.patient_gross_cents == 30000
    assert split.patient_cents == 30000


def test_coupon_applies_only_to_what_the_patient_pays():
    split = split_amounts(to_cents(500), coverage_percent=40, coupon_percent=20)
    assert split.insurer_cents == 20000
    assert split.discount_cents == 6000  # 20 % de 300, no de 500
    assert split.patient_cents == 24000


def test_full_coverage_leaves_nothing_to_pay():
    split = split_amounts(to_cents(530), coverage_percent=100, coupon_percent=50)
    assert (split.insurer_cents, split.patient_gross_cents, split.discount_cents, split.patient_cents) == (
        53000,
        0,
        0,
        0,
    )


def test_full_coupon_makes_the_particular_payment_free():
    assert split_amounts(to_cents(500), coupon_percent=100).patient_cents == 0


@pytest.mark.parametrize("total", [0, 1, 99, 50000, 53000, 59000, 123457])
@pytest.mark.parametrize("coverage", [0, 12.5, 33.33, 40, 66.67, 100])
@pytest.mark.parametrize("coupon", [0, 5, 15, 33.3, 100])
def test_the_three_parts_always_add_up_to_the_total(total, coverage, coupon):
    split = split_amounts(total, coverage, coupon)
    assert split.insurer_cents + split.discount_cents + split.patient_cents == total
    assert min(split.insurer_cents, split.discount_cents, split.patient_cents) >= 0


def test_rounding_is_half_up_to_the_cent():
    # 53000 * 33.33 % = 17664.9 centavos -> 17665
    assert split_amounts(53000, coverage_percent=Decimal("33.33")).insurer_cents == 17665
    # 5 centavos * 50 % = 2.5 -> 3 (mitad hacia arriba)
    assert split_amounts(5, coverage_percent=50).insurer_cents == 3


@pytest.mark.parametrize("value", [-1, 100.01, "abc", None, float("nan"), float("inf"), True])
def test_invalid_percentages_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_percent(value)
    with pytest.raises(ValueError):
        split_amounts(50000, coverage_percent=value)


def test_negative_total_is_rejected():
    with pytest.raises(ValueError):
        split_amounts(-1)


def test_statuses_follow_the_payment_flow():
    assert status_after_mode_choice("particular") == "pendiente_pago"
    assert status_after_mode_choice("obra_social") == "pendiente_autorizacion"
    assert status_after_authorization(0) == "autorizado"
    assert status_after_authorization(30000) == "pendiente_pago"
    assert status_after_patient_payment("particular") == "pagado"
    assert status_after_patient_payment("obra_social") == "autorizado"
    for function in (status_after_mode_choice, status_after_patient_payment):
        with pytest.raises(ValueError):
            function("efectivo")
