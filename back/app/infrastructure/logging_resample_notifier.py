import logging

logger = logging.getLogger(__name__)


class LoggingResampleNotifier:
    """PROVISORIO: solo deja el aviso en el log hasta que exista `notificar` del servicio de avisos (Camila, EC-20)."""

    def avisar_remuestreo(self, study_id: int, motivo: str) -> None:
        logger.info("Aviso de remuestreo pendiente de enviar (estudio %s): %s", study_id, motivo)
