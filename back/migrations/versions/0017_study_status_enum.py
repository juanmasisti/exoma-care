"""Constrain study statuses to the domain enum values."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = depends_on = None

STUDY_STATUSES = (
    "creado",
    "pendiente_pago",
    "pendiente_autorizacion",
    "pagado",
    "autorizado",
    "rechazado",
    "turno_sacado",
    "listo_para_retirar",
    "requiere_remuestreo",
    "en_viaje_a_corea",
    "en_area_bioinformatica",
    "en_analisis",
    "resultado_disponible",
)
STATUS_CONSTRAINT = "ck_studies_status_valid"


def upgrade():
    bind = op.get_bind()
    existing_statuses = set(
        bind.execute(sa.text("SELECT DISTINCT status FROM studies")).scalars()
    )
    invalid_statuses = existing_statuses.difference(STUDY_STATUSES)
    if invalid_statuses:
        raise RuntimeError(
            "No se puede restringir el estado de estudios: "
            f"hay valores no reconocidos {sorted(invalid_statuses)}."
        )

    allowed_statuses = ", ".join(f"'{status}'" for status in STUDY_STATUSES)
    with op.batch_alter_table("studies") as batch_op:
        batch_op.create_check_constraint(
            STATUS_CONSTRAINT,
            f"status IN ({allowed_statuses})",
        )


def downgrade():
    with op.batch_alter_table("studies") as batch_op:
        batch_op.drop_constraint(STATUS_CONSTRAINT, type_="check")
