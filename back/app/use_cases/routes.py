from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository
from app.domain.interfaces.route_optimizer import Point, RouteOptimizer, RouteOptimizerError

# La API no devuelve ids: cada punto se reconoce por sus coordenadas, con margen por redondeo (~0,1 m).
MATCH_TOLERANCE = 1e-6


def _same_point(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= MATCH_TOLERANCE and abs(a[1] - b[1]) <= MATCH_TOLERANCE


class RoutePreviewService:
    def __init__(self, centers: ExtractionCenterRepository, optimizer: RouteOptimizer, central_lab: Point):
        self.centers = centers
        self.optimizer = optimizer
        self.central_lab = central_lab

    def order_centers(self, center_ids: list[int]) -> list[dict]:
        if len(set(center_ids)) != len(center_ids):
            raise ValueError("Hay centros repetidos en la lista.")
        centers = []
        for center_id in center_ids:
            center = self.centers.get_active_center(center_id)
            if center is None:
                raise LookupError(f"El centro de extracción {center_id} no existe o no está activo.")
            centers.append(center)
        if len(centers) <= 1:
            return centers

        points = [self.central_lab, *((c["latitude"], c["longitude"]) for c in centers), self.central_lab]
        ordered = self.optimizer.order(points)
        if (len(ordered) != len(points) or not _same_point(ordered[0], self.central_lab)
                or not _same_point(ordered[-1], self.central_lab)):
            raise RouteOptimizerError("El módulo de recorridos devolvió un recorrido que no corresponde al pedido.")
        pending, result = list(centers), []
        for point in ordered[1:-1]:
            center = next((c for c in pending if _same_point(point, (c["latitude"], c["longitude"]))), None)
            if center is None:
                raise RouteOptimizerError(
                    f"El módulo de recorridos devolvió el punto {point[0]}, {point[1]}, que no es de ningún centro pedido.")
            pending.remove(center)
            result.append(center)
        return result
