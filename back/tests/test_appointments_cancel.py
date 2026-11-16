"""Cancelar un turno."""
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.api.routes.extraction_centers import get_clock
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import AppointmentModel
from app.infrastructure.database.study_models import StudyModel
from app.main import app
from appointments_setup import (ADMIN, AUTHORIZED, DOCTOR, MONDAY_10, NOW, OTHER_PATIENT, PAID, SOFIA, book, client, login,
                                monday_slots, study_status)


def test_cancel_and_book_again_end_to_end(client):
    http, engine = client
    appointment_id = book(http, AUTHORIZED).json()["id"]
    assert http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http)).status_code == 200
    assert study_status(engine, AUTHORIZED) == "turno_sacado"

    assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http)).status_code == 204
    assert study_status(engine, AUTHORIZED) == "autorizado"
    with Session(engine) as session:
        cancelled = session.get(AppointmentModel, appointment_id)
        assert cancelled.status == "cancelled" and cancelled.cancelled_at == NOW
    assert http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http)).status_code == 404
    assert MONDAY_10 in monday_slots(http)

    again = book(http, AUTHORIZED)
    assert again.status_code == 201 and again.json()["starts_at"] == MONDAY_10
    assert study_status(engine, AUTHORIZED) == "turno_sacado"


def test_cancel_rules(client):
    http, engine = client
    appointment_id = book(http).json()["id"]
    for user in (DOCTOR, ADMIN):
        assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http, user)).status_code == 403
    for identifier, user in ((appointment_id, OTHER_PATIENT), (999, SOFIA)):
        response = http.delete(f"/api/appointments/{identifier}", headers=login(http, user))
        assert response.status_code == 404 and response.json()["detail"] == "El turno no existe."
    assert study_status(engine, PAID) == "turno_sacado"
    assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http)).status_code == 204
    again = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert again.status_code == 409 and again.json()["detail"] == "Solo se puede cancelar un turno reservado."
    assert study_status(engine, PAID) == "pagado"


@pytest.mark.parametrize("now", [datetime(2026, 11, 2, 10, tzinfo=TIMEZONE), datetime(2026, 11, 3, 9, tzinfo=TIMEZONE)])
def test_an_appointment_that_already_started_cannot_be_cancelled(client, now):
    http, engine = client
    appointment_id = book(http).json()["id"]
    app.dependency_overrides[get_clock] = lambda: now
    response = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert response.status_code == 409 and response.json()["detail"] == "No se puede cancelar un turno que ya empezó."
    assert study_status(engine, PAID) == "turno_sacado"
    with Session(engine) as session:
        assert session.get(AppointmentModel, appointment_id).status == "booked"


def test_cancel_does_not_move_back_a_study_that_advanced(client):
    http, engine = client
    appointment_id = book(http).json()["id"]
    with Session(engine) as session:  # p. ej., el aviso de extracción de T03
        session.get(StudyModel, PAID).status = "listo_para_retirar"
        session.commit()
    response = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert response.status_code == 409
    assert response.json()["detail"] == "El turno ya no se puede cancelar: el estudio pasó a otra etapa."
    assert study_status(engine, PAID) == "listo_para_retirar"
    with Session(engine) as session:
        assert session.get(AppointmentModel, appointment_id).status == "booked"
