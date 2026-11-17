"""Simulador del bot de extracción en la app (T03d): mismo caso de uso que el webhook."""
from datetime import UTC

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.extraction import get_resample_notifier
from app.infrastructure.database.logistics_models import AppointmentModel, ExtractionNoticeModel, SampleModel
from app.main import app
from appointments_setup import (  # noqa: F401
    ADMIN, AUTHORIZED, DOCTOR, NOW, PAID, SOFIA, book, client, login, study_status,
)

SECRET = "extraction-webhook-test-secret"
WEDNESDAY_10 = "2026-11-04T10:00:00-03:00"


class RecordingNotifier:
    def __init__(self):
        self.calls = []

    def avisar_remuestreo(self, study_id, sample_id, motivo):
        self.calls.append((study_id, motivo))


@pytest.fixture
def demo(client, monkeypatch):
    http, engine = client
    monkeypatch.setenv("DEMO_TOOLS_ENABLED", "true")
    monkeypatch.setenv("EXTRACTION_WEBHOOK_SECRET", SECRET)
    notifier = RecordingNotifier()
    app.dependency_overrides[get_resample_notifier] = lambda: notifier
    return http, engine, notifier


def simulate(http, code="EST-000001", volume="2.0", user=ADMIN):
    return http.post("/api/demo/extraction-notice", headers=login(http, user),
                     json={"study_code": code, "volume_ml": volume})


def webhook(http, code="EST-000001", volume="2.0"):
    return http.post("/api/webhooks/extraction", headers={"X-Webhook-Secret": SECRET},
                     json={"external_id": "bot-1", "study_code": code, "volume_ml": volume,
                           "taken_at": NOW.isoformat()})


def sample_of(engine, study_id):
    with Session(engine) as session:
        sample = session.scalars(select(SampleModel).where(SampleModel.study_id == study_id)).one()
        appointment = session.scalars(select(AppointmentModel).where(AppointmentModel.study_id == study_id)).one()
        return sample.volume_ml, sample.status, sample.is_current, appointment.status


@pytest.mark.parametrize("volume", ["2.0", "1.9"])
def test_simulated_notice_gives_the_same_result_as_the_webhook(demo, volume):
    http, engine, notifier = demo
    book(http, PAID)
    book(http, AUTHORIZED, starts_at=WEDNESDAY_10)
    by_bot = webhook(http, "EST-000001", volume)
    simulated = simulate(http, "EST-000002", volume)
    assert (by_bot.status_code, simulated.status_code) == (201, 201)
    without_id = lambda body: {key: value for key, value in body.items() if key != "sample_id"}  # noqa: E731
    assert without_id(simulated.json()) == without_id(by_bot.json())
    assert sample_of(engine, AUTHORIZED) == sample_of(engine, PAID)
    assert study_status(engine, AUTHORIZED) == study_status(engine, PAID)
    # Mismo aviso de remuestreo (solo con menos de 2 ml), cada uno para su estudio.
    motivos = {study_id: motivo for study_id, motivo in notifier.calls}
    assert motivos.get(AUTHORIZED) == motivos.get(PAID)
    assert len(notifier.calls) == (2 if volume == "1.9" else 0)
    with Session(engine) as session:
        notice = session.scalars(select(ExtractionNoticeModel).where(ExtractionNoticeModel.external_id != "bot-1")).one()
    assert notice.external_id.startswith("sim-")
    assert notice.payload["taken_at"] == NOW.astimezone(UTC).isoformat()  # la hora del reloj, como "ahora"


def test_simulated_notice_keeps_the_webhook_errors(demo):
    http, _, _ = demo
    for code in ("EST-000999", "EST-000001"):  # inexistente; existe pero sin turno
        by_bot, simulated = webhook(http, code), simulate(http, code)
        assert simulated.status_code == by_bot.status_code
        assert simulated.json() == by_bot.json()
    assert simulate(http, volume="1.999").status_code == 422


def test_waiting_studies_lists_only_booked_appointments(demo):
    http, _, _ = demo
    book(http, PAID)
    book(http, AUTHORIZED, starts_at=WEDNESDAY_10)
    assert simulate(http, "EST-000002").status_code == 201  # su turno pasa a asistido: sale de la lista
    response = http.get("/api/demo/extraction-notice/studies", headers=login(http, ADMIN))
    assert response.status_code == 200
    [study] = response.json()
    assert (study["study_id"], study["code"], study["patient_name"]) == (PAID, "EST-000001", "Sofía DEMO")
    assert study["center_name"] and study["starts_at"].startswith("2026-11-02T10:00:00")


@pytest.mark.parametrize("method, path", [("get", "/api/demo/extraction-notice/studies"),
                                          ("post", "/api/demo/extraction-notice")])
def test_only_the_lab_administrator_can_simulate(demo, method, path):
    http, _, _ = demo
    body = {"json": {"study_code": "EST-000001", "volume_ml": "2.0"}} if method == "post" else {}
    assert getattr(http, method)(path, **body).status_code == 401
    for user in (SOFIA, DOCTOR):
        assert getattr(http, method)(path, headers=login(http, user), **body).status_code == 403


@pytest.mark.parametrize("method, path", [("get", "/api/demo/extraction-notice/studies"),
                                          ("post", "/api/demo/extraction-notice")])
def test_demo_tools_off_answers_404(demo, monkeypatch, method, path):
    http, engine, _ = demo
    monkeypatch.setenv("DEMO_TOOLS_ENABLED", "false")
    book(http, PAID)
    body = {"json": {"study_code": "EST-000001", "volume_ml": "2.0"}} if method == "post" else {}
    assert getattr(http, method)(path, **body).status_code == 404  # sin sesión: no revela que existe
    assert getattr(http, method)(path, headers=login(http, ADMIN), **body).status_code == 404
    assert study_status(engine, PAID) == "turno_sacado"
