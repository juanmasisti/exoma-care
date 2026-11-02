"""Antecedentes familiares opcionales y revisiones independientes de la clínica."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.create_table("patient_family_records",
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_physician_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False))
    op.create_table("family_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient_family_records.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("relationship", sa.String(32), nullable=False),
        sa.Column("relationship_detail", sa.String(100), nullable=False),
        sa.Column("diagnosis_status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False))
    op.create_index("ix_family_members_patient_id", "family_members", ["patient_id"])
    op.create_table("family_member_symptoms",
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symptom_id", sa.Integer(), sa.ForeignKey("symptoms.id"), primary_key=True))
    op.create_table("family_member_diagnoses",
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pathology_id", sa.Integer(), sa.ForeignKey("pathologies.id"), primary_key=True))
    op.create_table("patient_family_revisions",
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient_family_records.patient_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("changed_by_physician_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("members", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("patient_family_revisions")
    op.drop_table("family_member_diagnoses")
    op.drop_table("family_member_symptoms")
    op.drop_index("ix_family_members_patient_id", table_name="family_members")
    op.drop_table("family_members")
    op.drop_table("patient_family_records")
