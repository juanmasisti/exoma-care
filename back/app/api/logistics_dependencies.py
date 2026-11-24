"""Roles compartidos de transporte (T04), lotes (T05) y envío (T06)."""
from app.api.catalog_dependencies import require_roles
from app.domain.entities.roles import UserRole

# PROVISORIO (decisión 016, antes 009): el administrativo hace de transportista hasta que exista el rol
# transporter (Camila, EC-03). Cuando exista, se cambia esta línea y TRANSPORT_ROLES del front.
TRANSPORT_ROLES = (UserRole.LAB_ADMINISTRATOR,)
transporter = require_roles(*TRANSPORT_ROLES)
lab_administrator = require_roles(UserRole.LAB_ADMINISTRATOR)
