"""Roles y enganches compartidos de transporte (T04), lotes (T05) y envío (T06)."""
from datetime import datetime

from app.api.catalog_dependencies import require_roles
from app.domain.entities.roles import UserRole
from app.domain.interfaces.sample_set_hooks import SampleSetAssigner, SampleSetClosedHandler

# PROVISORIO (decisión 016, antes 009): el administrativo hace de transportista hasta que exista el rol
# transporter (Camila, EC-03). Cuando exista, se cambia esta línea y TRANSPORT_ROLES del front.
TRANSPORT_ROLES = (UserRole.LAB_ADMINISTRATOR,)
transporter = require_roles(*TRANSPORT_ROLES)
lab_administrator = require_roles(UserRole.LAB_ADMINISTRATOR)


class PendingSampleSetAssigner:
    """PROVISORIO hasta T05: la llegada no arma lotes todavía."""

    def asignar_a_sample_set(self, sample_id: int, now: datetime) -> None:
        pass


class PendingSampleSetClosedHandler:
    """PROVISORIO hasta T06: cerrar un lote no pide la autorización todavía."""

    def al_cerrar_lote(self, sample_set_id: int, now: datetime) -> None:
        pass


# T05 reemplaza esta función por la que arma lotes; T06, la de abajo. Nadie más toca este archivo.
def get_sample_set_assigner() -> SampleSetAssigner:
    return PendingSampleSetAssigner()


def get_sample_set_closed_handler() -> SampleSetClosedHandler:
    return PendingSampleSetClosedHandler()
