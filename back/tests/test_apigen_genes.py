import asyncio
import json

import httpx
import pytest

from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.errors import ExternalServiceError

BASE_URL = "https://apigen.test/rest/v1"


def client_for(respond):
    return ApigenClient("test-key", base_url=BASE_URL, transport=httpx.MockTransport(respond))


def test_genes_por_patologia_posts_the_pathology_code():
    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/genes_por_patologia"
        assert request.headers["apikey"] == "test-key"
        assert json.loads(request.content) == {"p_patologia": "POMPE"}
        return httpx.Response(200, json=["GAA"])

    assert asyncio.run(client_for(respond).genes_por_patologia("POMPE")) == ["GAA"]


def test_genes_por_patologia_rejects_an_invalid_shape():
    client = client_for(lambda _request: httpx.Response(200, json=[{"gen": "GAA"}]))
    with pytest.raises(ExternalServiceError) as error:
        asyncio.run(client.genes_por_patologia("POMPE"))
    assert error.value.status_code == 502


def test_unknown_pathology_shows_the_apigen_message():
    client = client_for(
        lambda _request: httpx.Response(400, json={"message": "Patología inexistente: XYZ"})
    )
    with pytest.raises(ExternalServiceError, match="Patología inexistente: XYZ") as error:
        asyncio.run(client.genes_por_patologia("XYZ"))
    assert error.value.status_code == 400


def test_listar_patologias_returns_code_inheritance_and_genes():
    pathologies = [
        {"codigo": "ASMD", "nombre": "ASMD", "herencia": "autosomica_recesiva", "genes": ["SMPD1"], "de_grupo": False}
    ]

    def respond(request):
        assert request.url.path == "/rest/v1/rpc/listar_patologias"
        return httpx.Response(200, json=pathologies)

    assert asyncio.run(client_for(respond).listar_patologias()) == pathologies


def test_listar_patologias_rejects_items_without_genes():
    client = client_for(lambda _request: httpx.Response(200, json=[{"codigo": "ASMD"}]))
    with pytest.raises(ExternalServiceError):
        asyncio.run(client.listar_patologias())


def test_genes_hallazgos_secundarios_requests_the_acmg_columns():
    findings = [{"gen": "BRCA1", "condicion": "Cáncer de mama y ovario hereditario", "herencia": "dominante"}]

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/genes_hallazgos_secundarios"
        assert request.url.params["select"] == "gen,condicion,herencia"
        return httpx.Response(200, json=findings)

    assert asyncio.run(client_for(respond).genes_hallazgos_secundarios()) == findings


def test_buscar_genes_filters_by_prefix_and_returns_symbols():
    def respond(request):
        assert request.url.path == "/rest/v1/gen"
        assert request.url.params["simbolo"] == "ilike.GA*"
        assert request.url.params["select"] == "simbolo"
        assert request.url.params["limit"] == "20"
        return httpx.Response(200, json=[{"simbolo": "GAA"}, {"simbolo": "GAB1"}])

    assert asyncio.run(client_for(respond).buscar_genes("GA")) == ["GAA", "GAB1"]


@pytest.mark.parametrize("prefix", ["", "  ", "GA*&select=*", "G A", "GAA,BRCA1"])
def test_buscar_genes_rejects_prefixes_that_could_alter_the_query(prefix):
    def respond(_request):
        raise AssertionError("no debe llamar a Apigen")

    with pytest.raises(ValueError):
        asyncio.run(client_for(respond).buscar_genes(prefix))


def test_apigen_network_error_becomes_503():
    def fail(_request):
        raise httpx.ConnectError("network unavailable")

    with pytest.raises(ExternalServiceError) as error:
        asyncio.run(client_for(fail).genes_por_patologia("POMPE"))
    assert error.value.status_code == 503
