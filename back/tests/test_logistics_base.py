"""Tablas, restricciones y repositorios compartidos de transporte, lotes y envío (base de T04 a T06)."""
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.logistics import SampleSetStatus, SampleStatus
from app.domain.interfaces.route_repository import RouteAlreadyExists
from app.domain.interfaces.sample_set_repository import AssemblingSetExists, SampleAlreadyInSet, SetFull, SetNotAssembling, SlotTaken
from app.infrastructure.database.logistics_models import SampleSetModel
from app.infrastructure.repositories.sqlalchemy_route_repository import SQLAlchemyRouteRepository
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.infrastructure.repositories.sqlalchemy_shipment_repository import SQLAlchemyShipmentRepository

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
SAMPLES = 12
CONFIG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _insert_samples(connection, status):
    connection.execute(text("INSERT INTO provinces (id, name) VALUES (1, 'DEMO')"))
    connection.execute(text("""INSERT INTO extraction_centers (id, name, address, city, province_id, latitude, longitude, active)
        VALUES (1, 'Centro DEMO 1', 'Calle DEMO 1', 'DEMO', 1, 0, 0, 1), (2, 'Centro DEMO 2', 'Calle DEMO 2', 'DEMO', 1, 1, 1, 1)"""))
    connection.execute(text("INSERT INTO users (id, username, role, first_name, last_name, phone, email, password_hash) "
                            "VALUES (1, 'demo', 'patient', 'Demo', 'Prueba', '000', 'demo@example.test', 'x')"))
    connection.execute(text("INSERT INTO patients (id, dni, nombre, apellido, usuario_id) VALUES (1, '45000001', 'Demo', 'DEMO', 1)"))
    for number in range(1, SAMPLES + 1):
        params = {"id": number, "status": status}
        connection.execute(text("INSERT INTO studies (id, patient_id, status, created_at) "
                                "VALUES (:id, 1, 'listo_para_retirar', '2026-11-01')"), params)
        connection.execute(text("""INSERT INTO appointments (id, study_id, center_id, starts_at, status, study_status_before, created_at)
            VALUES (:id, :id, 1, '2026-11-02 13:00:00', 'attended', 'pagado', '2026-11-01 13:00:00')"""), params)
        connection.execute(text("INSERT INTO extraction_notices (id, external_id, payload, received_at) "
                                "VALUES (:id, 'aviso-' || :id, '{}', '2026-11-02')"), params)
        connection.execute(text("""INSERT INTO samples (id, study_id, appointment_id, extraction_notice_id, volume_ml, status, is_current)
            VALUES (:id, :id, :id, :id, 3, :status, 1)"""), params)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    database = tmp_path / "logistics-base.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    command.upgrade(CONFIG, "head")
    engine = create_engine(f"sqlite:///{database}")
    # Como la app (session.py): SQLite solo aplica las claves foráneas si se le pide.
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    with engine.begin() as connection:
        _insert_samples(connection, SampleStatus.READY_FOR_PICKUP.value)
    yield engine
    engine.dispose()


def test_migration_renames_the_in_transit_status_and_the_downgrade_restores_it(tmp_path, monkeypatch):
    database = tmp_path / "rename.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    command.upgrade(CONFIG, "0017")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        _insert_samples(connection, "in_transit_to_korea")
        connection.execute(text("INSERT INTO sample_events (sample_id, from_status, to_status, at) VALUES "
                                "(1, 'in_sample_set', 'in_transit_to_korea', '2026-11-03'), "
                                "(1, 'in_transit_to_korea', 'discarded', '2026-11-04')"))

    def statuses():
        with engine.connect() as connection:
            return (set(connection.scalars(text("SELECT DISTINCT status FROM samples"))),
                    connection.execute(text("SELECT from_status, to_status FROM sample_events ORDER BY id")).all())

    command.upgrade(CONFIG, "0018")
    assert statuses() == ({"in_transit_to_sequencing_lab"}, [("in_sample_set", "in_transit_to_sequencing_lab"),
                                                            ("in_transit_to_sequencing_lab", "discarded")])
    command.downgrade(CONFIG, "0017")
    assert statuses() == ({"in_transit_to_korea"}, [("in_sample_set", "in_transit_to_korea"),
                                                   ("in_transit_to_korea", "discarded")])
    engine.dispose()


def test_change_status_only_moves_the_samples_still_in_the_expected_status(engine):
    with Session(engine) as session:
        samples = SQLAlchemySampleRepository(session)
        assert samples.change_status([1, 2], "ready_for_pickup", "with_transporter", NOW, actor_id=1) == 2
        # Repetido: ya no están en ready_for_pickup, no cambia ni deja otro evento.
        assert samples.change_status([1, 2, 3], "ready_for_pickup", "with_transporter", NOW) == 1
        session.commit()
        rows = session.execute(text("SELECT sample_id, from_status, to_status, actor_id FROM sample_events ORDER BY id")).all()
    assert rows == [(1, "ready_for_pickup", "with_transporter", 1), (2, "ready_for_pickup", "with_transporter", 1),
                    (3, "ready_for_pickup", "with_transporter", None)]


def test_route_keeps_the_stops_in_order_and_is_unique_per_day_and_province(engine):
    with Session(engine) as session:
        routes = SQLAlchemyRouteRepository(session)
        route_id = routes.add_route(date(2026, 11, 23), 1, None, [2, 1])
        with pytest.raises(RouteAlreadyExists):
            routes.add_route(date(2026, 11, 23), 1, None, [1])
        routes.commit()
        route = routes.route_for(date(2026, 11, 23), 1)
    assert route["id"] == route_id and route["status"] == "pending" and route["transporter_id"] is None
    assert [(stop["sequence"], stop["center_id"]) for stop in route["stops"]] == [(1, 2), (2, 1)]


def test_a_route_does_not_repeat_a_center_and_a_sample_is_picked_up_once(engine):
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO daily_routes (id, date, province_id, status, created_at) "
                                "VALUES (1, '2026-11-23', 1, 'pending', '2026-11-23')"))
        connection.execute(text("INSERT INTO route_stops (id, route_id, center_id, sequence) VALUES (1, 1, 1, 1)"))
        connection.execute(text("INSERT INTO route_pickups (stop_id, sample_id) VALUES (1, 1)"))
    for statement in ("INSERT INTO route_stops (route_id, center_id, sequence) VALUES (1, 1, 2)",
                      "INSERT INTO route_stops (route_id, center_id, sequence) VALUES (1, 2, 1)",
                      "INSERT INTO route_pickups (stop_id, sample_id) VALUES (1, 1)"):
        with engine.connect() as connection, pytest.raises(IntegrityError):
            connection.execute(text(statement))


def test_only_one_sample_set_is_assembling_at_a_time(engine):
    with Session(engine) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        first = sample_sets.open_set(False, NOW)
        with pytest.raises(AssemblingSetExists):
            sample_sets.open_set(False, NOW)
        assert sample_sets.close(first, NOW)
        second = sample_sets.open_set(False, NOW)
        sample_sets.commit()
        assert sample_sets.assembling()["id"] == second


def test_slots_go_from_1_to_10_and_a_sample_belongs_to_one_set(engine):
    with Session(engine) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        sample_set_id = sample_sets.open_set(False, NOW)
        for slot in range(1, 11):
            sample_sets.add_item(sample_set_id, slot, slot)
        with pytest.raises(SlotTaken):
            sample_sets.add_item(sample_set_id, 11, 10)
        with pytest.raises(SetFull):  # nunca hay un lote de 11
            sample_sets.add_item(sample_set_id, 11, 11)
        with pytest.raises(SampleAlreadyInSet):
            sample_sets.add_item(sample_set_id, 1, 1)
        # Los choques no deshacen lo anterior: se deshace solo el savepoint.
        sample_sets.commit()
        assert [item["slot"] for item in sample_sets.get(sample_set_id)["items"]] == list(range(1, 11))


def test_the_check_rejects_slot_11_even_without_the_repository(engine):
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO sample_sets (id, status, is_urgent, created_at, version) "
                                "VALUES (1, 'assembling', 0, '2026-11-23', 1)"))
    with engine.connect() as connection, pytest.raises(IntegrityError, match="ck_sample_set_items_slot"):
        connection.execute(text("INSERT INTO sample_set_items (sample_set_id, sample_id, slot) VALUES (1, 1, 11)"))


def test_other_integrity_errors_are_not_reported_as_a_slot_or_route_conflict(engine):
    with Session(engine) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        with pytest.raises(IntegrityError):
            sample_sets.add_item(sample_sets.open_set(False, NOW), 999, 1)  # muestra inexistente
        with pytest.raises(IntegrityError):
            SQLAlchemyRouteRepository(session).add_route(date(2026, 11, 24), 1, None, [1, 1])


def test_a_set_closed_by_another_request_is_not_closed_again_and_the_session_keeps_working(engine):
    # Como SessionLocal: sin expirar al confirmar, el lote sigue cargado con la versión vieja.
    with Session(engine, expire_on_commit=False) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        sample_set_id = sample_sets.open_set(False, NOW)
        sample_sets.commit()
        # Se retiene el modelo: así sigue en la sesión, "armándose" y con la versión 1.
        loaded = session.get(SampleSetModel, sample_set_id)
        session.commit()  # suelta el lock de SQLite sin expirar el lote cargado
        # Otro pedido cierra el lote entre la lectura y el cierre: en memoria sigue "armándose", pero el
        # UPDATE condicional de `close` (decisión 018) mira la base y no lo vuelve a cerrar.
        with engine.begin() as other:
            other.execute(text("UPDATE sample_sets SET status = 'closed', version = version + 1 WHERE id = :id"),
                          {"id": sample_set_id})
        assert loaded.status == "assembling"
        SQLAlchemySampleRepository(session).change_status([1], "ready_for_pickup", "with_transporter", NOW)
        assert not sample_sets.close(sample_set_id, NOW)
        sample_sets.commit()  # lo demás del pedido se guarda
        assert session.scalar(text("SELECT status FROM samples WHERE id = 1")) == "with_transporter"
        # El lote quedó como lo dejó el otro pedido.
        assert session.scalar(text("SELECT version FROM sample_sets WHERE id = :id"), {"id": sample_set_id}) == 2


def test_a_closed_set_does_not_take_more_samples_even_if_it_was_read_while_assembling(engine):
    with Session(engine, expire_on_commit=False) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        sample_set_id = sample_sets.open_set(False, NOW)
        sample_sets.add_item(sample_set_id, 1, 1)
        sample_sets.commit()
        assert sample_sets.assembling()["id"] == sample_set_id  # la llegada lo leyó armándose
        session.commit()
        # Otro pedido (un Pompe urgente) lo cierra antes de que la llegada sume su muestra.
        with engine.begin() as other:
            other.execute(text("UPDATE sample_sets SET status = 'closed', version = version + 1 WHERE id = :id"),
                          {"id": sample_set_id})
        with pytest.raises(SetNotAssembling):
            sample_sets.add_item(sample_set_id, 2, 2)
        with pytest.raises(SetNotAssembling):
            sample_sets.add_item(999, 2, 1)  # lote inexistente
        sample_sets.commit()
        assert [item["sample_id"] for item in sample_sets.get(sample_set_id)["items"]] == [1]


def test_close_only_closes_an_assembling_set_and_marks_it_urgent(engine):
    with Session(engine) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        sample_set_id = sample_sets.open_set(False, NOW)
        sample_sets.add_item(sample_set_id, 1, 1)
        assert sample_sets.close(sample_set_id, NOW, is_urgent=True)
        assert not sample_sets.close(sample_set_id, NOW)
        sample_sets.commit()
        closed = sample_sets.get(sample_set_id)
    assert closed["status"] == SampleSetStatus.CLOSED.value and closed["is_urgent"]
    assert closed["closed_at"] == NOW


def test_shipment_reads_the_set_and_lists_closed_ones_without_authorization(engine):
    with Session(engine) as session:
        sample_sets = SQLAlchemySampleSetRepository(session)
        authorized = sample_sets.open_set(False, NOW)
        sample_sets.add_item(authorized, 1, 1)
        sample_sets.close(authorized, NOW)
        pending = sample_sets.open_set(False, NOW)
        sample_sets.add_item(pending, 2, 1)
        sample_sets.close(pending, NOW)
        sample_sets.open_set(False, NOW)  # armándose: no cuenta
        session.execute(text("UPDATE sample_sets SET authorization_pdf_path = 'demo.pdf' WHERE id = :id"),
                        {"id": authorized})
        sample_sets.commit()
        shipments = SQLAlchemyShipmentRepository(session)
        assert shipments.closed_without_authorization() == [pending]
        assert shipments.get(pending)["sample_ids"] == [2]
        assert shipments.get(999) is None
