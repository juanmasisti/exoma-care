"""Persist analyst claims and completed study results."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("studies") as batch:
        batch.add_column(sa.Column("analyst_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("result_json", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_studies_analyst_id_users",
            "users",
            ["analyst_id"],
            ["id"],
        )
    op.create_index("ix_studies_analyst_id", "studies", ["analyst_id"])


def downgrade():
    op.drop_index("ix_studies_analyst_id", table_name="studies")
    with op.batch_alter_table("studies") as batch:
        batch.drop_constraint("fk_studies_analyst_id_users", type_="foreignkey")
        batch.drop_column("result_json")
        batch.drop_column("analyst_id")
