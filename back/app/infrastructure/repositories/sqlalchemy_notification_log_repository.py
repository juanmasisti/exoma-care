from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import NotificacionLog


class SQLAlchemyNotificationLogRepository:
    def __init__(self, session: Session):
        self._session = session

    def guardar(
        self,
        *,
        aviso_id: str,
        idempotency_key: str,
        referencia: str | None,
        asunto: str,
        estado_inicial: str,
    ) -> NotificacionLog:
        existing = self._session.scalar(
            select(NotificacionLog).where(
                NotificacionLog.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if existing.aviso_id != aviso_id:
                raise RuntimeError(
                    "La Idempotency-Key ya está asociada a otro aviso."
                )
            return existing

        log = NotificacionLog(
            aviso_id=aviso_id,
            idempotency_key=idempotency_key,
            referencia=referencia,
            asunto=asunto,
            estado_inicial=estado_inicial,
        )
        self._session.add(log)
        self._session.commit()
        return log
