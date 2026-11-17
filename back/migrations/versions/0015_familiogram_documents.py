"""Versioned familiogram documents and explicit family drawing data."""
from alembic import op
import sqlalchemy as sa
revision = "0015"
down_revision = "0014"
branch_labels = depends_on = None

def upgrade():
    op.add_column("family_members", sa.Column("diagram_details", sa.JSON(), nullable=True))
    op.create_table("familiogram_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_version", sa.Integer(), nullable=False),
        sa.Column("family_version", sa.Integer(), nullable=False),
        sa.Column("created_by_physician_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("svg", sa.LargeBinary(), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False))
    op.create_index("ix_familiogram_documents_patient_id", "familiogram_documents", ["patient_id"])

def downgrade():
    op.drop_table("familiogram_documents")
    op.drop_column("family_members", "diagram_details")
