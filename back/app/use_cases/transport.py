from datetime import date

from app.domain.entities.logistics import is_business_day
from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository
from app.domain.interfaces.route_repository import RouteAlreadyExists, RouteRepository
from app.use_cases.routes import RoutePreviewService


class InvalidDay(Exception):
    pass


class TransportService:
    def __init__(self, routes: RouteRepository, centers: ExtractionCenterRepository,
                 route_preview: RoutePreviewService):
        self.routes = routes
        self.centers = centers
        self.route_preview = route_preview

    def generar_orden_del_dia(self, day: date) -> tuple[bool, list[dict]]:
        """Una orden por provincia con muestras listas que todavía no la tenga. Devuelve (creó alguna, órdenes del día)."""
        holiday = self.centers.holiday(day)
        if not is_business_day(day, {day} if holiday else set()):
            reason = f"es feriado ({holiday})" if holiday else "es fin de semana"
            raise InvalidDay(f"El {day:%d/%m/%Y} {reason}: no hay orden del día.")
        existing = {route["province_id"] for route in self.routes.routes_for_day(day)}
        pending = {province_id: center_ids
                   for province_id, center_ids in self.routes.centers_with_ready_samples().items()
                   if province_id not in existing}
        # Primero todas las secuencias: si la API de recorridos falla con una provincia, no se guarda ninguna orden.
        sequences = {province_id: [center["id"] for center in self.route_preview.order_centers(center_ids)]
                     for province_id, center_ids in pending.items()}
        created = False
        for province_id, center_ids in sequences.items():
            try:
                # PROVISORIO (decisión 016): sin transportista hasta que exista el rol con provincia.
                self.routes.add_route(day, province_id, None, center_ids)
                created = True
            except RouteAlreadyExists:
                pass  # otro pedido la generó recién: no se toca
        self.routes.commit()
        return created, self.routes.routes_for_day(day)

    def listar(self, day: date) -> list[dict]:
        return self.routes.routes_for_day(day)
