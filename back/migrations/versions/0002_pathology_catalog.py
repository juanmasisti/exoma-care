"""Catálogo de patologías y conceptos de terminología."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "symptoms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("code_system", sa.String(50), nullable=False),
        sa.UniqueConstraint("code_system", "code", name="uq_symptom_code"),
    )
    op.create_table(
        "pathologies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), unique=True, nullable=False),
        sa.Column("cardinal_symptom_id", sa.Integer(), sa.ForeignKey("symptoms.id"), nullable=False),
    )
    op.create_table(
        "pathology_secondary_symptoms",
        sa.Column("pathology_id", sa.Integer(), sa.ForeignKey("pathologies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symptom_id", sa.Integer(), sa.ForeignKey("symptoms.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("pathology_secondary_symptoms")
    op.drop_table("pathologies")
    op.drop_table("symptoms")
