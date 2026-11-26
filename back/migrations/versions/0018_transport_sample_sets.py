"""Órdenes del día, paradas, retiros, sample sets y renombre del estado de muestra en viaje."""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = depends_on = None

ASSEMBLING_ONLY = sa.text("status = 'assembling'")
OLD_IN_TRANSIT = "in_transit_to_korea"
NEW_IN_TRANSIT = "in_transit_to_sequencing_lab"


def _rename_sample_status(old, new):
    params = {"old": old, "new": new}
    op.execute(sa.text("UPDATE samples SET status = :new WHERE status = :old").bindparams(**params))
    op.execute(sa.text("UPDATE sample_events SET from_status = :new WHERE from_status = :old").bindparams(**params))
    op.execute(sa.text("UPDATE sample_events SET to_status = :new WHERE to_status = :old").bindparams(**params))


def upgrade():
    op.create_table(
        "daily_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("province_id", sa.Integer(), sa.ForeignKey("provinces.id"), nullable=False),
        sa.Column("transporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("date", "province_id", name="uq_daily_routes_date_province"),
    )
    op.create_table(
        "route_stops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("daily_routes.id"), nullable=False),
        sa.Column("center_id", sa.Integer(), sa.ForeignKey("extraction_centers.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_stops_route_sequence"),
        sa.UniqueConstraint("route_id", "center_id", name="uq_route_stops_route_center"),
    )
    op.create_table(
        "route_pickups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stop_id", sa.Integer(), sa.ForeignKey("route_stops.id"), nullable=False),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("samples.id"), nullable=False, unique=True),
    )
    op.create_table(
        "sample_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("is_urgent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("csv_path", sa.String(255), nullable=True),
        sa.Column("authorization_pdf_path", sa.String(255), nullable=True),
        sa.Column("pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("courier_pickup_id", sa.String(36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("uq_sample_sets_assembling", "sample_sets", ["status"], unique=True,
                    sqlite_where=ASSEMBLING_ONLY, postgresql_where=ASSEMBLING_ONLY)
    op.create_table(
        "sample_set_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sample_set_id", sa.Integer(), sa.ForeignKey("sample_sets.id"), nullable=False),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("samples.id"), nullable=False, unique=True),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.UniqueConstraint("sample_set_id", "slot", name="uq_sample_set_items_set_slot"),
        sa.CheckConstraint("slot BETWEEN 1 AND 10", name="ck_sample_set_items_slot"),
    )
    _rename_sample_status(OLD_IN_TRANSIT, NEW_IN_TRANSIT)


def downgrade():
    _rename_sample_status(NEW_IN_TRANSIT, OLD_IN_TRANSIT)
    op.drop_table("sample_set_items")
    op.drop_index("uq_sample_sets_assembling", table_name="sample_sets")
    op.drop_table("sample_sets")
    op.drop_table("route_pickups")
    op.drop_table("route_stops")
    op.drop_table("daily_routes")
