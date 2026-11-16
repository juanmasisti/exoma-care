"""Persist structured bioinformatics results on studies."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("studies") as batch:
        batch.add_column(sa.Column("variantes_detectadas", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("resultado_diagnostico", sa.String(20), nullable=True))
        batch.add_column(sa.Column("hallazgos_secundarios", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("fecha_reevaluacion", sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table("studies") as batch:
        batch.drop_column("fecha_reevaluacion")
        batch.drop_column("hallazgos_secundarios")
        batch.drop_column("resultado_diagnostico")
        batch.drop_column("variantes_detectadas")
