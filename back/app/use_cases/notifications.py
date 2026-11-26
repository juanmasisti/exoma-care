from app.domain.dtos.notification_dto import (
    NotificacionInput,
    NotificacionResultado,
)
from app.domain.interfaces.notification_service import INotificationService
from app.infrastructure.repositories.sqlalchemy_notification_log_repository import (
    SQLAlchemyNotificationLogRepository,
)


class EnviarNotificacionUseCase:
    def __init__(
        self,
        notification_service: INotificationService,
        log_repository: SQLAlchemyNotificationLogRepository,
    ):
        self._notification_service = notification_service
        self._log_repository = log_repository

    async def execute(self, datos: NotificacionInput) -> NotificacionResultado:
        resultado = await self._notification_service.enviar_aviso(datos)
        self._log_repository.guardar(
            aviso_id=resultado.aviso_id,
            idempotency_key=datos.idempotency_key,
            referencia=datos.referencia,
            asunto=datos.asunto,
            estado_inicial=resultado.estado,
        )
        return resultado

    async def enviar_aviso_resultado(
        self,
        *,
        study_id: int,
        asunto: str,
        mensaje: str,
        destinatarios: list[dict[str, str]],
        idempotency_key: str | None = None,
    ) -> int:
        datos = NotificacionInput(
            asunto=asunto,
            mensaje=mensaje,
            destinatarios=[destinatario["destino"] for destinatario in destinatarios],
            idempotency_key=idempotency_key or f"resultado-{study_id}-aviso",
            referencia=str(study_id),
        )
        resultado = await self.execute(datos)
        return 202 if resultado.creado else 200
