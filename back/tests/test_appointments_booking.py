"""Reservar un turno."""
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.database.logistics_models import AppointmentModel, ExtractionCenterModel
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.use_cases.appointments import AppointmentService
from app.use_cases.studies import StudyService
from appointments_setup import (AUTHORIZED, MONDAY_10, NOW, OTHERS_STUDY, PAID, PENDING, REJECTED, SOFIA, UNLINKED_PATIENT,
                                appointment_count, book, client, monday_slots, study_status)


def test_booking_returns_the_appointment_and_marks_the_study(client):
    http, engine = client
    response = book(http)
    assert response.status_code == 201
    body = response.json()
    assert body["starts_at"] == MONDAY_10 and body["status"] == "booked" and body["study_id"] == PAID
    assert body["center"]["id"] == 1 and body["center"]["name"]
    assert study_status(engine, PAID) == "turno_sacado"
    with Session(engine) as session:
        assert session.get(AppointmentModel, body["id"]).study_status_before == "pagado"
    assert MONDAY_10 not in monday_slots(http)


@pytest.mark.parametrize("starts_at", [
    "2026-11-07T10:00:00-03:00",  # sábado
    "2026-12-08T10:00:00-03:00",  # feriado
    "2026-11-02T18:00:00-03:00",  # cierre
    "2026-11-02T09:10:00-03:00",  # fuera de los 15 minutos
    "2026-10-30T10:00:00-03:00",  # viernes pasado según el reloj
    "2026-11-02T10:00:00",        # sin zona horaria
])
def test_invalid_or_past_slot_is_422(client, starts_at):
    http, engine = client
    assert book(http, starts_at=starts_at).status_code == 422
    assert appointment_count(engine) == 0 and study_status(engine, PAID) == "pagado"


def test_same_center_and_slot_twice_is_one_201_and_one_409(client):
    http, engine = client
    assert book(http, PAID).status_code == 201
    second = book(http, AUTHORIZED, starts_at="2026-11-02T13:00:00+00:00")  # mismas 10:00 en UTC
    assert second.status_code == 409
    assert second.json()["detail"] == "El horario ya está reservado en este centro."
    assert study_status(engine, AUTHORIZED) == "autorizado" and appointment_count(engine) == 1


def test_study_with_another_booked_appointment_is_409(client):
    http, engine = client
    assert book(http, PAID).status_code == 201
    with Session(engine) as session:  # simula dos reservas simultáneas del mismo estudio
        session.get(StudyModel, PAID).status = "pagado"
        session.commit()
    response = book(http, PAID, starts_at="2026-11-02T11:00:00-03:00")
    assert response.status_code == 409 and response.json()["detail"] == "El estudio ya tiene un turno vigente."
    assert appointment_count(engine) == 1


@pytest.mark.parametrize("study_id, status", [(PENDING, "pendiente_pago"), (REJECTED, "rechazado")])
def test_study_not_enabled_is_409(client, study_id, status):
    http, engine = client
    response = book(http, study_id)
    assert response.status_code == 409 and "no está habilitado" in response.json()["detail"]
    assert appointment_count(engine) == 0 and study_status(engine, study_id) == status


@pytest.mark.parametrize("study_id, user", [(OTHERS_STUDY, SOFIA), (999, SOFIA), (PAID, UNLINKED_PATIENT)])
def test_foreign_missing_or_unlinked_study_is_404(client, study_id, user):
    http, engine = client
    response = book(http, study_id, user=user)
    assert response.status_code == 404 and response.json()["detail"] == "El estudio no existe o no es tuyo."
    assert study_status(engine, OTHERS_STUDY) == "pagado" and appointment_count(engine) == 0


def test_missing_or_inactive_center_is_404(client):
    http, engine = client
    with Session(engine) as session:
        session.get(ExtractionCenterModel, 2).active = False
        session.commit()
    for center_id in (2, 9999):
        response = book(http, center_id=center_id)
        assert response.status_code == 404
        assert response.json()["detail"] == "El centro de extracción no existe o no está activo."


def test_if_the_study_change_fails_no_appointment_is_left(client):
    _, engine = client

    class FailingStudyService(StudyService):
        def cambiar_estado_estudio(self, study_id, nuevo_estado):
            super().cambiar_estado_estudio(study_id, nuevo_estado)
            raise RuntimeError("falla simulada del módulo de estudios")

    with Session(engine) as session:
        service = AppointmentService(SQLAlchemyAppointmentRepository(session),
                                     SQLAlchemyExtractionCenterRepository(session),
                                     FailingStudyService(SQLAlchemyStudyRepository(session)))
        with pytest.raises(RuntimeError):
            service.reservar(SOFIA, PAID, 1, datetime.fromisoformat(MONDAY_10), NOW)
    assert appointment_count(engine) == 0 and study_status(engine, PAID) == "pagado"
