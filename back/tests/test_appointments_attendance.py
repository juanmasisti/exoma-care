"""Registrar la asistencia de un turno."""
from appointments_setup import ADMIN, AUTHORIZED, DOCTOR, PAID, SOFIA, book, client, login


def test_attendance_and_absence_counter(client):
    http, _ = client
    first = book(http, PAID).json()["id"]
    second = book(http, AUTHORIZED, starts_at="2026-11-02T11:00:00-03:00").json()["id"]
    admin = login(http, ADMIN)
    attended = http.patch(f"/api/appointments/{first}/attendance", headers=admin, json={"attended": True})
    assert attended.status_code == 200
    assert attended.json() == {"id": first, "status": "attended", "patient_absences": 0}
    absent = http.patch(f"/api/appointments/{second}/attendance", headers=admin, json={"attended": False})
    assert absent.json() == {"id": second, "status": "absent", "patient_absences": 1}


def test_attendance_rules(client):
    http, _ = client
    booked = book(http, PAID).json()["id"]
    cancelled = book(http, AUTHORIZED, starts_at="2026-11-02T11:00:00-03:00").json()["id"]
    http.delete(f"/api/appointments/{cancelled}", headers=login(http))
    for user in (SOFIA, DOCTOR):
        response = http.patch(f"/api/appointments/{booked}/attendance", headers=login(http, user),
                              json={"attended": True})
        assert response.status_code == 403
    admin = login(http, ADMIN)
    assert http.patch("/api/appointments/999/attendance", headers=admin, json={"attended": True}).status_code == 404
    assert http.patch(f"/api/appointments/{booked}/attendance", headers=admin, json={"attended": True}).status_code == 200
    for identifier in (booked, cancelled):
        response = http.patch(f"/api/appointments/{identifier}/attendance", headers=admin, json={"attended": False})
        assert response.status_code == 409
        assert response.json()["detail"] == "Solo se registra la asistencia de un turno reservado."
