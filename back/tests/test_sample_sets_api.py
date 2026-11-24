"""Armado automático de sample sets, Pompe urgente y consulta de lotes (T05)."""
from datetime import UTC, date, datetime

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.routes.sample_sets import get_sample_set_assigner
from app.api.routes.shipments import get_sample_set_closed_handler
from app.infrastructure.database.session import Base
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.domain.interfaces.sample_set_repository import SetNotAssembling
from app.use_cases.sample_sets import SampleSetService, pompe_reference_date

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
# Alta de los estudios: es la fecha de referencia de "menor de 4 meses" (decisión 018).
STUDY_CREATED = "2026-11-01 12:00:00"
THREE_MONTHS_OLD = date(2026, 8, 1)
# Cumple 4 meses el 15/11: menor al alta del estudio (1/11), pero no a la llegada (NOW, 23/11).
FOUR_MONTHS_AFTER_CREATION = date(2026, 7, 15)
FIVE_MONTHS_OLD = date(2026, 6, 1)


class CountingClosedHandler:
    def __init__(self):
        self.calls = []

    def al_cerrar_lote(self, sample_set_id: int, now: datetime) -> None:
        self.calls.append(sample_set_id)


def add_sample(session, sample_id, status="received", birth_date=None, pathology_code=None):
    """Una muestra con su propio paciente DEMO, estudio, turno y aviso."""
    params = {"id": sample_id, "status": status, "birth": birth_date and birth_date.isoformat(),
              "code": pathology_code, "created": STUDY_CREATED}
    session.execute(text("INSERT INTO patients (id, dni, nombre, apellido, fecha_nacimiento) "
                         "VALUES (:id, 'DEMO-' || :id, 'Demo', 'DEMO', :birth)"), params)
    session.execute(text("INSERT INTO studies (id, patient_id, status, created_at) "
                         "VALUES (:id, :id, 'listo_para_retirar', :created)"), params)
    if pathology_code:
        session.execute(text("INSERT INTO study_pathologies (study_id, code, name) "
                             "VALUES (:id, :code, 'DEMO')"), params)
    session.execute(text("""INSERT INTO appointments
        (id, study_id, center_id, starts_at, status, study_status_before, created_at)
        VALUES (:id, :id, 1, '2026-11-02 13:00:00', 'attended', 'pagado', '2026-11-01 13:00:00')"""), params)
    session.execute(text("INSERT INTO extraction_notices (id, external_id, payload, received_at) "
                         "VALUES (:id, 'aviso-' || :id, '{}', '2026-11-02')"), params)
    session.execute(text("""INSERT INTO samples
        (id, study_id, appointment_id, extraction_notice_id, volume_ml, status, is_current)
        VALUES (:id, :id, :id, :id, 3, :status, 1)"""), params)


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sample-sets.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO provinces (id, name) VALUES (1, 'DEMO')"))
        connection.execute(text("INSERT INTO extraction_centers "
                                "(id, name, address, city, province_id, latitude, longitude, active) "
                                "VALUES (1, 'Centro DEMO 1', 'Calle DEMO 1', 'DEMO', 1, 0, 0, 1)"))
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def service(session, sample_sets=None, handler=None):
    return SampleSetService(sample_sets or SQLAlchemySampleSetRepository(session), SQLAlchemySampleRepository(session),
                            handler or CountingClosedHandler())


def statuses(session):
    return dict(session.execute(text("SELECT id, status FROM sample_sets ORDER BY id")).all())


def items(session):
    return session.execute(text("SELECT sample_set_id, slot, sample_id FROM sample_set_items ORDER BY sample_id")).all()


def test_nine_samples_keep_the_set_open_the_tenth_closes_it_and_the_eleventh_opens_another(session):
    handler = CountingClosedHandler()
    sample_sets = service(session, handler=handler)
    for sample_id in range(1, 12):
        add_sample(session, sample_id)
    for sample_id in range(1, 10):
        sample_sets.asignar_a_sample_set(sample_id, NOW)
    assert statuses(session) == {1: "assembling"}
    sample_sets.asignar_a_sample_set(10, NOW)
    assert statuses(session) == {1: "closed"} and handler.calls == [1]
    sample_sets.asignar_a_sample_set(11, NOW)
    assert statuses(session) == {1: "closed", 2: "assembling"} and handler.calls == [1]
    assert [(set_id, slot) for set_id, slot, _ in items(session)] == [(1, n) for n in range(1, 11)] + [(2, 1)]
    moved = session.scalars(text("SELECT DISTINCT status FROM samples")).all()
    assert moved == ["in_sample_set"]
    assert session.scalar(text("SELECT count(*) FROM sample_events WHERE to_status = 'in_sample_set'")) == 11


class SlotStolenRepository(SQLAlchemySampleSetRepository):
    """Otro pedido ocupa el lugar leído antes de que este escriba.

    SQLite escribe de a uno y la llegada ya tiene el lock (movió la muestra): el otro pedido se simula en la
    misma sesión, entre la lectura del lote y el alta.
    """

    def __init__(self, session, rival_sample_id):
        super().__init__(session)
        self.rival_sample_id = rival_sample_id

    def add_item(self, sample_set_id, sample_id, slot):
        if self.rival_sample_id is not None:
            rival, self.rival_sample_id = self.rival_sample_id, None
            super().add_item(sample_set_id, rival, slot)
        super().add_item(sample_set_id, sample_id, slot)


def test_two_assignments_on_the_same_slot_lose_nothing_and_no_set_goes_over_ten(session):
    for sample_id in range(1, 13):
        add_sample(session, sample_id)
    sample_sets = service(session)
    for sample_id in range(1, 9):
        sample_sets.asignar_a_sample_set(sample_id, NOW)
    # La 9.ª lee el lugar 9 libre, pero lo gana la 12.ª: la 9.ª toma el 10 y el lote se cierra lleno.
    handler = CountingClosedHandler()
    service(session, SlotStolenRepository(session, rival_sample_id=12), handler).asignar_a_sample_set(9, NOW)
    assert statuses(session) == {1: "closed"} and handler.calls == [1]
    assert [(slot, sample_id) for _, slot, sample_id in items(session)][8:] == [(10, 9), (9, 12)]
    # La 10.ª ya no entra en el lote lleno: va a uno nuevo.
    sample_sets.asignar_a_sample_set(10, NOW)
    assert statuses(session) == {1: "closed", 2: "assembling"}
    counts = session.execute(text("SELECT sample_set_id, count(*) FROM sample_set_items GROUP BY sample_set_id")).all()
    assert counts == [(1, 10), (2, 1)]


class ClosedAfterReadRepository(SQLAlchemySampleSetRepository):
    """Otro pedido (un Pompe urgente) cierra el lote después de que la llegada lo leyó armándose."""

    closed = False

    def add_item(self, sample_set_id, sample_id, slot):
        if not self.closed:
            self.closed = True
            self.session.execute(text("UPDATE sample_sets SET status = 'closed', version = version + 1 WHERE id = :id"),
                                 {"id": sample_set_id})
        super().add_item(sample_set_id, sample_id, slot)


def test_a_set_closed_after_being_read_does_not_take_the_sample_and_it_goes_to_a_new_set(session):
    for sample_id in range(1, 4):
        add_sample(session, sample_id)
    service(session).asignar_a_sample_set(1, NOW)
    service(session).asignar_a_sample_set(2, NOW)
    service(session, ClosedAfterReadRepository(session)).asignar_a_sample_set(3, NOW)
    assert statuses(session) == {1: "closed", 2: "assembling"}
    assert items(session) == [(1, 1, 1), (1, 2, 2), (2, 1, 3)]


def test_an_urgent_pompe_closes_the_set_with_what_it_has(session):
    handler = CountingClosedHandler()
    for sample_id in range(1, 4):
        add_sample(session, sample_id)
    add_sample(session, 4, birth_date=THREE_MONTHS_OLD, pathology_code="pompe")  # el catálogo DEMO usa minúsculas
    sample_sets = service(session, handler=handler)
    for sample_id in range(1, 5):
        sample_sets.asignar_a_sample_set(sample_id, NOW)
    assert statuses(session) == {1: "closed"} and handler.calls == [1]
    assert session.scalar(text("SELECT is_urgent FROM sample_sets WHERE id = 1")) == 1
    assert len(items(session)) == 4


def test_pompe_older_than_four_months_does_not_close_the_set(session):
    for sample_id in range(1, 4):
        add_sample(session, sample_id)
    add_sample(session, 4, birth_date=FIVE_MONTHS_OLD, pathology_code="POMPE")
    sample_sets = service(session)
    for sample_id in range(1, 5):
        sample_sets.asignar_a_sample_set(sample_id, NOW)
    assert statuses(session) == {1: "assembling"}


def test_an_urgent_pompe_without_an_assembling_set_leaves_in_a_set_of_one(session):
    # Propuesta pendiente de confirmar con el profesor (decisión abierta 6).
    handler = CountingClosedHandler()
    add_sample(session, 1, birth_date=THREE_MONTHS_OLD, pathology_code="POMPE")
    service(session, handler=handler).asignar_a_sample_set(1, NOW)
    assert statuses(session) == {1: "closed"} and handler.calls == [1]
    assert session.scalar(text("SELECT is_urgent FROM sample_sets WHERE id = 1")) == 1


def test_pompe_urgency_uses_the_study_creation_date_and_no_birth_date_is_not_urgent(session):
    add_sample(session, 1, birth_date=FOUR_MONTHS_AFTER_CREATION, pathology_code="POMPE")
    add_sample(session, 2, birth_date=None, pathology_code="POMPE")
    add_sample(session, 3, birth_date=THREE_MONTHS_OLD, pathology_code="FABRY")
    sample_sets = service(session)
    assert sample_sets.es_pompe_urgente(1)
    assert not sample_sets.es_pompe_urgente(2)  # ABIERTO: sin fecha de nacimiento, no es urgente
    assert not sample_sets.es_pompe_urgente(3)
    with pytest.raises(LookupError):
        sample_sets.es_pompe_urgente(999)
    sample_sets.asignar_a_sample_set(1, NOW)
    assert statuses(session) == {1: "closed"}  # urgente al alta, aunque a la llegada ya tenga 4 meses
    # Medianoche UTC todavía es el día anterior en Buenos Aires.
    assert pompe_reference_date(datetime(2026, 11, 2, 1, 0)) == date(2026, 11, 1)


def test_a_sample_that_is_not_received_is_rejected_and_leaves_nothing(session):
    add_sample(session, 1, status="with_transporter")
    with pytest.raises(ValueError):
        service(session).asignar_a_sample_set(1, NOW)
    assert items(session) == [] and statuses(session) == {}
    with pytest.raises(LookupError):
        service(session).asignar_a_sample_set(999, NOW)
    with pytest.raises(ValueError):
        service(session).asignar_a_sample_set(1, NOW.replace(tzinfo=None))


class OpenedMeanwhileRepository(SQLAlchemySampleSetRepository):
    """Otro pedido abre un lote entre que este ve que no hay ninguno y lo intenta abrir."""

    rival_opened = False

    def assembling(self):
        if not self.rival_opened:
            self.rival_opened = True
            self.open_set(False, NOW)
            return None
        return super().assembling()


def test_a_set_opened_meanwhile_by_another_request_is_used_instead_of_opening_a_second_one(session):
    add_sample(session, 1)
    service(session, OpenedMeanwhileRepository(session)).asignar_a_sample_set(1, NOW)
    assert statuses(session) == {1: "assembling"} and items(session) == [(1, 1, 1)]


class LastSlotStolenRepository(SQLAlchemySampleSetRepository):
    """Otro pedido gana el lugar 10 y cierra el lote: este prueba el 11, que ya no existe."""

    def add_item(self, sample_set_id, sample_id, slot):
        if slot == 10:
            super().add_item(sample_set_id, 12, 10)
        if slot == 11:
            self.close(sample_set_id, NOW)
        super().add_item(sample_set_id, sample_id, slot)


def test_when_another_request_fills_the_set_the_sample_goes_to_a_new_one(session):
    for sample_id in range(1, 13):
        add_sample(session, sample_id)
    for sample_id in range(1, 10):
        service(session).asignar_a_sample_set(sample_id, NOW)
    handler = CountingClosedHandler()
    service(session, LastSlotStolenRepository(session), handler).asignar_a_sample_set(10, NOW)
    assert statuses(session) == {1: "closed", 2: "assembling"}
    assert handler.calls == []  # el cierre lo avisó el otro pedido
    assert (2, 1, 10) in items(session)


class AlwaysClosedRepository(SQLAlchemySampleSetRepository):
    def add_item(self, sample_set_id, sample_id, slot):
        raise SetNotAssembling()


def test_too_many_conflicts_in_a_row_raise_so_the_arrival_is_undone(session):
    add_sample(session, 1)
    with pytest.raises(RuntimeError):
        service(session, AlwaysClosedRepository(session)).asignar_a_sample_set(1, NOW)


def test_the_assigner_hook_runs_in_the_request_session_with_the_closed_handler_and_does_not_commit(engine):
    with Session(engine) as session:
        for sample_id in range(1, 11):
            add_sample(session, sample_id)
        session.commit()
    handler = CountingClosedHandler()
    sessions = []

    def database_session():
        with Session(engine) as session:
            sessions.append(session)
            yield session

    # Una llegada mínima, como la de T04: asigna con el enganche y confirma ella.
    arrival = FastAPI()

    @arrival.post("/arrival/{commit}")
    def arrive(commit: bool, assigner=Depends(get_sample_set_assigner),
               session: Session = Depends(get_database_session)):
        for sample_id in range(1, 11):
            assigner.asignar_a_sample_set(sample_id, NOW)
        if commit:
            session.commit()

    arrival.dependency_overrides = {get_database_session: database_session,
                                    get_sample_set_closed_handler: lambda: handler}
    with TestClient(arrival) as http:
        assert http.post("/arrival/false").status_code == 200
        assert len(sessions) == 1  # el enganche usó la sesión del pedido
        with Session(engine) as session:
            assert statuses(session) == {}  # sin el commit de la llegada no queda nada
        assert http.post("/arrival/true").status_code == 200
    assert handler.calls == [1, 1]  # una vez por pedido: el primero se deshizo
    with Session(engine) as session:
        assert statuses(session) == {1: "closed"}
