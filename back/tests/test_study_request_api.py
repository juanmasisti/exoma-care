"""Endpoints de solicitudes de estudio, pagos y cupones, con servicios en memoria."""

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from study_request_fakes import (
    FakeCoupons,
    FakeGeneCatalog,
    FakeInsurance,
    InMemoryStudyRequestRepository,
)

from app.api.catalog_dependencies import get_current_user
from app.api.study_dependencies import (
    get_coupon_service,
    get_study_payment_service,
    get_study_request_service,
)
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.main import app
from app.use_cases.coupons import CouponService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_requests import StudyRequestService

USERS = {
    "physician": AuthenticatedUser(10, "medico@demo.test", UserRole.TREATING_PHYSICIAN),
    "other_physician": AuthenticatedUser(11, "medico2@demo.test", UserRole.TREATING_PHYSICIAN),
    "admin": AuthenticatedUser(20, "admin@demo.test", UserRole.LAB_ADMINISTRATOR),
    "manager": AuthenticatedUser(30, "gerente@demo.test", UserRole.MEDICAL_MANAGER),
    "patient": AuthenticatedUser(40, "paciente@demo.test", UserRole.PATIENT),
    "other_patient": AuthenticatedUser(41, "paciente2@demo.test", UserRole.PATIENT),
    "bio": AuthenticatedUser(50, "bio@demo.test", UserRole.BIOINFORMATICIAN),
}
PDF = b"%PDF-1.4 contenido de prueba"
BASE = "/api/solicitudes-estudio"


def as_user(name):
    return {"X-Test-User": name}


@pytest.fixture
def client():
    repo = InMemoryStudyRequestRepository()
    repo.add_physician(10)
    repo.add_physician(11)
    repo.add_patient(1, "Paciente Demo", 40)
    repo.add_patient(2, "Otra Paciente", 41)
    genes, insurance, gateway = FakeGeneCatalog(), FakeInsurance(), FakeCoupons()
    requests = StudyRequestService(repo, genes)
    payments = StudyPaymentService(repo, insurance, gateway)
    coupons = CouponService(repo, gateway, "G-TEST")

    def current_user(request: Request):
        name = request.headers.get("x-test-user")
        if name is None:
            raise HTTPException(status_code=401, detail="sin sesión")
        return USERS[name]

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_study_request_service] = lambda: requests
    app.dependency_overrides[get_study_payment_service] = lambda: payments
    app.dependency_overrides[get_coupon_service] = lambda: coupons
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_study(client, codes=("FABRY",), extra=(), patient_id=1, user="physician"):
    response = client.post(
        BASE,
        json={"patient_id": patient_id, "pathology_codes": list(codes), "additional_genes": list(extra)},
        headers=as_user(user),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def budgeted(client, **kwargs):
    study_id = create_study(client, **kwargs)
    assert client.post(f"{BASE}/{study_id}/presupuesto", headers=as_user("admin")).status_code == 201
    return study_id


def test_requires_authentication(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={}).status_code == 401


def test_physician_creates_and_reads_study(client):
    study_id = create_study(client, codes=("TEST-A", "TEST-B"), extra=("EXTRA1",))
    detail = client.get(f"{BASE}/{study_id}", headers=as_user("physician")).json()
    assert detail["status"] == "creado"
    assert {g["symbol"] for g in detail["genes"]} == {"GENA1", "GENA2", "GENB1", "SHARED1", "EXTRA1"}
    assert detail["estimated_budget"]["total_cents"] == 50000


def test_create_is_restricted_to_physicians_and_validates_input(client):
    body = {"patient_id": 1, "pathology_codes": ["FABRY"]}
    for role in ("patient", "admin", "manager", "bio"):
        assert client.post(BASE, json=body, headers=as_user(role)).status_code == 403
    headers = as_user("physician")
    assert client.post(BASE, json={"patient_id": 1, "pathology_codes": []}, headers=headers).status_code == 422
    assert client.post(BASE, json={**body, "extra": 1}, headers=headers).status_code == 422
    assert client.post(BASE, json={**body, "patient_id": 99}, headers=headers).status_code == 404
    assert client.post(BASE, json={**body, "pathology_codes": ["NOPE"]}, headers=headers).status_code == 422
    assert client.post(BASE, json={**body, "additional_genes": ["NOEXISTE"]}, headers=headers).status_code == 422


def test_read_access_is_limited_to_owners_and_staff(client):
    study_id = create_study(client)
    url = f"{BASE}/{study_id}"
    for role in ("physician", "admin", "patient"):
        assert client.get(url, headers=as_user(role)).status_code == 200
    for role in ("other_physician", "other_patient"):
        assert client.get(url, headers=as_user(role)).status_code == 403
    for role in ("manager", "bio"):
        assert client.get(url, headers=as_user(role)).status_code == 403
    assert client.get(f"{BASE}/999", headers=as_user("admin")).status_code == 404


def test_catalog_and_gene_search_for_physicians_only(client):
    assert client.get(f"{BASE}/catalogo", headers=as_user("physician")).status_code == 200
    assert client.get(f"{BASE}/catalogo", headers=as_user("patient")).status_code == 403
    assert client.get(f"{BASE}/genes", params={"q": "EXTRA"}, headers=as_user("physician")).json()[:2] == ["EXTRA1", "EXTRA2"]
    assert client.get(f"{BASE}/genes", headers=as_user("physician")).status_code == 422


def test_budget_is_issued_by_administrativo_only_and_once(client):
    study_id = create_study(client)
    url = f"{BASE}/{study_id}/presupuesto"
    for role in ("physician", "patient", "manager"):
        assert client.post(url, headers=as_user(role)).status_code == 403
    assert client.get(url, headers=as_user("admin")).status_code == 404
    created = client.post(url, headers=as_user("admin"))
    assert created.status_code == 201 and created.json()["total_cents"] == 50000
    assert client.post(url, headers=as_user("admin")).status_code == 409
    assert client.get(url, headers=as_user("patient")).json()["total_cents"] == 50000
    assert client.get(url, headers=as_user("other_patient")).status_code == 403


def test_full_flow_particular_payment_with_coupon(client):
    study_id = budgeted(client)
    manager, physician, patient = as_user("manager"), as_user("physician"), as_user("patient")

    batch = client.post("/api/cupones/lote", json={"cantidad": 1, "porcentaje_descuento": 10}, headers=manager)
    assert batch.status_code == 201
    code = batch.json()[0]["code"]
    assert client.post(f"/api/cupones/{code}/asignar-medico", json={"medico_id": 10}, headers=manager).status_code == 200
    assert client.post(f"/api/cupones/{code}/asignar-paciente", json={"patient_id": 1}, headers=physician).status_code == 200
    assert [c["code"] for c in client.get("/api/cupones", headers=patient).json()] == [code]

    mode = client.post(f"{BASE}/{study_id}/modalidad-pago", json={"mode": "particular"}, headers=patient)
    assert mode.status_code == 200 and mode.json()["status"] == "pendiente_pago"
    paid = client.post(f"{BASE}/{study_id}/pago", json={"coupon_code": code}, headers=patient)
    assert paid.status_code == 200
    body = paid.json()
    assert body["status"] == "pagado"
    assert body["operations"][0]["amount_cents"] == 45000
    assert client.post(f"{BASE}/{study_id}/pago", headers=patient).status_code == 409


def test_payment_endpoints_are_patient_only(client):
    study_id = budgeted(client)
    for role in ("physician", "admin", "manager", "bio"):
        assert client.post(f"{BASE}/{study_id}/modalidad-pago", json={"mode": "particular"}, headers=as_user(role)).status_code == 403
        assert client.post(f"{BASE}/{study_id}/pago", headers=as_user(role)).status_code == 403
    assert client.post(f"{BASE}/{study_id}/modalidad-pago", json={"mode": "particular"}, headers=as_user("other_patient")).status_code == 403
    assert client.post(f"{BASE}/{study_id}/modalidad-pago", json={"mode": "trueque"}, headers=as_user("patient")).status_code == 422


def test_insurance_flow_reject_demand_authorize(client):
    study_id = budgeted(client)
    patient, admin = as_user("patient"), as_user("admin")
    assert client.get(f"{BASE}/obras-sociales", headers=patient).json()[0]["id"] == "os-1"
    assert client.get(f"{BASE}/obras-sociales", headers=as_user("physician")).status_code == 403

    response = client.post(f"{BASE}/{study_id}/modalidad-pago", json={"mode": "obra_social", "obra_social_id": "os-1"}, headers=patient)
    assert response.status_code == 200 and response.json()["status"] == "pendiente_autorizacion"
    assert "simulacion" not in response.text

    for role in ("patient", "physician", "manager"):
        assert client.post(f"{BASE}/{study_id}/cobertura/rechazar", json={"motivo": "x"}, headers=as_user(role)).status_code == 403
    assert client.post(f"{BASE}/{study_id}/cobertura/rechazar", json={"motivo": ""}, headers=admin).status_code == 422
    assert client.post(f"{BASE}/{study_id}/cobertura/rechazar", json={"motivo": "Falta orden"}, headers=admin).json()["status"] == "rechazado"

    url = f"{BASE}/{study_id}/cobertura/demanda"
    assert client.post(url, content=PDF, headers={**patient, "Content-Type": "text/plain"}).status_code == 415
    assert client.post(url, content=b"no es pdf", headers={**patient, "Content-Type": "application/pdf"}).status_code == 422
    assert client.post(url, content=b"%PDF" + b"0" * (5 * 1024 * 1024), headers={**patient, "Content-Type": "application/pdf"}).status_code == 413
    assert client.post(url, content=PDF, headers={**as_user("other_patient"), "Content-Type": "application/pdf"}).status_code == 403
    ok = client.post(url, params={"filename": "demanda.pdf"}, content=PDF, headers={**patient, "Content-Type": "application/pdf"})
    assert ok.status_code == 200 and ok.json()["coverage"]["status"] == "demanda_en_curso"

    assert client.post(f"{BASE}/{study_id}/cobertura/autorizar", headers=admin).status_code == 422  # falta porcentaje
    assert client.post(f"{BASE}/{study_id}/cobertura/autorizar", json={"porcentaje": 101}, headers=admin).status_code == 422
    done = client.post(f"{BASE}/{study_id}/cobertura/autorizar", json={"porcentaje": 60}, headers=admin)
    assert done.status_code == 200
    assert done.json()["budget"]["split"] == {"insurer_cents": 30000, "patient_cents": 20000, "estimated": False}
    assert client.post(f"{BASE}/{study_id}/pago", headers=patient).json()["status"] == "autorizado"


def test_coupon_endpoints_permissions_and_validation(client):
    manager = as_user("manager")
    assert client.post("/api/cupones/lote", json={"cantidad": 1, "porcentaje_descuento": 10}, headers=as_user("physician")).status_code == 403
    for body in ({"cantidad": 0, "porcentaje_descuento": 10}, {"cantidad": 101, "porcentaje_descuento": 10},
                 {"cantidad": 1, "porcentaje_descuento": 0}, {"cantidad": 1, "porcentaje_descuento": 101}):
        assert client.post("/api/cupones/lote", json=body, headers=manager).status_code == 422
    code = client.post("/api/cupones/lote", json={"cantidad": 1, "porcentaje_descuento": 10}, headers=manager).json()[0]["code"]
    assert client.get("/api/cupones/medicos", headers=manager).json()[0]["id"] == 10
    assert client.get("/api/cupones/medicos", headers=as_user("physician")).status_code == 403
    assert client.post(f"/api/cupones/{code}/asignar-paciente", json={"patient_id": 1}, headers=as_user("physician")).status_code == 403
    assert client.post(f"/api/cupones/{code}/asignar-medico", json={"medico_id": 10}, headers=manager).status_code == 200
    assert client.post(f"/api/cupones/{code}/asignar-medico", json={"medico_id": 11}, headers=manager).status_code == 409
    assert client.post("/api/cupones/9999/asignar-medico", json={"medico_id": 10}, headers=manager).status_code == 404
    assert client.get("/api/cupones", params={"estado": "otro"}, headers=manager).status_code == 422
    assert client.get("/api/cupones", headers=as_user("admin")).status_code == 403
