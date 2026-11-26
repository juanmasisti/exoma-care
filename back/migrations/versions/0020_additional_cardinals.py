"""Additional cardinal criteria, preserving the original cardinal and snapshots."""
from alembic import op
import sqlalchemy as sa
revision = "0020"
down_revision = "0019"
branch_labels = depends_on = None

def upgrade():
    op.create_table("pathology_additional_cardinals",
        sa.Column("pathology_id", sa.Integer(), sa.ForeignKey("pathologies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symptom_id", sa.Integer(), sa.ForeignKey("symptoms.id"), primary_key=True))

def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM pathology_additional_cardinals")).scalar():
        raise RuntimeError("No se puede quitar la migración mientras existan cardinales adicionales.")
    op.drop_table("pathology_additional_cardinals")
