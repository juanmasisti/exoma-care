"""Link local definitions to explicitly selected external identities."""
from alembic import op
import sqlalchemy as sa
revision = "0015"
down_revision = "0014"
branch_labels = depends_on = None

def upgrade():
    with op.batch_alter_table("pathologies") as batch:
        batch.add_column(sa.Column("apigen_code", sa.String(100), nullable=True))
        batch.add_column(sa.Column("apigen_group", sa.String(50), nullable=True))
        batch.add_column(sa.Column("cdss_code", sa.String(100), nullable=True))
        batch.create_unique_constraint("uq_pathology_apigen_identity", ["apigen_code", "apigen_group"])
        batch.create_unique_constraint("uq_pathology_cdss_code", ["cdss_code"])

def downgrade():
    with op.batch_alter_table("pathologies") as batch:
        batch.drop_constraint("uq_pathology_apigen_identity", type_="unique")
        batch.drop_constraint("uq_pathology_cdss_code", type_="unique")
        batch.drop_column("cdss_code")
        batch.drop_column("apigen_group")
        batch.drop_column("apigen_code")
