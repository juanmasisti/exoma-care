"""Add the Super Admin role to existing databases."""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade():
    # PostgreSQL cannot safely remove an enum value that may already be in use.
    pass
