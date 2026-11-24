from datetime import date, datetime

from app.domain.entities.logistics import (
    DailyRouteStatus, SampleStatus, can_change_route, is_business_day, next_stop_sequence,
)
from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository
from app.domain.interfaces.route_repository import RouteAlreadyExists, RouteRepository
from app.domain.interfaces.sample_repository import SampleRepository
from app.domain.interfaces.sample_set_hooks import SampleSetAssigner
from app.use_cases.routes import RoutePreviewService


class InvalidDay(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class TransportService:
    def __init__(self, routes: RouteRepository, samples: SampleRepository, centers: ExtractionCenterRepository,
                 route_preview: RoutePreviewService):
        self.routes = routes
        self.samples = samples
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

    def mi_recorrido(self, day: date, province_id: int) -> dict:
        # PROVISORIO (decisión 016): la provincia llega en el pedido hasta que el rol transporter la tenga.
        route = self.routes.route_for(day, province_id)
        if route is None:
            raise NotFound("No hay orden del día para esa provincia en esa fecha.")
        route = self._route(route["id"])
        picked = [stop for stop in route["stops"] if stop["picked_up_at"] is not None]
        sequence = next_stop_sequence([stop["sequence"] for stop in picked], len(route["stops"]))
        on_board = route["status"] == DailyRouteStatus.PENDING.value
        return {**route,
                "next_stop_id": next((stop["id"] for stop in route["stops"] if stop["sequence"] == sequence), None),
                "on_board": [code for stop in picked for code in stop["sample_codes"]] if on_board else []}

    def retirar(self, route_id: int, stop_id: int, actor_id: int, now: datetime) -> dict:
        """Pasa a with_transporter las muestras listas del centro en este momento y las guarda como retiradas."""
        route = self._route(route_id)
        stop = next((stop for stop in route["stops"] if stop["id"] == stop_id), None)
        if stop is None:
            raise NotFound("La parada no es de esta orden del día.")
        if route["status"] != DailyRouteStatus.PENDING.value:
            raise Conflict("La llegada de esta orden ya fue registrada.")
        if stop["picked_up_at"] is not None:
            raise Conflict("Este centro ya fue retirado.")
        expected = next_stop_sequence([s["sequence"] for s in route["stops"] if s["picked_up_at"] is not None],
                                      len(route["stops"]))
        if stop["sequence"] != expected:
            raise Conflict(f"El recorrido es fijo: primero hay que retirar la parada {expected}.")
        try:
            if not self.routes.mark_stop_picked(stop_id, now):
                raise Conflict("Este centro ya fue retirado.")
            # Primero el cambio condicional: si otro retiro ya se llevó alguna, es 409 antes de chocar en route_pickups.
            moved = self.samples.change_status(stop["sample_ids"], SampleStatus.READY_FOR_PICKUP.value,
                                               SampleStatus.WITH_TRANSPORTER.value, now, actor_id)
            if moved != len(stop["sample_ids"]):
                raise Conflict("Las muestras del centro cambiaron mientras se registraba el retiro. Volvé a intentar.")
            self.routes.add_pickups(stop_id, stop["sample_ids"])
        except Exception:
            self.routes.rollback()
            raise
        self.routes.commit()
        return {"route_id": route_id, "stop_id": stop_id, "center": stop["center"], "picked_up_at": now,
                "sample_codes": stop["sample_codes"]}

    def registrar_llegada(self, route_id: int, actor_id: int, now: datetime, assigner: SampleSetAssigner) -> dict:
        """Recibe exactamente las muestras retiradas y dispara el armado de lotes por cada una."""
        route = self._route(route_id)
        if not can_change_route(DailyRouteStatus(route["status"]), DailyRouteStatus.ARRIVED):
            raise Conflict("La llegada de esta orden ya fue registrada.")
        missing = sum(stop["picked_up_at"] is None for stop in route["stops"])
        if missing:
            raise Conflict(f"El recorrido es fijo: faltan retirar {missing} centros antes de la llegada.")
        sample_ids = [sample_id for stop in route["stops"] for sample_id in stop["sample_ids"]]
        try:
            if not self.routes.mark_arrived(route_id, now):
                raise Conflict("La llegada de esta orden ya fue registrada.")
            moved = self.samples.change_status(sample_ids, SampleStatus.WITH_TRANSPORTER.value,
                                               SampleStatus.RECEIVED.value, now, actor_id)
            if moved != len(sample_ids):
                raise Conflict("Las muestras a bordo cambiaron mientras se registraba la llegada. Volvé a intentar.")
            for sample_id in sample_ids:
                assigner.asignar_a_sample_set(sample_id, now)
        except Exception:
            # Los enganches no confirman ni deshacen: si el armado falla, se deshace la llegada entera.
            self.routes.rollback()
            raise
        self.routes.commit()
        return {"route_id": route_id, "arrived_at": now,
                "received_codes": [code for stop in route["stops"] for code in stop["sample_codes"]]}

    def _route(self, route_id: int) -> dict:
        route = self.routes.route_detail(route_id)
        if route is None:
            raise NotFound("La orden del día no existe.")
        return route
