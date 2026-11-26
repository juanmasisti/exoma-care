"""Provincias, centros de extracción y feriados del turnero."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "provinces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(60), unique=True, nullable=False),
    )
    op.create_table(
        "extraction_centers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(200), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province_id", sa.Integer(), sa.ForeignKey("provinces.id"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("province_id", "name", name="uq_extraction_center_province_name"),
    )
    op.create_index("ix_extraction_centers_province_id", "extraction_centers", ["province_id"])
    op.create_table(
        "holidays",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("description", sa.String(120), nullable=False),
    )


def downgrade():
    op.drop_table("holidays")
    op.drop_index("ix_extraction_centers_province_id", table_name="extraction_centers")
    op.drop_table("extraction_centers")
    op.drop_table("provinces")
