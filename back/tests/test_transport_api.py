"""Orden del día y transportista (T04), con las muestras DEMO del seeder y un doble de la API de recorridos."""
import json
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.sample_sets import get_sample_set_assigner
from app.api.routes.transport import get_route_optimizer
from app.config import get_settings
from app.domain.interfaces.route_optimizer import RouteOptimizerError
from app.infrastructure.adapters.route_optimizer_client import RouteOptimizerClient
from app.infrastructure.database.logistics_models import (
    DailyRouteModel, ExtractionCenterModel, ProvinceModel, RoutePickupModel, SampleEventModel, SampleModel,
)
from app.infrastructure.repositories.sqlalchemy_route_repository import SQLAlchemyRouteRepository
from app.main import app
from appointments_setup import ADMIN, NOW, SOFIA, client, login  # noqa: F401
from seeders.logistics import seed_demo_logistics_samples

MONDAY = "2026-11-02"
SATURDAY = "2026-11-07"
HOLIDAY = "2026-12-08"  # martes, Inmaculada Concepción


class FakeOptimizer:
    """Doble del Protocol RouteOptimizer: anota cada llamada y responde con `answer`."""

    def __init__(self):
        self.calls = []
        # Invierte los centros del medio, para ver que se guarda el orden de la API y no el de la base.
        self.answer = lambda points: [points[0], *reversed(points[1:-1]), points[-1]]

    def order(self, points):
        self.calls.append(points)
        return self.answer(points)


class FakeAssigner:
    """Doble del enganche de T05: anota cada muestra recibida; con `fail`, falla como un error inesperado."""

    def __init__(self):
        self.sample_ids = []
        self.fail = False

    def asignar_a_sample_set(self, sample_id, now):
        if self.fail:
            raise RuntimeError("Falla inesperada del armado de lotes.")
        self.sample_ids.append(sample_id)


@pytest.fixture
def transport(client):
    http, engine = client
    # 5 listas para retirar: 4 en La Plata 1, 1, 2 y 3 (Buenos Aires) y 1 en Córdoba 1.
    seed_demo_logistics_samples(sessionmaker(engine), now=NOW)
    optimizer = FakeOptimizer()
    app.dependency_overrides[get_route_optimizer] = lambda: optimizer
    return http, engine, optimizer


@pytest.fixture
def assigner(transport):
    fake = FakeAssigner()
    app.dependency_overrides[get_sample_set_assigner] = lambda: fake
    return fake


def generate(http, day=MONDAY, user=ADMIN):
    return http.post("/api/transport/daily-routes", json={"date": day}, headers=login(http, user))


def center_id(engine, city, number):
    with Session(engine) as session:
        return session.scalar(select(ExtractionCenterModel.id)
                              .where(ExtractionCenterModel.name == f"Centro de extracción DEMO {city} {number}"))


def province_id(engine, name):
    with Session(engine) as session:
        return session.scalar(select(ProvinceModel.id).where(ProvinceModel.name == name))


def route_count(engine):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(DailyRouteModel))


def stop_centers(engine, province, day=MONDAY):
    with Session(engine) as session:
        route = SQLAlchemyRouteRepository(session).route_for(date.fromisoformat(day), province_id(engine, province))
        return [stop["center_id"] for stop in route["stops"]]


def la_plata(engine, *numbers):
    return [center_id(engine, "La Plata", number) for number in numbers]


def test_generates_one_route_per_province_in_the_order_returned_by_the_api(transport):
    http, engine, optimizer = transport
    response = generate(http)
    assert response.status_code == 201
    assert [(r["province"], r["stops"], r["picked_up"], r["status"]) for r in response.json()] == [
        ("Buenos Aires", 3, 0, "pending"), ("Córdoba", 1, 0, "pending")]
    assert stop_centers(engine, "Buenos Aires") == la_plata(engine, 3, 2, 1)
    # Córdoba tiene un solo centro: no hace falta la API. La de Buenos Aires sale y vuelve al laboratorio.
    settings = get_settings()
    lab = (settings.central_lab_latitude, settings.central_lab_longitude)
    (sent,) = optimizer.calls
    assert sent[0] == sent[-1] == lab and len(sent) == 5


def test_generating_twice_leaves_one_route_per_province(transport):
    http, engine, optimizer = transport
    first = generate(http).json()
    second = generate(http)
    assert second.status_code == 200
    assert second.json() == first
    assert route_count(engine) == 2 and len(optimizer.calls) == 1


def test_only_the_missing_provinces_are_generated_and_the_existing_ones_are_not_touched(transport):
    http, engine, optimizer = transport
    with Session(engine) as session:
        routes = SQLAlchemyRouteRepository(session)
        routes.add_route(date(2026, 11, 2), province_id(engine, "Buenos Aires"), None, la_plata(engine, 1))
        routes.commit()
    response = generate(http)
    assert response.status_code == 201
    assert [(r["province"], r["stops"]) for r in response.json()] == [("Buenos Aires", 1), ("Córdoba", 1)]
    assert optimizer.calls == []


def test_an_inactive_center_is_left_out_of_the_route(transport):
    http, engine, _optimizer = transport
    with Session(engine) as session:
        session.get(ExtractionCenterModel, center_id(engine, "La Plata", 2)).active = False
        session.commit()
    assert generate(http).status_code == 201
    assert stop_centers(engine, "Buenos Aires") == la_plata(engine, 3, 1)


@pytest.mark.parametrize("day, reason", [(SATURDAY, "es fin de semana"),
                                         (HOLIDAY, "es feriado (Inmaculada Concepción de María)")])
def test_weekends_and_holidays_have_no_route(transport, day, reason):
    http, engine, _optimizer = transport
    response = generate(http, day)
    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert route_count(engine) == 0


def api_down(_points):
    raise RouteOptimizerError("El módulo de recorridos tardó demasiado en responder.")


@pytest.mark.parametrize("answer", [
    api_down,
    lambda points: [points[0], (0.0, 0.0), *points[2:]],  # un punto que no es de ningún centro
    lambda points: points[:-1],  # sin el destino
])
def test_route_api_failure_is_a_502_without_any_route(transport, answer):
    http, engine, optimizer = transport
    optimizer.answer = answer
    response = generate(http)
    assert response.status_code == 502
    assert response.json()["detail"]
    assert route_count(engine) == 0  # tampoco la de Córdoba, que no necesitaba la API


def test_lists_the_routes_of_the_day(transport):
    http, _engine, _optimizer = transport
    generate(http)
    response = http.get("/api/transport/daily-routes", params={"date": MONDAY}, headers=login(http, ADMIN))
    assert response.status_code == 200
    assert [r["province"] for r in response.json()] == ["Buenos Aires", "Córdoba"]
    other_day = http.get("/api/transport/daily-routes", params={"date": "2026-11-03"}, headers=login(http, ADMIN))
    assert other_day.json() == []


def test_only_the_lab_administrator_generates_and_lists(transport):
    http, engine, _optimizer = transport
    assert http.post("/api/transport/daily-routes", json={"date": MONDAY}).status_code == 401
    assert generate(http, user=SOFIA).status_code == 403
    assert http.get("/api/transport/daily-routes", params={"date": MONDAY},
                    headers=login(http, SOFIA)).status_code == 403
    assert route_count(engine) == 0


# Recorrido del transportista: retiro por parada y llegada al laboratorio central.

def my_route(http, engine, province="Buenos Aires", day=MONDAY, user=ADMIN):
    return http.get("/api/transport/my-route", params={"date": day, "province_id": province_id(engine, province)},
                    headers=login(http, user))


def pick_up(http, route, index, user=ADMIN):
    stop_id = route["stops"][index]["id"]
    return http.post(f"/api/transport/daily-routes/{route['id']}/stops/{stop_id}/pickup", headers=login(http, user))


def arrive(http, route, user=ADMIN):
    return http.post(f"/api/transport/daily-routes/{route['id']}/arrival", headers=login(http, user))


def statuses(engine):
    with Session(engine) as session:
        return dict(session.execute(select(SampleModel.status, func.count()).group_by(SampleModel.status)).all())


def ready_route(http, engine):
    generate(http)
    return my_route(http, engine).json()


def test_my_route_shows_the_fixed_order_the_centers_and_their_codes(transport):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    assert route["province"] == "Buenos Aires" and route["status"] == "pending"
    assert [stop["center"]["id"] for stop in route["stops"]] == la_plata(engine, 3, 2, 1)
    assert [len(stop["sample_codes"]) for stop in route["stops"]] == [1, 1, 2]
    assert all(code.startswith("EST-") for stop in route["stops"] for code in stop["sample_codes"])
    assert route["next_stop_id"] == route["stops"][0]["id"]
    assert route["on_board"] == []


def test_my_route_is_404_without_a_route(transport):
    http, engine, _optimizer = transport
    assert my_route(http, engine).status_code == 404
    generate(http)
    assert my_route(http, engine, "Mendoza").status_code == 404
    assert my_route(http, engine, day="2026-11-03").status_code == 404


def test_pickup_follows_the_fixed_order_and_is_not_repeated(transport):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    skipped = pick_up(http, route, 1)
    assert skipped.status_code == 409
    assert "primero hay que retirar la parada 1" in skipped.json()["detail"]
    receipt = pick_up(http, route, 0)
    assert receipt.status_code == 200
    assert receipt.json()["center"]["id"] == la_plata(engine, 3)[0]
    assert receipt.json()["sample_codes"] == route["stops"][0]["sample_codes"]
    repeated = pick_up(http, route, 0)
    assert repeated.status_code == 409 and repeated.json()["detail"] == "Este centro ya fue retirado."
    assert statuses(engine)["with_transporter"] == 1
    after = my_route(http, engine).json()
    assert after["next_stop_id"] == route["stops"][1]["id"]
    assert after["on_board"] == route["stops"][0]["sample_codes"]
    # En hora de Argentina, igual que el comprobante (el reloj de la prueba).
    assert after["stops"][0]["picked_up_at"] == receipt.json()["picked_up_at"] == "2026-11-01T10:00:00-03:00"


def test_pickup_saves_each_sample_and_signs_the_events(transport):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    pick_up(http, route, 0)
    pick_up(http, route, 1)
    pick_up(http, route, 2)
    with Session(engine) as session:
        picked = session.scalars(select(RoutePickupModel.sample_id)).all()
        events = session.scalars(select(SampleEventModel).where(SampleEventModel.sample_id.in_(picked),
                                                                SampleEventModel.to_status == "with_transporter")).all()
    assert len(picked) == 4
    assert len(events) == 4 and {event.actor_id for event in events} == {ADMIN}


def test_pickup_of_a_stop_of_another_route_is_404(transport):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    cordoba = my_route(http, engine, "Córdoba").json()
    other_stop = cordoba["stops"][0]["id"]
    response = http.post(f"/api/transport/daily-routes/{route['id']}/stops/{other_stop}/pickup",
                         headers=login(http, ADMIN))
    assert response.status_code == 404
    assert http.post("/api/transport/daily-routes/999/arrival", headers=login(http, ADMIN)).status_code == 404


def test_arrival_needs_every_stop_picked_up(transport, assigner):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    pick_up(http, route, 0)
    response = arrive(http, route)
    assert response.status_code == 409
    assert "faltan retirar 2 centros" in response.json()["detail"]
    assert assigner.sample_ids == []


def test_arrival_receives_exactly_the_picked_samples_and_calls_the_assigner_for_each(transport, assigner):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    for index in range(3):
        pick_up(http, route, index)
    before = statuses(engine)
    response = arrive(http, route)
    assert response.status_code == 200
    picked_codes = [code for stop in route["stops"] for code in stop["sample_codes"]]
    assert response.json()["received_codes"] == picked_codes
    with Session(engine) as session:
        picked = session.scalars(select(RoutePickupModel.sample_id).order_by(RoutePickupModel.sample_id)).all()
    assert sorted(assigner.sample_ids) == list(picked)
    after = statuses(engine)
    # Las 2 recibidas DEMO siguen igual y la de Córdoba sigue lista para retirar.
    assert after["received"] == before["received"] + 4 == 6
    assert after["ready_for_pickup"] == 1 and "with_transporter" not in after
    done = my_route(http, engine).json()
    assert done["status"] == "arrived" and done["on_board"] == [] and done["next_stop_id"] is None
    repeated = arrive(http, route)
    assert repeated.status_code == 409 and repeated.json()["detail"] == "La llegada de esta orden ya fue registrada."
    assert len(assigner.sample_ids) == 4


def test_an_unexpected_assigner_error_undoes_the_whole_arrival(transport, assigner):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    for index in range(3):
        pick_up(http, route, index)
    assigner.fail = True
    with pytest.raises(RuntimeError, match="armado de lotes"):
        arrive(http, route)
    assert statuses(engine)["with_transporter"] == 4
    assert my_route(http, engine).json()["status"] == "pending"


def test_only_transport_roles_see_and_operate_the_route(transport):
    http, engine, _optimizer = transport
    route = ready_route(http, engine)
    assert my_route(http, engine, user=SOFIA).status_code == 403
    assert pick_up(http, route, 0, user=SOFIA).status_code == 403
    assert arrive(http, route, user=SOFIA).status_code == 403
    assert http.post(f"/api/transport/daily-routes/{route['id']}/arrival").status_code == 401
    assert statuses(engine)["ready_for_pickup"] == 5


# Adaptador HTTP del módulo de recorridos, con un transporte falso de httpx: no sale a internet.

def client_with(handler):
    return RouteOptimizerClient("https://recorridos.test/api/optimizacion", transport=httpx.MockTransport(handler))


def test_client_sends_contract_body_and_reads_answer():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"coordenadas": [{"lat": 1, "lon": 2}, {"lat": "3.5", "lon": 4}]})
    assert client_with(handler).order([(1.0, 2.0), (3.5, 4.0)]) == [(1.0, 2.0), (3.5, 4.0)]
    assert seen["body"] == {"coordenadas": [{"lat": 1.0, "lon": 2.0}, {"lat": 3.5, "lon": 4.0}]}


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(500, text="error"),
    lambda request: httpx.Response(200, text="no es json"),
    lambda request: httpx.Response(200, json={"otra": []}),
])
def test_client_translates_bad_answers(handler):
    with pytest.raises(RouteOptimizerError, match="no respondió correctamente"):
        client_with(handler).order([(1.0, 2.0)])


def test_client_translates_timeout():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)
    with pytest.raises(RouteOptimizerError, match="tardó demasiado"):
        client_with(handler).order([(1.0, 2.0)])
