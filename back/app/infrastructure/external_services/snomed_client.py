"""Bounded SNOMED search with sanitized provider failures."""
import math
import re
from urllib.parse import urlsplit
import httpx
from app.infrastructure.external_services.errors import ExternalServiceError


class SnomedClient:
    def __init__(self, api_key: str, *, url: str, region: str = 'us-east-1', timeout: float = 15.0, transport=None):
        parsed = urlsplit(url)
        if not api_key.strip() or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Configura una URL HTTPS y credenciales SNOMED válidas.')
        self._key, self._url, self._region = api_key, url, region
        self._timeout, self._transport = timeout, transport

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        query = query.strip()
        if not 3 <= len(query) <= 100 or not 1 <= limit <= 50:
            raise ValueError('Escribe entre 3 y 100 caracteres y solicita entre 1 y 50 resultados.')
        unavailable = 'El servicio SNOMED no está disponible. Intenta nuevamente.'
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport, follow_redirects=False) as client:
                response = await client.get(self._url, params={'q': query, 'limite': limit}, headers={'X-API-Key': self._key, 'x-region': self._region, 'Accept': 'application/json'})
            if response.status_code != 200:
                raise ExternalServiceError('SNOMED', unavailable, 503)
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('resultados'), list) or len(payload['resultados']) > 50:
                raise ValueError()
            results, seen = [], set()
            for item in payload['resultados']:
                if not isinstance(item, dict):
                    raise ValueError()
                code, label = item.get('sctid'), item.get('termino_preferido')
                strategy, similarity = item.get('estrategia'), item.get('similitud')
                if not isinstance(code, str) or not re.fullmatch(r'[1-9][0-9]{5,17}', code) or not isinstance(label, str) or not 1 <= len(label.strip()) <= 200:
                    raise ValueError()
                if strategy not in (None, 'exacta', 'prefijo', 'lexica', 'semantica'):
                    raise ValueError()
                if similarity is not None and (type(similarity) not in (int, float) or not math.isfinite(similarity) or not 0 <= similarity <= 1):
                    raise ValueError()
                if code not in seen:
                    results.append({'code': code, 'label': label.strip(), 'code_system': 'SNOMED', 'strategy': strategy, 'similarity': similarity})
                    seen.add(code)
            return results[:limit]
        except (httpx.HTTPError, ValueError, TypeError):
            raise ExternalServiceError('SNOMED', unavailable, 503) from None
