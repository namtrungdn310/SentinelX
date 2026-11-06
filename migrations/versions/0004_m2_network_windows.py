"""Store bounded, idempotent network observation windows for M2."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004_m2_network_windows"
down_revision: str | None = "0003_f8_telemetry_metric_samples"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_network_windows",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interface", sa.String(64), nullable=False),
        sa.Column("features", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("omitted_packets", sa.BigInteger(), nullable=False),
        sa.Column("skipped_windows", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("node_id", "window_id"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_network_node_time", "telemetry_network_windows", ["node_id", "window_end"])


def downgrade() -> None:
    op.drop_table("telemetry_network_windows")
