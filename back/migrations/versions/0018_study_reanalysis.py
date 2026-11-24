"""Reanálisis de estudios (EC-14): vínculo con el estudio de origen y descuento del presupuesto."""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = depends_on = None

# Copia de la 0017: si SQLite recrea la tabla sin el CHECK de estados, se vuelve a crear.
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


def _restore_status_check():
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    table_sql = bind.scalar(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'studies'")
    )
    if table_sql and STATUS_CONSTRAINT not in table_sql:
        allowed = ", ".join(f"'{status}'" for status in STUDY_STATUSES)
        with op.batch_alter_table("studies") as batch_op:
            batch_op.create_check_constraint(STATUS_CONSTRAINT, f"status IN ({allowed})")


def upgrade():
    with op.batch_alter_table("studies") as batch_op:
        batch_op.add_column(sa.Column("original_study_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_studies_original_study_id_studies", "studies", ["original_study_id"], ["id"]
        )
        batch_op.create_index("ix_studies_original_study_id", ["original_study_id"])
    _restore_status_check()
    with op.batch_alter_table("study_budgets") as batch_op:
        batch_op.add_column(
            sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade():
    with op.batch_alter_table("study_budgets") as batch_op:
        batch_op.drop_column("discount_cents")
    with op.batch_alter_table("studies") as batch_op:
        batch_op.drop_index("ix_studies_original_study_id")
        batch_op.drop_constraint("fk_studies_original_study_id_studies", type_="foreignkey")
        batch_op.drop_column("original_study_id")
    _restore_status_check()
