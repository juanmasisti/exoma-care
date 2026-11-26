"""Consulta en FedEx los retiros programados y pasa a "en viaje" los lotes ya retirados.

Para la demo: FedEx no avisa y no hay cron, así que se consulta a mano (es lo mismo que el botón
"Actualizar estado" de cada lote). Usa la configuración de FedEx de back/.env.

Uso (desde back/, con el entorno virtual activo):
    python -m scripts.consultar_retiros
"""
from datetime import datetime

from fastapi import HTTPException

from app.api.routes.shipments import get_courier, get_health_ministry, get_shipment_service
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.session import SessionLocal
from app.use_cases.shipments import IN_TRANSIT, Conflict, ExternalServiceError


def main() -> None:
    try:
        courier = get_courier()
    except HTTPException as exc:
        raise SystemExit(exc.detail) from exc
    with SessionLocal() as session:
        service = get_shipment_service(session, get_health_ministry())
        sample_set_ids = service.shipments.awaiting_pickup()
        if not sample_set_ids:
            print("No hay lotes esperando el retiro.")
        for sample_set_id in sample_set_ids:
            try:
                status = service.actualizar_estado(sample_set_id, datetime.now(TIMEZONE), courier, None)["status"]
            except (Conflict, ExternalServiceError) as exc:
                print(f"Lote {sample_set_id}: {exc}")
                continue
            print(f"Lote {sample_set_id}: "
                  + ("en viaje al laboratorio de secuenciación." if status == IN_TRANSIT else "sigue esperando el retiro."))


if __name__ == "__main__":
    main()
