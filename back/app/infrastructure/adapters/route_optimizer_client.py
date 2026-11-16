"""Cliente de la API de optimización de recorridos (módulo 9, de otro grupo)."""
import httpx

from app.domain.interfaces.route_optimizer import Point, RouteOptimizerError

TIMEOUT_SECONDS = 5


class RouteOptimizerClient:
    def __init__(self, url: str, transport: httpx.BaseTransport | None = None):
        self.url = url
        self.transport = transport  # las pruebas pasan un httpx.MockTransport

    def order(self, points: list[Point]) -> list[Point]:
        body = {"coordenadas": [{"lat": lat, "lon": lon} for lat, lon in points]}
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self.transport) as http:
                response = http.post(self.url, json=body)
            response.raise_for_status()
            return [(float(point["lat"]), float(point["lon"])) for point in response.json()["coordenadas"]]
        except httpx.TimeoutException as exc:
            raise RouteOptimizerError("El módulo de recorridos tardó demasiado en responder.") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RouteOptimizerError("El módulo de recorridos no respondió correctamente.") from exc
