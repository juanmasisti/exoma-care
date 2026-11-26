import asyncio

import httpx
import pytest
from app.infrastructure.external_services.snomed_client import SnomedClient
from app.infrastructure.external_services.errors import ExternalServiceError


def test_search_contract():
    def respond(request):
        assert request.headers['X-API-Key'] == 'private-test-key'
        assert request.headers['x-region'] == 'us-east-1'
        assert request.url.params['q'] == 'fiebre'
        return httpx.Response(200, json={'resultados': [{'sctid': '386661006', 'termino_preferido': 'fiebre', 'estrategia': 'exacta', 'similitud': None}]})
    client = SnomedClient('private-test-key', url='https://example.test/sintomas', transport=httpx.MockTransport(respond))
    assert asyncio.run(client.search(' fiebre '))[0]['code'] == '386661006'


@pytest.mark.parametrize('payload', [{}, {'resultados': [{}]}, {'resultados': [{'sctid': 386661006, 'termino_preferido': 'fiebre'}]}])
def test_malformed_provider_response(payload):
    client = SnomedClient('private-test-key', url='https://example.test', transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(ExternalServiceError, match='SNOMED'):
        asyncio.run(client.search('fiebre'))


@pytest.mark.parametrize('status', [401, 403, 429, 500, 503])
def test_provider_errors_are_sanitized(status):
    client = SnomedClient('private-test-key', url='https://example.test', transport=httpx.MockTransport(lambda r: httpx.Response(status, text='private-test-key')))
    with pytest.raises(ExternalServiceError) as error:
        asyncio.run(client.search('fiebre'))
    assert 'private-test-key' not in str(error.value)


@pytest.mark.parametrize('query,limit', [('ab', 10), ('   ', 10), ('fiebre', 51), ('fiebre', 0)])
def test_invalid_search(query, limit):
    client = SnomedClient('private-test-key', url='https://example.test')
    with pytest.raises(ValueError):
        asyncio.run(client.search(query, limit))


def test_timeout_is_sanitized():
    def timeout(request):
        raise httpx.ReadTimeout('private-test-key', request=request)
    client = SnomedClient('private-test-key', url='https://example.test', transport=httpx.MockTransport(timeout))
    with pytest.raises(ExternalServiceError) as error:
        asyncio.run(client.search('fiebre'))
    assert 'private-test-key' not in str(error.value)


def test_duplicate_results_keep_provider_order_and_empty_results_are_valid():
    items = [{'sctid': '386661006', 'termino_preferido': 'fiebre'}, {'sctid': '386661006', 'termino_preferido': 'sinónimo'}]
    client = SnomedClient('private-test-key', url='https://example.test', transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'resultados': items})))
    assert [item['label'] for item in asyncio.run(client.search('fiebre'))] == ['fiebre']
    items.clear()
    assert asyncio.run(client.search('fiebre')) == []
