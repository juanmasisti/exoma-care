"""Persist notification delivery references for audit."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aviso_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("referencia", sa.Text(), nullable=True),
        sa.Column("asunto", sa.String(length=200), nullable=False),
        sa.Column("estado_inicial", sa.String(length=20), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("aviso_id"),
        sa.UniqueConstraint("idempotency_key"),
    )

def downgrade():
    op.drop_table("notification_logs")
