"""PROVISORIO: tabla mínima de estudios para destrabar turnos (la amplía el área de estudios)."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "studies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_studies_patient_id", "studies", ["patient_id"])


def downgrade():
    op.drop_index("ix_studies_patient_id", table_name="studies")
    op.drop_table("studies")
