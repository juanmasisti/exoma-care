from datetime import datetime

from fastapi import APIRouter

from app.domain.interfaces.sample_set_hooks import SampleSetAssigner

# Vacío en la base (decisión 016): T05 agrega GET /api/sample-sets y GET /api/sample-sets/{id}.
router = APIRouter(prefix="/api/sample-sets", tags=["sample sets"])


class PendingSampleSetAssigner:
    """PROVISORIO hasta T05: la llegada no arma lotes todavía."""

    def asignar_a_sample_set(self, sample_id: int, now: datetime) -> None:
        pass


# Enganche que usa la llegada (T04) con Depends; lo implementa T05 acá mismo.
def get_sample_set_assigner() -> SampleSetAssigner:
    return PendingSampleSetAssigner()
