import hashlib
import json
from typing import Any

import httpx

from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.list_cache import (
    TTLListCache,
    apigen_list_cache,
)

VARIANT_COLUMNS = "id,hgvs_c,proteina,clasificacion"


class ApigenClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
        list_cache: TTLListCache | None = None,
    ):
        if not base_url.strip():
            raise ValueError("base_url de Apigen no puede estar vacía.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._list_cache = list_cache if list_cache is not None else apigen_list_cache

    async def listar_patologias(self, grupo_id: str) -> list[dict[str, Any]]:
        from pydantic import TypeAdapter, ValidationError
        from app.infrastructure.external_services.clinical_contracts import GeneticPathology
        payload = await self._clinical_request("POST", "/rpc/listar_patologias", json={"p_grupo_id": grupo_id})
        try:
            return [item.model_dump() for item in TypeAdapter(list[GeneticPathology]).validate_python(payload)]
        except ValidationError as exc:
            raise ExternalServiceError("Apigen", "Apigen devolvió un catálogo inválido.", 502) from exc

    async def buscar_genes(self, query: str) -> list[str]:
        payload = await self._clinical_request("GET", "/gen", params={"simbolo": f"ilike.{query}*", "select": "simbolo", "limit": "20"})
        if not isinstance(payload, list) or any(not isinstance(item, dict) or not isinstance(item.get("simbolo"), str) for item in payload):
            raise ExternalServiceError("Apigen", "Apigen devolvió genes inválidos.", 502)
        return [item["simbolo"] for item in payload]

    async def alta_patologia(self, grupo_id: str, codigo: str, nombre: str, genes: list[str], herencia: str) -> dict[str, Any]:
        from pydantic import TypeAdapter, ValidationError
        from app.infrastructure.external_services.clinical_contracts import GeneticPathology
        payload = await self._clinical_request("POST", "/rpc/alta_patologia", json={
            "p_grupo_id": grupo_id, "p_codigo": codigo, "p_nombre": nombre,
            "p_genes": genes, "p_herencia": herencia,
        })
        try:
            records = TypeAdapter(list[GeneticPathology]).validate_python(payload)
            if len(records) != 1 or records[0].codigo != codigo:
                raise ValueError("identity mismatch")
            return records[0].model_dump() | {"de_grupo": True}
        except (ValidationError, ValueError) as exc:
            raise ExternalServiceError("Apigen", "No se pudo verificar el alta. Actualizá el catálogo externo antes de reintentar.", 502) from exc

    async def _clinical_request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            return await self._request(method, path, **kwargs)
        except ExternalServiceError as exc:
            # Provider errors may echo credentials or submitted payloads.
            raise ExternalServiceError("Apigen", "No se pudo completar la consulta a Apigen. Revisá los datos o reintentá más tarde.", 503 if exc.status_code >= 500 else 502) from None

    async def buscar_variantes(
        self,
        gen: str,
        hgvs_c: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        params = {
            "gen": f"eq.{gen}",
            "select": VARIANT_COLUMNS,
            "limit": str(limit),
            "offset": str(offset),
        }
        if hgvs_c:
            params["hgvs_c"] = f"ilike.*{hgvs_c}*"
        cache_key = self._variant_cache_key(params)
        cached_result = self._list_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        response = await self._request(
            "GET",
            "/variantes",
            params=params,
            extra_headers={"Prefer": "count=exact"},
            return_response=True,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                "Apigen", "Apigen devolvió una respuesta JSON inválida.", 502
            ) from exc
        if not isinstance(payload, list):
            raise ExternalServiceError(
                "Apigen", "Apigen devolvió una lista de variantes inválida.", 502
            )
        result = (payload, _total_count(response.headers.get("Content-Range")))
        self._list_cache.set(cache_key, result)
        return result

    async def resultado_diagnostico(
        self, patologia: str, variantes: list[str]
    ) -> Any:
        return await self._request(
            "POST",
            "/rpc/resultado_diagnostico",
            json={"p_patologia": patologia, "p_variantes": variantes},
        )

    async def hallazgos_secundarios(
        self,
        variantes: list[str],
        excluir_patologias: list[str],
    ) -> Any:
        return await self._request(
            "POST",
            "/rpc/hallazgos_secundarios",
            json={
                "p_variantes": variantes,
                "p_excluir_patologias": excluir_patologias,
            },
        )

    async def consultar_diagnostico(
        self, patologia: str, variantes: list[dict[str, Any]]
    ) -> Any:
        return await self._request(
            "POST",
            "/rpc/resultado_diagnostico",
            json={"p_patologia": patologia, "p_variantes": variantes},
        )

    async def consultar_hallazgos(
        self,
        variantes: list[dict[str, Any]],
        excluir_patologias: list[str],
    ) -> Any:
        return await self._request(
            "POST",
            "/rpc/hallazgos_secundarios",
            json={
                "p_variantes": variantes,
                "p_excluir_patologias": excluir_patologias,
            },
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        extra_headers: dict[str, str] | None = None,
        return_response: bool = False,
        **kwargs: Any,
    ) -> Any:
        headers = {
            "apikey": self._api_key,
            "Accept": "application/json",
            **(extra_headers or {}),
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ExternalServiceError(
                "Apigen", "Apigen no responde.", 503
            ) from exc
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                "Apigen", "Apigen no responde.", 503
            ) from exc

        if response.status_code >= 400:
            raise ExternalServiceError(
                "Apigen",
                _response_message(response),
                response.status_code,
            )
        if return_response:
            return response
        try:
            return response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                "Apigen", "Apigen devolvió una respuesta JSON inválida.", 502
            ) from exc

    def _variant_cache_key(self, params: dict[str, str]) -> str:
        key_fingerprint = hashlib.sha256(self._api_key.encode("utf-8")).hexdigest()
        canonical_params = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return f"{self._base_url}|{key_fingerprint}|/variantes|{canonical_params}"


def _response_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    text = response.text.strip()
    return text[:500] if text else f"Apigen respondió HTTP {response.status_code}."


def _total_count(content_range: str | None) -> int:
    if not content_range or "/" not in content_range:
        return 0
    total = content_range.rsplit("/", 1)[1]
    try:
        return int(total)
    except ValueError:
        return 0
