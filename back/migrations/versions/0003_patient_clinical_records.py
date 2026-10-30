"""Datos clínicos, sospechas y evidencia histórica; acceso del paciente separado."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    # Nullable conserva pacientes heredados sin inventar historia ni médico creador.
    with op.batch_alter_table("patients") as batch:
        batch.alter_column("usuario_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("created_by_physician_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("email", sa.String(255), nullable=True))
        batch.add_column(sa.Column("clinical_summary", sa.Text(), nullable=True))
        batch.add_column(sa.Column("suspicion_type", sa.String(16), nullable=True))
        batch.add_column(sa.Column("family_history", sa.Text(), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_patient_created_by", "users", ["created_by_physician_id"], ["id"])
        batch.create_index("ix_patients_created_by_physician_id", ["created_by_physician_id"])
    op.create_table("patient_pathologies",
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pathology_id", sa.Integer(), sa.ForeignKey("pathologies.id"), primary_key=True))
    op.create_table("patient_symptoms",
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symptom_id", sa.Integer(), sa.ForeignKey("symptoms.id"), primary_key=True))
    op.create_table("patient_clinical_revisions",
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("changed_by_physician_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False))


def downgrade():
    # Volver a exigir cuenta no es posible sin inventar cuentas para las altas nuevas.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM patients WHERE usuario_id IS NULL")):
        raise RuntimeError("Hay pacientes con acceso pendiente. No se revierte sin resolver sus cuentas y respaldar la información clínica.")
    op.drop_table("patient_clinical_revisions")
    op.drop_table("patient_symptoms")
    op.drop_table("patient_pathologies")
    with op.batch_alter_table("patients") as batch:
        batch.drop_index("ix_patients_created_by_physician_id")
        batch.drop_constraint("fk_patient_created_by", type_="foreignkey")
        for name in ("created_by_physician_id", "email", "clinical_summary", "suspicion_type", "family_history", "version", "created_at", "updated_at"):
            batch.drop_column(name)
        batch.alter_column("usuario_id", existing_type=sa.Integer(), nullable=False)
