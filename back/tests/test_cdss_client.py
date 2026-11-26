import asyncio

import httpx
import pytest

from app.infrastructure.external_services.cdss_client import (
    CDSS_UNAVAILABLE_MESSAGE,
    CDSSClient,
)
from app.infrastructure.external_services.errors import ExternalServiceError


def test_cdss_client_sends_api_key_and_returns_only_code_and_name():
    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/api/v1/patologias"
        assert request.headers["X-API-Key"] == "test-key"
        return httpx.Response(
            200,
            json=[
                {
                    "codigo": "FABRY",
                    "nombre": "Enfermedad de Fabry",
                    "sintomas": ["omitido"],
                }
            ],
        )

    client = CDSSClient(
        "test-key",
        transport=httpx.MockTransport(respond),
    )
    assert asyncio.run(client.obtener_patologias()) == [
        {"codigo": "FABRY", "nombre": "Enfermedad de Fabry"}
    ]


@pytest.mark.parametrize("status_code", [500, 503])
def test_cdss_server_errors_become_503(status_code):
    client = CDSSClient(
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"error": "down"})
        ),
    )
    with pytest.raises(ExternalServiceError, match=CDSS_UNAVAILABLE_MESSAGE) as error:
        asyncio.run(client.obtener_patologias())
    assert error.value.status_code == 503


def test_cdss_invalid_api_key_is_401():
    client = CDSSClient(
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                401, json={"code": "API_KEY_INVALIDA"}
            )
        ),
    )
    with pytest.raises(ExternalServiceError, match="Credenciales inválidas") as error:
        asyncio.run(client.obtener_patologias())
    assert error.value.status_code == 401


def test_cdss_network_error_becomes_503():
    def fail(_request):
        raise httpx.ConnectError("network unavailable")

    client = CDSSClient("test-key", transport=httpx.MockTransport(fail))
    with pytest.raises(ExternalServiceError, match=CDSS_UNAVAILABLE_MESSAGE) as error:
        asyncio.run(client.obtener_patologias())
    assert error.value.status_code == 503


def test_cdss_timeout_becomes_503():
    def timeout(_request):
        raise httpx.ReadTimeout("request timed out")

    client = CDSSClient("test-key", transport=httpx.MockTransport(timeout))
    with pytest.raises(ExternalServiceError, match=CDSS_UNAVAILABLE_MESSAGE) as error:
        asyncio.run(client.obtener_patologias())
    assert error.value.status_code == 503


def test_cdss_invalid_response_shape_becomes_503():
    client = CDSSClient(
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[{"codigo": "FABRY"}])
        ),
    )
    with pytest.raises(ExternalServiceError, match=CDSS_UNAVAILABLE_MESSAGE) as error:
        asyncio.run(client.obtener_patologias())
    assert error.value.status_code == 503
