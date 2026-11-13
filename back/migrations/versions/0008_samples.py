"""Muestras, avisos del bot de extracción e historial de muestras."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None

CURRENT_ONLY = sa.text("is_current")


def upgrade():
    op.create_table(
        "extraction_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(100), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("extraction_notice_id", sa.Integer(), sa.ForeignKey("extraction_notices.id"), nullable=False,
                  unique=True),
        sa.Column("volume_ml", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
    )
    op.create_index("uq_samples_study_current", "samples", ["study_id"], unique=True,
                    sqlite_where=CURRENT_ONLY, postgresql_where=CURRENT_ONLY)
    op.create_table(
        "sample_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("samples.id"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("sample_events")
    op.drop_index("uq_samples_study_current", table_name="samples")
    op.drop_table("samples")
    op.drop_table("extraction_notices")
