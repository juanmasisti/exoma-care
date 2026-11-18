"""Seeder de turnos DEMO para el simulador del bot (T03d): 3 estudios pagados con turno reservado."""
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import (
    SQLAlchemyExtractionCenterRepository,
)
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.infrastructure.repositories.sqlalchemy_study_request_repository import SqlAlchemyStudyRequestRepository
from app.use_cases.appointments import AppointmentService
from app.use_cases.studies import StudyService
from appointments_setup import DOCTOR, NOW, OTHER_PATIENT, OTHERS_STUDY, SOFIA, book, client  # noqa: F401
from seeders.logistics import seed_demo_booked_studies


def booked(engine):
    with Session(engine) as session:
        return SQLAlchemyAppointmentRepository(session).booked_for_user(SOFIA)


def test_seeder_leaves_three_studies_paid_through_the_study_flow_with_a_booked_appointment(client):
    _, engine = client
    assert seed_demo_booked_studies(sessionmaker(engine), now=NOW) == 3  # NOW es domingo 1/11/2026
    appointments = booked(engine)
    assert [a["starts_at"].isoformat() for a in appointments] == [
        "2026-11-02T10:00:00-03:00", "2026-11-03T10:00:00-03:00", "2026-11-04T10:00:00-03:00"]
    assert all(a["center"]["name"].startswith("Centro de extracción DEMO") for a in appointments)
    with Session(engine) as session:
        studies = SqlAlchemyStudyRequestRepository(session)
        for appointment in appointments:
            study = studies.get_study(appointment["study_id"])
            assert (study.status, study.physician_id) == ("turno_sacado", DOCTOR)
            assert [p.code for p in study.pathologies] == ["fabry"]
            assert studies.get_budget(study.id).payment_mode == "particular"
            [operation] = studies.list_operations(study.id)
            assert operation["status"] == "registrada"


def test_seeder_is_idempotent_and_replaces_used_studies(client):
    _, engine = client
    factory = sessionmaker(engine)
    seed_demo_booked_studies(factory, now=NOW)
    assert seed_demo_booked_studies(factory, now=NOW) == 0
    assert len(booked(engine)) == 3
    # Como después del simulador: el turno de uno queda asistido y deja de estar reservado.
    with Session(engine) as session:
        AppointmentService(SQLAlchemyAppointmentRepository(session), SQLAlchemyExtractionCenterRepository(session),
                           StudyService(SQLAlchemyStudyRepository(session))).registrar_asistencia(
            booked(engine)[0]["id"], True)
    assert len(booked(engine)) == 2
    assert seed_demo_booked_studies(factory, now=NOW) == 1
    assert len(booked(engine)) == 3


def test_seeder_skips_weekends_and_taken_slots(client):
    http, engine = client
    # Otro paciente ya tiene las 10:00 del viernes en el mismo centro DEMO.
    assert book(http, OTHERS_STUDY, starts_at="2026-11-06T10:00:00-03:00", user=OTHER_PATIENT).status_code == 201
    thursday = datetime(2026, 11, 5, 12, tzinfo=TIMEZONE)
    seed_demo_booked_studies(sessionmaker(engine), now=thursday)
    assert [a["starts_at"].date().isoformat() for a in booked(engine)] == ["2026-11-09", "2026-11-10", "2026-11-11"]
