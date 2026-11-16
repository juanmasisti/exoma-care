"""Persist the pathology code selected for a bioinformatics study."""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("studies") as batch:
        batch.add_column(sa.Column("codigo_patologia", sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table("studies") as batch:
        batch.drop_column("codigo_patologia")
