"""Documentos del turno: orden de extracción y consentimiento en PDF, y quién puede descargarlos."""
import re
import zlib

from sqlalchemy.orm import Session

from app.infrastructure.database.models import Paciente
from appointments_setup import ADMIN, DOCTOR, OTHER_PATIENT, book, client, login

MONDAY_9 = "2026-11-02T09:00:00-03:00"


def document(http, appointment_id, kind, user=None):
    headers = login(http, user) if user else login(http)
    return http.get(f"/api/appointments/{appointment_id}/documents/{kind}", headers=headers)


def pdf_text(content: bytes) -> str:
    # fpdf2 comprime cada página con zlib; Helvetica escribe el texto en latin-1.
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", content, re.S)
    return "".join(zlib.decompress(stream).decode("latin-1") for stream in streams)


def test_order_has_the_appointment_data_in_argentine_time(client):
    http, _ = client
    appointment_id = book(http, starts_at=MONDAY_9).json()["id"]
    response = document(http, appointment_id, "order")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="orden-EST-000001.pdf"'
    assert response.content.startswith(b"%PDF")
    text = pdf_text(response.content)
    center = http.get("/api/studies/1/appointment", headers=login(http)).json()["center"]
    for expected in ("EST-000001", "02/11/2026", "09:00", center["name"], center["address"], center["city"],
                     "Sofía DEMO", "45000001", "No requiere ayuno ni preparación especial."):
        assert expected in text, expected
    assert "12:00" not in text  # la hora en UTC


def test_consent_is_marked_as_provisional_and_names_the_patient(client):
    http, _ = client
    appointment_id = book(http).json()["id"]
    response = document(http, appointment_id, "consent")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="consentimiento-EST-000001.pdf"'
    text = pdf_text(response.content)
    for expected in ("PROVISORIO", "EST-000001", "Sofía DEMO", "45000001", "madre, padre o tutor"):
        assert expected in text, expected


def test_documents_of_someone_else_or_missing_are_not_found(client):
    http, _ = client
    appointment_id = book(http).json()["id"]
    for kind in ("order", "consent"):
        foreign = document(http, appointment_id, kind, OTHER_PATIENT)
        assert foreign.status_code == 404 and foreign.json()["detail"] == "El turno no existe."
        assert document(http, 999, kind).status_code == 404


def test_documents_only_for_booked_appointments(client):
    http, _ = client
    cancelled = book(http).json()["id"]
    assert http.delete(f"/api/appointments/{cancelled}", headers=login(http)).status_code == 204
    attended = book(http).json()["id"]
    assert http.patch(f"/api/appointments/{attended}/attendance", headers=login(http, ADMIN),
                      json={"attended": True}).status_code == 200
    for appointment_id in (cancelled, attended):
        response = document(http, appointment_id, "order")
        assert response.status_code == 409
        assert response.json()["detail"] == "Los documentos solo están disponibles para un turno reservado."


def test_documents_require_a_patient_session_and_a_known_kind(client):
    http, _ = client
    appointment_id = book(http).json()["id"]
    assert http.get(f"/api/appointments/{appointment_id}/documents/order").status_code == 401
    for user in (DOCTOR, ADMIN):
        assert document(http, appointment_id, "order", user).status_code == 403
    assert document(http, appointment_id, "invoice").status_code == 422


def test_a_character_helvetica_cannot_draw_does_not_break_the_pdf(client):
    http, engine = client
    with Session(engine) as session:
        session.get(Paciente, 1).apellido = "DEMO – Şahin"
        session.commit()
    appointment_id = book(http).json()["id"]
    for kind in ("order", "consent"):
        response = document(http, appointment_id, kind)
        assert response.status_code == 200
        assert "Sofía DEMO ? ?ahin" in pdf_text(response.content)
