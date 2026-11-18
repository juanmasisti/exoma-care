import base64
from types import SimpleNamespace
import httpx
import pytest
from app.infrastructure.external_services.familiogram_client import FamiliogramClient, FamiliogramUnavailable, safe_svg, svg_pdf
from app.use_cases.familiogram import build_payload
from app.api.routes.familiogram import get_client
from test_family_api import client, setup_family, member
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"><rect x="20" y="20" width="50" height="50"/><text x="20" y="100">Paciente ficticio</text></svg>'
class FakeProvider:
    def generate(self, payload):
        assert sum(p["parentesco"] == 0 for p in payload["personas"]) == 1
        assert payload["opciones"]["reglaSospecha"] == "desactivada"
        return SVG, []
    def relationships(self):
        return [{"id": 1, "parentesco": "progenitor"}]
def test_real_pdf_conversion():
    output = svg_pdf(SVG)
    assert output.startswith(b"%PDF-") and b"%%EOF" in output and len(output) > 800
@pytest.mark.parametrize("fragment", [b'<script>alert(1)</script>', b'<foreignObject/>', b'<image href="https://evil/a"/>', b'<rect onclick="x()"/>', b'<rect fill="url(https://evil/a)"/>', b'<style>@import url(x)</style>', b'<use href="#x"/>'])
def test_reject_active_svg(fragment):
    with pytest.raises(FamiliogramUnavailable):
        safe_svg(b'<svg xmlns="http://www.w3.org/2000/svg">' + fragment + b'</svg>')
def test_provider_contract_and_invalid_base64():
    def transport(request):
        assert request.headers["x-api-key"] == "synthetic-secret"
        return httpx.Response(200, json={"imagen": {"tipo": "image/svg+xml", "base64": base64.b64encode(SVG).decode()}, "advertencias": []})
    provider = FamiliogramClient("https://example.test/family", "synthetic-secret", httpx.MockTransport(transport))
    assert provider.generate({"personas": []}) == (safe_svg(SVG), [])
    provider.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"imagen": {"tipo": "image/svg+xml", "base64": "!invalid"}, "advertencias": []}))
    with pytest.raises(FamiliogramUnavailable): provider.generate({})
def test_payload_never_converts_patient_suspicions_to_diagnoses():
    patient = {"first_name": "Ana", "last_name": "Prueba", "symptoms": [], "suspicions": [{"id": 1}]}
    family = {"members": [{**member(), "first_name": "Marta", "last_name": "Prueba", "provider_relationship": 1, "symptoms": [], "diagnoses": [{"id": 1, "name": "Confirmada"}]}]}
    payload = build_payload(patient, family, SimpleNamespace(get_pathology=lambda _: SimpleNamespace(apigen_code=None)))
    assert payload["personas"][0]["diagnosticos"] == []
    assert payload["personas"][1]["diagnosticos"] == [{"codigo": "EXOMA:1", "nombre": "Confirmada"}]
    del family["members"][0]["first_name"]
    with pytest.raises(ValueError, match="nombre, apellido"): build_payload(patient, family, None)
def test_versioned_document_download_permissions_and_stale(client):
    http, engine = client
    headers, patient, family_url = setup_family(http)
    http.app.dependency_overrides[get_client] = lambda: FakeProvider()
    url = f"/api/patients/{patient['id']}/familiogram"
    body = {"patient_version": patient["version"], "family_version": 0}
    result = http.post(url, headers=headers, json=body)
    assert result.status_code == 201, result.text
    doc = result.json()
    assert not doc["stale"]
    assert http.get(f"{url}/{doc['id']}/pdf", headers=headers).content.startswith(b"%PDF-")
    assert http.get(f"{url}/{doc['id']}/pdf").status_code == 401
    from test_patient_api import login
    assert http.get(url, headers=login(http, 3)).status_code == 403
    assert http.get(f"/api/patients/999/familiogram/{doc['id']}/pdf", headers=headers).status_code == 404
    assert http.put(family_url, headers=headers, json={"version": 0, "members": []}).status_code == 200
    assert http.get(url, headers=headers).json()[0]["stale"]
    assert http.post(url, headers=headers, json=body).status_code == 409
def test_provider_failure_preserves_saved_family(client):
    http, _ = client
    headers, patient, family_url = setup_family(http)
    assert http.put(family_url, headers=headers, json={"version": 0, "members": []}).status_code == 200
    class Failing(FakeProvider):
        def generate(self, payload): raise FamiliogramUnavailable("Servicio no disponible")
    http.app.dependency_overrides[get_client] = lambda: Failing()
    url = f"/api/patients/{patient['id']}/familiogram"
    assert http.post(url, headers=headers, json={"patient_version": 1, "family_version": 1}).status_code == 503
    assert http.get(family_url, headers=headers).json()["version"] == 1
    assert http.get(url, headers=headers).json() == []
def test_concurrent_change_during_generation_is_rejected(client):
    http, engine = client
    headers, patient, family_url = setup_family(http)
    from sqlalchemy.orm import Session
    from app.infrastructure.database.models import Paciente
    class Racing(FakeProvider):
        def generate(self, payload):
            with Session(engine) as session:
                row = session.get(Paciente, patient["id"])
                row.clinical_summary = "Cambio concurrente"
                session.commit()
            return SVG, []
    http.app.dependency_overrides[get_client] = lambda: Racing()
    url = f"/api/patients/{patient['id']}/familiogram"
    assert http.post(url, headers=headers, json={"patient_version": 1, "family_version": 0}).status_code == 409
    assert http.get(url, headers=headers).json() == []

def test_provider_css_inlined_without_external_resources():
    svg = safe_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><style>text{fill:#172b3a}.nombre{font-size:14px;font-weight:700}</style><text class="nombre">Prueba</text></svg>')
    assert b'<style' not in svg and b'font-size="14px"' in svg and b'fill="#172b3a"' in svg

def test_real_provider_hsl_palette_converts_to_pdf():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"><defs><clipPath id="mother"><circle cx="100" cy="100" r="30"/></clipPath></defs><g clip-path="url(#mother)"><rect x="70" y="70" width="60" height="60" fill="hsl(210,60%,36%)"/></g><text x="20" y="150">Fabry</text></svg>'
    output = svg_pdf(svg)
    assert output.startswith(b"%PDF-")

@pytest.mark.parametrize("relationship,code,sex", [("mother",9,"mujer"),("father",1,"mujer"),("mother",1,"hombre"),("cousin",3,"no_identificado")])
def test_inconsistent_family_relationships_rejected(relationship, code, sex):
    from app.domain.entities.family import validate_diagram_relationship
    with pytest.raises(ValueError): validate_diagram_relationship(relationship,code,sex)
