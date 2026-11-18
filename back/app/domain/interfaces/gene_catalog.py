"""Contrato para consultar genes y patologías de una fuente externa (hoy, Apigen)."""

from typing import Any, Protocol


class GeneCatalogGateway(Protocol):
    async def listar_patologias(self) -> list[dict[str, Any]]:
        """Patologías disponibles: codigo, nombre, herencia y genes."""
        ...

    async def genes_por_patologia(self, codigo: str) -> list[str]:
        """Símbolos de los genes asociados a una patología, por su código."""
        ...

    async def genes_hallazgos_secundarios(self) -> list[dict[str, Any]]:
        """Genes de hallazgos secundarios: gen, condicion y herencia."""
        ...

    async def buscar_genes(self, prefijo: str, limit: int = 20) -> list[str]:
        """Símbolos de gen que empiezan con el prefijo, para autocompletar."""
        ...
