"""Esquema de usuarios y pacientes recibido de la base de arquitectura."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("role", sa.Enum("treating_physician", "lab_administrator", "bioinformatician",
                                 "patient", "medical_manager", name="user_role"), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("license_number", sa.String(50)),
        sa.Column("specialty", sa.String(100)),
        sa.Column("national_id", sa.String(30), unique=True),
        sa.Column("date_of_birth", sa.Date()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dni", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("apellido", sa.String(100), nullable=False),
        sa.Column("fecha_nacimiento", sa.Date()),
        sa.Column("telefono", sa.String(30)),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_patients_dni", "patients", ["dni"], unique=True)
    op.create_index("ix_patients_usuario_id", "patients", ["usuario_id"], unique=True)


def downgrade():
    op.drop_table("patients")
    op.drop_table("users")
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
