"""Consultas del paciente: turno del estudio, mis turnos, estudios elegibles y sesión."""
from appointments_setup import (ADMIN, AUTHORIZED, DOCTOR, MONDAY_10, OTHER_PATIENT, OTHERS_STUDY, PAID, UNLINKED_PATIENT, book,
                                client, login)


def test_study_appointment_for_its_owner_only(client):
    http, _ = client
    book(http)
    response = http.get(f"/api/studies/{PAID}/appointment", headers=login(http))
    assert response.status_code == 200
    body = response.json()
    assert body["starts_at"] == MONDAY_10
    assert set(body["center"]) == {"id", "name", "address", "city", "phone"}
    foreign = http.get(f"/api/studies/{PAID}/appointment", headers=login(http, OTHER_PATIENT))
    assert foreign.status_code == 404 and foreign.json()["detail"] == "El estudio no existe o no es tuyo."
    without = http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http))
    assert without.status_code == 404 and without.json()["detail"] == "El estudio no tiene un turno vigente."


def test_endpoints_require_a_session(client):
    http, _ = client
    assert http.post("/api/appointments", json={}).status_code == 401
    assert http.delete("/api/appointments/1").status_code == 401
    assert http.get("/api/studies/1/appointment").status_code == 401
    assert http.patch("/api/appointments/1/attendance", json={"attended": True}).status_code == 401


def test_my_appointments_lists_only_my_booked_ones_in_order(client):
    http, _ = client
    later = book(http, PAID, starts_at="2026-11-03T10:00:00-03:00").json()["id"]
    earlier = book(http, AUTHORIZED).json()["id"]
    book(http, OTHERS_STUDY, starts_at="2026-11-02T11:00:00-03:00", user=OTHER_PATIENT)
    mine = http.get("/api/appointments/mine", headers=login(http)).json()
    assert [a["id"] for a in mine] == [earlier, later]
    assert mine[0]["study_code"] == "EST-000002" and mine[0]["starts_at"] == MONDAY_10
    assert set(mine[0]["center"]) == {"id", "name", "address", "city", "phone"}
    http.delete(f"/api/appointments/{earlier}", headers=login(http))
    assert [a["id"] for a in http.get("/api/appointments/mine", headers=login(http)).json()] == [later]
    assert http.get("/api/appointments/mine", headers=login(http, UNLINKED_PATIENT)).json() == []


def test_eligible_studies_are_paid_or_authorized_without_booking(client):
    http, _ = client
    eligible = lambda: http.get("/api/appointments/eligible-studies", headers=login(http)).json()
    assert eligible() == [{"id": PAID, "code": "EST-000001", "status": "pagado"},
                          {"id": AUTHORIZED, "code": "EST-000002", "status": "autorizado"}]
    appointment_id = book(http, PAID).json()["id"]
    assert [s["id"] for s in eligible()] == [AUTHORIZED]
    http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert [s["id"] for s in eligible()] == [PAID, AUTHORIZED]
    other = http.get("/api/appointments/eligible-studies", headers=login(http, OTHER_PATIENT)).json()
    assert [s["id"] for s in other] == [OTHERS_STUDY]


def test_my_appointments_and_eligible_studies_are_for_patients_only(client):
    http, _ = client
    for path in ("/api/appointments/mine", "/api/appointments/eligible-studies"):
        assert http.get(path).status_code == 401
        for user in (DOCTOR, ADMIN):
            assert http.get(path, headers=login(http, user)).status_code == 403
