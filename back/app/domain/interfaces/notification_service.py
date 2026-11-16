from abc import ABC, abstractmethod
from typing import Any

from app.domain.dtos.notification_dto import (
    NotificacionInput,
    NotificacionResultado,
)


class INotificationService(ABC):
    @abstractmethod
    async def enviar_aviso(
        self, datos: NotificacionInput
    ) -> NotificacionResultado: ...

    @abstractmethod
    async def verificar_conexion(self) -> dict[str, Any]: ...

    @abstractmethod
    async def consultar_estado(self, aviso_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def listar_pendientes(self, limite: int = 25) -> dict[str, Any]: ...
