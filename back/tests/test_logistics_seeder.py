"""Seeders de logística: turnos DEMO (T03d) y muestras DEMO en cada estado (base de T04 a T06)."""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import (
    SQLAlchemyExtractionCenterRepository,
)
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.infrastructure.repositories.sqlalchemy_study_request_repository import SqlAlchemyStudyRequestRepository
from app.use_cases.appointments import AppointmentService
from app.use_cases.studies import StudyService
from appointments_setup import DOCTOR, NOW, OTHER_PATIENT, OTHERS_STUDY, SOFIA, book, client  # noqa: F401
from seeders.logistics import seed_demo_booked_studies, seed_demo_logistics_samples


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


def test_logistics_samples_seeder_leaves_samples_in_each_status_and_is_idempotent(client):
    _, engine = client
    factory = sessionmaker(engine)
    assert seed_demo_logistics_samples(factory, now=NOW) == 26
    with Session(engine) as session:
        by_status = dict(session.execute(text("SELECT status, count(*) FROM samples GROUP BY status")).all())
        ready_centers = session.execute(text(
            "SELECT p.name, count(*) FROM samples s JOIN appointments a ON a.id = s.appointment_id "
            "JOIN extraction_centers c ON c.id = a.center_id JOIN provinces p ON p.id = c.province_id "
            "WHERE s.status = 'ready_for_pickup' GROUP BY p.name")).all()
        sets = session.execute(text(
            "SELECT ss.status, ss.authorization_pdf_path, count(i.id) FROM sample_sets ss "
            "JOIN sample_set_items i ON i.sample_set_id = ss.id GROUP BY ss.id ORDER BY ss.id")).all()
        studies = set(session.scalars(text("SELECT DISTINCT st.status FROM studies st JOIN samples s ON s.study_id = st.id")))
        # El nacimiento de cada una más un evento por paso: 2 por cada recibida y 3 por cada una en lote.
        events = session.scalar(text("SELECT count(*) FROM sample_events"))
    assert by_status == {"ready_for_pickup": 5, "received": 2, "in_sample_set": 19}
    assert dict(ready_centers) == {"Buenos Aires": 4, "Córdoba": 1}
    assert sets == [("closed", None, 10), ("assembling", None, 9)]
    assert studies == {"listo_para_retirar"}
    assert events == 26 + 2 * 2 + 19 * 3
    assert seed_demo_logistics_samples(factory, now=NOW) == 0


def test_logistics_samples_seeder_does_not_build_a_second_assembling_set(client):
    _, engine = client
    with Session(engine) as session:
        SQLAlchemySampleSetRepository(session).open_set(False, NOW)  # un lote de la demo, armándose
        session.commit()
    assert seed_demo_logistics_samples(sessionmaker(engine), now=NOW) == 7  # solo lista y recibida
    with Session(engine) as session:
        assert session.scalar(text("SELECT count(*) FROM sample_sets")) == 1
        assert session.scalar(text("SELECT count(*) FROM sample_set_items")) == 0


def test_logistics_samples_seeder_does_not_complete_a_half_loaded_group(client, capsys):
    _, engine = client
    factory = sessionmaker(engine)
    seed_demo_logistics_samples(factory, now=NOW)
    with Session(engine) as session:
        # Como una corrida cortada: el grupo recibida queda con uno solo de sus dos avisos.
        session.execute(text("UPDATE extraction_notices SET external_id = 'otro-aviso' "
                             "WHERE external_id = 'seed-logistica-recibida-2'"))
        session.commit()
    assert seed_demo_logistics_samples(factory, now=NOW) == 0
    assert "el grupo recibida quedó incompleto (1 de 2)" in capsys.readouterr().out
