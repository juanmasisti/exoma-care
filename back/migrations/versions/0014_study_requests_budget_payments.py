"""Study request, budget, coverage, financial operations and coupons (EC-10 to EC-13)."""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("studies") as batch:
        batch.add_column(sa.Column("physician_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "include_secondary_findings",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch.create_foreign_key(
            "fk_studies_physician_id_users", "users", ["physician_id"], ["id"]
        )
        batch.create_index("ix_studies_physician_id", ["physician_id"])

    op.create_table(
        "study_pathologies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.UniqueConstraint("study_id", "code", name="uq_study_pathologies_study_code"),
    )
    op.create_index("ix_study_pathologies_study_id", "study_pathologies", ["study_id"])

    op.create_table(
        "study_genes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.UniqueConstraint("study_id", "symbol", name="uq_study_genes_study_symbol"),
    )
    op.create_index("ix_study_genes_study_id", "study_genes", ["study_id"])

    op.create_table(
        "study_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("gene_count", sa.Integer(), nullable=False),
        sa.Column("base_cents", sa.Integer(), nullable=False),
        sa.Column("extra_genes", sa.Integer(), nullable=False),
        sa.Column("extra_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("issued_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_mode", sa.String(length=20), nullable=True),
        sa.Column("insurer_external_id", sa.String(length=64), nullable=True),
        sa.Column("insurer_name", sa.String(length=200), nullable=True),
        sa.Column("coverage_percent", sa.Float(), nullable=True),
        sa.Column("insurer_cents", sa.Integer(), nullable=True),
        sa.Column("patient_cents", sa.Integer(), nullable=True),
        sa.UniqueConstraint("study_id", name="uq_study_budgets_study"),
    )

    op.create_table(
        "coverage_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("study_budgets.id"), nullable=False),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("insurer_external_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("authorize_url", sa.String(length=500), nullable=False),
        sa.Column("reject_url", sa.String(length=500), nullable=False),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("demands_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("budget_id", name="uq_coverage_requests_budget"),
        sa.UniqueConstraint("study_id", name="uq_coverage_requests_study"),
        sa.UniqueConstraint("external_id", name="uq_coverage_requests_external_id"),
    )

    op.create_table(
        "coverage_demands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coverage_id", sa.Integer(), sa.ForeignKey("coverage_requests.id"), nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coverage_demands_coverage_id", "coverage_demands", ["coverage_id"])

    op.create_table(
        "financial_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("study_budgets.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coupon_code", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=True),
        sa.Column("insurer_external_id", sa.String(length=64), nullable=True),
        sa.Column("insurer_name", sa.String(length=200), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("budget_id", "type", name="uq_financial_operations_budget_type"),
    )
    op.create_index("ix_financial_operations_study_id", "financial_operations", ["study_id"])
    op.create_index("ix_financial_operations_patient_id", "financial_operations", ["patient_id"])

    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("medico_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("redeemed_study_id", sa.Integer(), sa.ForeignKey("studies.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
    )
    op.create_index("ix_coupons_status", "coupons", ["status"])
    op.create_index("ix_coupons_medico_id", "coupons", ["medico_id"])
    op.create_index("ix_coupons_patient_id", "coupons", ["patient_id"])


def downgrade():
    op.drop_index("ix_coupons_patient_id", table_name="coupons")
    op.drop_index("ix_coupons_medico_id", table_name="coupons")
    op.drop_index("ix_coupons_status", table_name="coupons")
    op.drop_table("coupons")
    op.drop_index("ix_financial_operations_patient_id", table_name="financial_operations")
    op.drop_index("ix_financial_operations_study_id", table_name="financial_operations")
    op.drop_table("financial_operations")
    op.drop_index("ix_coverage_demands_coverage_id", table_name="coverage_demands")
    op.drop_table("coverage_demands")
    op.drop_table("coverage_requests")
    op.drop_table("study_budgets")
    op.drop_index("ix_study_genes_study_id", table_name="study_genes")
    op.drop_table("study_genes")
    op.drop_index("ix_study_pathologies_study_id", table_name="study_pathologies")
    op.drop_table("study_pathologies")
    with op.batch_alter_table("studies") as batch:
        batch.drop_index("ix_studies_physician_id")
        batch.drop_constraint("fk_studies_physician_id_users", type_="foreignkey")
        batch.drop_column("include_secondary_findings")
        batch.drop_column("physician_id")
