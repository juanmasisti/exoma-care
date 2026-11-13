"""Aviso de extracción del bot, remuestreo y seguimiento del estudio (T03)."""
import logging
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.extraction import get_resample_notifier
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import (
    AppointmentModel, ExtractionNoticeModel, SampleEventModel, SampleModel,
)
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.main import app
from app.use_cases.extraction import Conflict, ExtractionService, NotFound
from app.use_cases.studies import StudyService
from appointments_setup import (
    ADMIN, AUTHORIZED, DOCTOR, OTHER_PATIENT, PAID, SOFIA, book, client, login, study_status,  # noqa: F401
)

SECRET = "extraction-webhook-test-secret"
HEADERS = {"X-Webhook-Secret": SECRET}
TAKEN_AT = "2026-11-02T10:05:00-03:00"
LATER = datetime(2026, 11, 3, 9, tzinfo=TIMEZONE)


class RecordingNotifier:
    def __init__(self):
        self.calls = []

    def avisar_remuestreo(self, study_id, motivo):
        self.calls.append((study_id, motivo))


@pytest.fixture
def extraction(client, monkeypatch):
    http, engine = client
    monkeypatch.setenv("EXTRACTION_WEBHOOK_SECRET", SECRET)
    notifier = RecordingNotifier()
    app.dependency_overrides[get_resample_notifier] = lambda: notifier
    return http, engine, notifier


def notice(http, volume="2.0", external_id="bot-1", code="EST-000001", headers=HEADERS):
    return http.post("/api/webhooks/extraction", headers=headers,
                     json={"external_id": external_id, "study_code": code, "volume_ml": volume, "taken_at": TAKEN_AT})


def rows(engine, model):
    with Session(engine) as session:
        return session.scalars(select(model).order_by(model.id)).all()


def count(engine, model):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def service(session, notifier):
    return ExtractionService(SQLAlchemySampleRepository(session), SQLAlchemyAppointmentRepository(session),
                             StudyService(SQLAlchemyStudyRepository(session)), notifier)


def test_2_ml_leaves_the_sample_ready_and_the_appointment_attended(extraction):
    http, engine, notifier = extraction
    appointment_id = book(http).json()["id"]
    response = notice(http, "2.0")
    assert response.status_code == 201
    [sample] = rows(engine, SampleModel)
    assert response.json() == {"sample_id": sample.id, "sample_status": "ready_for_pickup",
                               "study_status": "listo_para_retirar"}
    assert (sample.study_id, sample.appointment_id, sample.volume_ml, sample.is_current) == (
        PAID, appointment_id, Decimal("2.00"), True)
    [event] = rows(engine, SampleEventModel)
    assert (event.from_status, event.to_status, event.actor_id) == (None, "ready_for_pickup", None)
    assert study_status(engine, PAID) == "listo_para_retirar"
    assert rows(engine, AppointmentModel)[0].status == "attended"
    assert notifier.calls == []
    # El turno ya se cerró: el paciente no puede cancelarlo después de la extracción.
    assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http)).status_code == 409


def test_1_9_ml_is_born_discarded_and_requires_resample(extraction):
    http, engine, notifier = extraction
    book(http)
    response = notice(http, "1.9")
    assert response.status_code == 201
    assert response.json()["sample_status"] == "discarded"
    assert response.json()["study_status"] == "requiere_remuestreo"
    [sample] = rows(engine, SampleModel)
    assert (sample.status, sample.is_current) == ("discarded", False)
    [event] = rows(engine, SampleEventModel)
    assert (event.from_status, event.to_status) == (None, "discarded")  # nace descartada, no es una transición
    assert study_status(engine, PAID) == "requiere_remuestreo"
    assert notifier.calls == [(PAID, "Volumen insuficiente: 1.9 ml (mínimo 2 ml).")]


def test_repeated_notice_returns_the_same_result_without_duplicating(extraction, caplog):
    http, engine, notifier = extraction
    book(http)
    first = notice(http, "1.9")
    again = notice(http, "1.9")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    with caplog.at_level(logging.WARNING, logger="app.use_cases.extraction"):
        assert notice(http, "1.90").status_code == 200  # mismo volumen con otro formato: no es otro contenido
        assert caplog.text == ""
        different = notice(http, "3.0")
    assert (different.status_code, different.json()) == (200, first.json())
    assert "bot-1 repetido con otro contenido" in caplog.text
    counts = count(engine, ExtractionNoticeModel), count(engine, SampleModel), count(engine, SampleEventModel)
    assert counts == (1, 1, 1)
    assert len(notifier.calls) == 1


def test_webhook_requires_the_shared_secret(extraction, monkeypatch):
    http, engine, _ = extraction
    book(http)
    for headers in ({}, {"X-Webhook-Secret": "wrong"}, login(http)):  # un token de usuario no alcanza
        response = notice(http, headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Aviso de extracción no autorizado."
    # Sin secreto el cuerpo no se valida: 401 y no 422.
    assert http.post("/api/webhooks/extraction", json={}).status_code == 401
    monkeypatch.setenv("EXTRACTION_WEBHOOK_SECRET", "")
    assert notice(http, headers={"X-Webhook-Secret": ""}).status_code == 401
    assert count(engine, ExtractionNoticeModel) == 0
    assert study_status(engine, PAID) == "turno_sacado"


@pytest.mark.parametrize("volume", ["NaN", "Infinity", "-Infinity", 0, "-1", "1.999", "1000", True, "abc"])
def test_invalid_volume_is_rejected(extraction, volume):
    http, engine, _ = extraction
    book(http)
    assert notice(http, volume).status_code == 422
    assert count(engine, ExtractionNoticeModel) == 0


def test_taken_at_without_timezone_is_rejected(extraction):
    http, engine, _ = extraction
    book(http)
    response = http.post("/api/webhooks/extraction", headers=HEADERS, json={
        "external_id": "bot-1", "study_code": "EST-000001", "volume_ml": "2.0", "taken_at": "2026-11-02T10:05:00"})
    assert response.status_code == 422
    assert count(engine, ExtractionNoticeModel) == 0


def test_notifier_failure_does_not_undo_the_notice(extraction, caplog):
    http, engine, _ = extraction

    class FailingNotifier:
        def avisar_remuestreo(self, study_id, motivo):
            raise RuntimeError("avisos caído")

    app.dependency_overrides[get_resample_notifier] = FailingNotifier
    book(http)
    with caplog.at_level(logging.ERROR, logger="app.use_cases.extraction"):
        assert notice(http, "1.9").status_code == 201
    assert "No se pudo avisar el remuestreo del estudio 1." in caplog.text
    assert study_status(engine, PAID) == "requiere_remuestreo"
    assert count(engine, SampleModel) == 1


def test_notice_rules(extraction):
    http, engine, _ = extraction
    assert notice(http, code="EST-000999").status_code == 404
    assert notice(http, code="EST-1").status_code == 404
    # Pagado pero sin turno: no espera una extracción.
    response = notice(http)
    assert (response.status_code, response.json()["detail"]) == (409, "El estudio no está esperando una extracción.")
    appointment_id = book(http).json()["id"]
    http.patch(f"/api/appointments/{appointment_id}/attendance", headers=login(http, ADMIN), json={"attended": False})
    response = notice(http)
    assert response.status_code == 409
    assert response.json()["detail"] == "El estudio no tiene un turno reservado o asistido para esta extracción."
    # Un aviso rechazado no queda guardado: el bot puede reintentar con el mismo id.
    assert count(engine, ExtractionNoticeModel) == 0
    assert study_status(engine, PAID) == "turno_sacado"


def test_notice_uses_an_appointment_already_marked_attended(extraction):
    http, engine, _ = extraction
    appointment_id = book(http).json()["id"]
    http.patch(f"/api/appointments/{appointment_id}/attendance", headers=login(http, ADMIN), json={"attended": True})
    assert notice(http).status_code == 201
    assert rows(engine, SampleModel)[0].appointment_id == appointment_id


def test_resample_keeps_the_same_study_and_history(extraction):
    http, engine, _ = extraction
    book(http)
    notice(http, "1.9", external_id="bot-1")
    studies = count(engine, StudyModel)
    rebooked = book(http, starts_at="2026-11-04T10:00:00-03:00")
    assert rebooked.status_code == 201
    assert study_status(engine, PAID) == "turno_sacado"
    assert notice(http, "2.5", external_id="bot-2").status_code == 201
    first, second = rows(engine, SampleModel)
    assert (first.status, first.is_current) == ("discarded", False)
    assert (second.status, second.is_current) == ("ready_for_pickup", True)
    assert second.appointment_id == rebooked.json()["id"]
    assert count(engine, StudyModel) == studies  # mismo estudio: no se crea otro ni se vuelve a pagar
    assert study_status(engine, PAID) == "listo_para_retirar"


def test_solicitar_remuestreo_discards_the_current_sample(extraction):
    http, engine, _ = extraction
    book(http)
    notice(http, "2.5")
    notifier = RecordingNotifier()
    with Session(engine) as session:
        service(session, notifier).solicitar_remuestreo(PAID, "ADN insuficiente", LATER, actor_id=ADMIN)
    [sample] = rows(engine, SampleModel)
    assert (sample.status, sample.is_current) == ("discarded", False)
    discard = rows(engine, SampleEventModel)[-1]
    assert (discard.from_status, discard.to_status, discard.reason, discard.actor_id) == (
        "ready_for_pickup", "discarded", "ADN insuficiente", ADMIN)
    assert study_status(engine, PAID) == "requiere_remuestreo"
    assert notifier.calls == [(PAID, "ADN insuficiente")]
    # El estudio queda habilitado para sacar un turno nuevo.
    assert book(http, starts_at="2026-11-04T10:00:00-03:00").status_code == 201


def test_solicitar_remuestreo_rules(extraction):
    http, engine, _ = extraction
    notifier = RecordingNotifier()
    with Session(engine) as session:
        with pytest.raises(NotFound):
            service(session, notifier).solicitar_remuestreo(PAID, "ADN insuficiente", LATER)
        with pytest.raises(ValueError):
            service(session, notifier).solicitar_remuestreo(PAID, "  ", LATER)
    book(http)
    notice(http, "2.5")
    with Session(engine) as session:
        session.execute(SampleModel.__table__.update().values(status="with_transporter"))
        session.commit()
        with pytest.raises(Conflict, match="with_transporter"):
            service(session, notifier).solicitar_remuestreo(PAID, "ADN insuficiente", LATER)
    assert study_status(engine, PAID) == "listo_para_retirar"
    assert notifier.calls == []


def test_tracking_shows_the_samples_and_the_resample(extraction):
    http, engine, _ = extraction
    book(http)
    notice(http, "1.9")
    response = http.get(f"/api/studies/{PAID}/tracking", headers=login(http))
    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in ("study_id", "code", "status", "requires_new_extraction")} == {
        "study_id": PAID, "code": "EST-000001", "status": "requiere_remuestreo", "requires_new_extraction": True}
    [sample] = body["samples"]
    assert (sample["volume_ml"], sample["status"], sample["is_current"]) == ("1.90", "discarded", False)
    assert sample["events"] == [{"from_status": None, "to_status": "discarded", "reason": None,
                                 "at": "2026-11-02T10:05:00-03:00"}]
    without_samples = http.get(f"/api/studies/{AUTHORIZED}/tracking", headers=login(http)).json()
    assert (without_samples["requires_new_extraction"], without_samples["samples"]) == (False, [])


def test_tracking_permissions(extraction):
    http, _, _ = extraction
    assert http.get(f"/api/studies/{PAID}/tracking").status_code == 401
    assert http.get(f"/api/studies/{PAID}/tracking", headers=login(http, DOCTOR)).status_code == 403
    for study_id in (PAID, 999):
        assert http.get(f"/api/studies/{study_id}/tracking", headers=login(http, OTHER_PATIENT)).status_code == 404
    assert http.get(f"/api/studies/{PAID}/tracking", headers=login(http, SOFIA)).status_code == 200
