"""Turnos de extracción."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None

BOOKED_ONLY = sa.text("status = 'booked'")


def upgrade():
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("center_id", sa.Integer(), sa.ForeignKey("extraction_centers.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("study_status_before", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_appointments_center_slot_booked", "appointments", ["center_id", "starts_at"], unique=True,
                    sqlite_where=BOOKED_ONLY, postgresql_where=BOOKED_ONLY)
    op.create_index("uq_appointments_study_booked", "appointments", ["study_id"], unique=True,
                    sqlite_where=BOOKED_ONLY, postgresql_where=BOOKED_ONLY)


def downgrade():
    op.drop_index("uq_appointments_study_booked", table_name="appointments")
    op.drop_index("uq_appointments_center_slot_booked", table_name="appointments")
    op.drop_table("appointments")
