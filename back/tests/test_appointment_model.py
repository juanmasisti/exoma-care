from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import AppointmentModel, ExtractionCenterModel, ProvinceModel
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyModel

LOCAL_NOON = datetime(2026, 11, 2, 12, 0, tzinfo=TIMEZONE)
SAME_IN_UTC = datetime.fromisoformat("2026-11-02T15:00:00+00:00")


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'appointments.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sessionmaker(engine).begin() as session:
        # Sin relaciones ORM la sesión no ordena por FK: se inserta en orden.
        for rows in ([ProvinceModel(id=1, name="DEMO"), Paciente(id=1, dni="45000001", nombre="Sofía", apellido="DEMO")],
                     [ExtractionCenterModel(id=1, name="Centro DEMO", address="Calle 1", city="DEMO",
                                            province_id=1, latitude=0, longitude=0)],
                     [StudyModel(id=i, patient_id=1, status="pagado") for i in (1, 2)]):
            session.add_all(rows)
            session.flush()
    yield sessionmaker(engine)
    engine.dispose()


def book(factory, study_id, starts_at, status="booked"):
    with factory.begin() as session:
        session.add(AppointmentModel(study_id=study_id, center_id=1, starts_at=starts_at, status=status,
                                     study_status_before="pagado"))


def test_same_instant_in_minus_03_and_utc_is_the_same_slot(factory):
    book(factory, 1, LOCAL_NOON)
    with factory() as session:
        stored = session.scalar(select(AppointmentModel.starts_at))
    assert stored == SAME_IN_UTC and stored.tzinfo == UTC
    with pytest.raises(IntegrityError):
        book(factory, 2, SAME_IN_UTC)


def test_cancelled_appointments_free_the_slot_and_the_study(factory):
    book(factory, 1, LOCAL_NOON, status="cancelled")
    book(factory, 1, LOCAL_NOON)


def test_a_study_has_only_one_booked_appointment(factory):
    book(factory, 1, LOCAL_NOON)
    with pytest.raises(IntegrityError):
        book(factory, 1, datetime(2026, 11, 3, 12, 0, tzinfo=TIMEZONE))


def test_unknown_study_or_center_is_rejected(factory):
    with pytest.raises(IntegrityError):
        book(factory, 99, LOCAL_NOON)
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(AppointmentModel(study_id=1, center_id=99, starts_at=LOCAL_NOON, status="booked",
                                     study_status_before="pagado"))


def test_naive_datetime_is_rejected(factory):
    with pytest.raises(Exception, match="zona horaria"):
        book(factory, 1, datetime(2026, 11, 2, 12, 0))
