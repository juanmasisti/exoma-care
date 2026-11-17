"""Clientes HTTP de cupones y obras sociales, con transporte simulado (sin red)."""

import asyncio
import json
from datetime import date

import httpx
import pytest

from app.infrastructure.external_services.cupones_client import CuponesClient
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.obras_sociales_client import ObrasSocialesClient

CUPONES = "https://cupones.test/api"
OBRAS = "https://obras.test/api"


def run(coro):
    return asyncio.run(coro)


def cupones(handler):
    return CuponesClient("clave-de-prueba", CUPONES, transport=httpx.MockTransport(handler))


def obras(handler):
    return ObrasSocialesClient("clave-de-prueba", OBRAS, transport=httpx.MockTransport(handler))


# ---------- Cupones ----------


def test_generar_lote_sends_key_header_and_payload():
    seen = {}

    def handler(request):
        seen.update(path=request.url.path, key=request.headers["X-API-Key"], body=json.loads(request.content))
        return httpx.Response(200, json=[{"codigo_cupon": "1234", "porcentaje": 15}])

    result = run(cupones(handler).generar_lote("G-1", 1, 15))
    assert result == [{"codigo_cupon": "1234", "porcentaje": 15}]
    assert seen == {
        "path": "/api/generar_cupones_gerencia",
        "key": "clave-de-prueba",
        "body": {"p_gerente_id": "G-1", "p_cantidad": 1, "p_porcentaje_descuento": 15},
    }


def test_assign_and_redeem_payloads():
    bodies = []

    def handler(request):
        bodies.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True})

    client = cupones(handler)
    run(client.asignar_a_medico("G-1", "M-2", "111"))
    run(client.asignar_a_paciente("M-2", "P-3", "111"))
    run(client.canjear("P-3", "111"))
    assert bodies == [
        ("/api/asignar_cupon_a_medico", {"p_gerente_id": "G-1", "p_medico_id": "M-2", "p_codigo": "111"}),
        ("/api/asignar_cupon_a_paciente", {"p_medico_id": "M-2", "p_paciente_id": "P-3", "p_codigo": "111"}),
        ("/api/canjear_cupon", {"p_paciente_id": "P-3", "p_codigo": "111"}),
    ]


@pytest.mark.parametrize("status,expected", [(400, 400), (403, 403), (404, 404), (409, 409), (503, 503), (401, 502), (415, 502), (500, 502)])
def test_error_status_mapping_and_no_write_retry(status, expected):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, json={"code": "x", "message": "Cupón inválido"})

    with pytest.raises(ExternalServiceError) as error:
        run(cupones(handler).canjear("P-1", "111"))
    assert error.value.status_code == expected
    assert len(calls) == 1
    if status in (400, 403, 404, 409):
        assert "Cupón inválido" in str(error.value)


def test_network_failure_is_reported_as_503_without_retry():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(ExternalServiceError) as error:
        run(cupones(handler).canjear("P-1", "111"))
    assert error.value.status_code == 503
    assert len(calls) == 1


def test_invalid_batch_shape_is_rejected():
    with pytest.raises(ExternalServiceError):
        run(cupones(lambda r: httpx.Response(200, json={"no": "lista"})).generar_lote("G", 1, 10))


def test_listar_validates_limit_and_passes_filters():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"items": [], "total": 0, "limit": 100, "offset": 0})

    client = cupones(handler)
    run(client.listar(estado="usado", medico_id="M-1"))
    assert seen["estado"] == "usado" and seen["medico_id"] == "M-1"
    with pytest.raises(ValueError):
        run(client.listar(limit=101))


def test_empty_keys_are_rejected():
    with pytest.raises(ValueError):
        CuponesClient("  ")
    with pytest.raises(ValueError):
        ObrasSocialesClient("")


# ---------- Obras sociales ----------


def test_listing_follows_pagination_and_uses_header():
    pages = []

    def handler(request):
        assert request.headers["x-api-key"] == "clave-de-prueba"
        page = int(request.url.params["pagina"])
        pages.append(page)
        return httpx.Response(
            200,
            json={"datos": [{"id": f"os-{page}", "nombre": f"OS {page}"}], "pagina": page,
                  "por_pagina": 100, "total": 2, "total_paginas": 2},
        )

    items = run(obras(handler).listar_obras_sociales())
    assert [i["id"] for i in items] == ["os-1", "os-2"]
    assert pages == [1, 2]


def test_obtener_obra_social_finds_or_returns_none():
    def handler(request):
        return httpx.Response(200, json={"datos": [{"id": "os-1", "nombre": "Uno"}], "total_paginas": 1})

    client = obras(handler)
    assert run(client.obtener_obra_social("os-1"))["nombre"] == "Uno"
    assert run(client.obtener_obra_social("otra")) is None


def test_create_request_payload_and_validation():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(201, json={"id": "sol-1", "estado": "pendiente",
                                         "urls_simulacion": {"autorizar": f"{OBRAS}/simulacion/t/autorizar",
                                                             "rechazar": f"{OBRAS}/simulacion/t/rechazar"}})

    result = run(obras(handler).crear_solicitud(
        obra_social_id="os-1", paciente_nombre="Paciente Demo",
        fecha=date(2026, 11, 16), referencia_externa="estudio-7"))
    assert result["id"] == "sol-1"
    assert seen == {"obra_social_id": "os-1", "paciente_nombre": "Paciente Demo",
                    "fecha": "2026-11-16", "referencia_externa": "estudio-7"}

    with pytest.raises(ExternalServiceError):
        run(obras(lambda r: httpx.Response(201, json={"id": "x"})).crear_solicitud(
            obra_social_id="os-1", paciente_nombre="P", fecha=date.today(), referencia_externa="e"))


def test_authorize_and_reject_use_simulation_urls_only_of_the_same_origin():
    calls = []

    def handler(request):
        calls.append((str(request.url), request.content))
        return httpx.Response(200, json={"estado": "autorizada", "porcentaje_cobertura": 40})

    client = obras(handler)
    url = f"{OBRAS}/simulacion/tok/autorizar"
    assert run(client.autorizar(url))["porcentaje_cobertura"] == 40
    run(client.autorizar(url, 60))
    run(client.rechazar(f"{OBRAS}/simulacion/tok/rechazar", "Falta orden"))
    assert calls[0][1] == b""
    assert json.loads(calls[1][1]) == {"porcentaje": 60}
    assert json.loads(calls[2][1]) == {"motivo": "Falta orden"}

    for hostile in ("https://evil.test/simulacion/x", "http://obras.test/api/simulacion/x", "file:///etc/passwd"):
        with pytest.raises(ExternalServiceError):
            run(client.autorizar(hostile))
    assert len(calls) == 3


def test_demand_is_sent_as_multipart_with_archivo_field():
    seen = {}

    def handler(request):
        seen.update(path=request.url.path, ctype=request.headers["content-type"], body=request.content)
        return httpx.Response(200, json={"estado": "demanda_en_curso"})

    pdf = b"%PDF-1.4 demo"
    run(obras(handler).presentar_demanda("sol-1", 'de"manda.pdf', pdf))
    assert seen["path"] == "/api/solicitudes/sol-1/demanda"
    assert seen["ctype"].startswith("multipart/form-data; boundary=")
    assert b'name="archivo"; filename="demanda.pdf"' in seen["body"]
    assert pdf in seen["body"]


def test_demand_rejects_oversized_and_malformed_ids():
    client = obras(lambda r: httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        run(client.presentar_demanda("sol-1", "d.pdf", b"0" * (5 * 1024 * 1024 + 1)))
    with pytest.raises(ValueError):
        run(client.presentar_demanda("../x", "d.pdf", b"%PDF"))


@pytest.mark.parametrize("status,expected", [(400, 400), (404, 404), (409, 409), (422, 422), (401, 502), (500, 502)])
def test_obras_error_mapping_and_message(status, expected):
    def handler(request):
        return httpx.Response(status, json={"error": {"codigo": "x", "mensaje": "No se puede", "detalle": "motivo"}})

    with pytest.raises(ExternalServiceError) as error:
        run(obras(handler).rechazar(f"{OBRAS}/simulacion/t/rechazar", "m"))
    assert error.value.status_code == expected
    assert "No se puede" in str(error.value)


def test_obras_network_failure_is_503():
    def handler(request):
        raise httpx.ConnectError("sin red")

    with pytest.raises(ExternalServiceError) as error:
        run(obras(handler).listar_obras_sociales())
    assert error.value.status_code == 503
