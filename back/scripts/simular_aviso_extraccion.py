"""SIMULACIÓN del bot de extracción (ningún grupo lo tiene; sección 7 del dominio).

Hace el mismo POST que haría el bot real cuando un centro avisa que tomó la muestra.
Solo el camino feliz. Con el back levantado, desde back/:

    .\\.venv\\Scripts\\python.exe -m scripts.simular_aviso_extraccion EST-000001 2.5
"""
import argparse
import uuid
from datetime import datetime

import httpx

from app.config import get_settings
from app.domain.entities.logistics import TIMEZONE


class SimulatedExtractionBot:
    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url
        self.secret = secret

    def avisar(self, study_code: str, volume_ml: str) -> httpx.Response:
        notice = {"external_id": f"sim-{uuid.uuid4()}", "study_code": study_code, "volume_ml": volume_ml,
                  "taken_at": datetime.now(TIMEZONE).isoformat()}
        return httpx.post(f"{self.base_url}/api/webhooks/extraction", json=notice,
                          headers={"X-Webhook-Secret": self.secret}, timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description="SIMULACIÓN del bot de extracción.")
    parser.add_argument("study_code", help="código impreso en la orden, por ejemplo EST-000001")
    parser.add_argument("volume_ml", help="mililitros del tubo, por ejemplo 2.5")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    secret = get_settings().extraction_webhook_secret
    if secret is None:
        raise SystemExit("Configurá EXTRACTION_WEBHOOK_SECRET en back/.env.")
    print("SIMULACIÓN DEL BOT DE EXTRACCIÓN")
    response = SimulatedExtractionBot(args.url, secret.get_secret_value()).avisar(args.study_code, args.volume_ml)
    print(response.status_code, response.json())


if __name__ == "__main__":
    main()
