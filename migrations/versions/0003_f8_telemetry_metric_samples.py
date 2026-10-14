"""Create telemetry_metric_samples table for Milestone F8."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic
revision: str = "0003_f8_telemetry_metric_samples"
down_revision: str | None = "0002_f6_agent_enrollments"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create telemetry_metric_samples table and index."""
    op.create_table(
        "telemetry_metric_samples",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cpu_usage_pct", sa.Float(), nullable=False),
        sa.Column("memory_usage_pct", sa.Float(), nullable=False),
        sa.Column("disk_usage_pct", sa.Float(), nullable=True),
        sa.Column("network_rx_bytes", sa.BigInteger(), server_default="0", nullable=True),
        sa.Column("network_tx_bytes", sa.BigInteger(), server_default="0", nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_telemetry_node_time",
        "telemetry_metric_samples",
        ["node_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop telemetry_metric_samples table."""
    op.drop_table("telemetry_metric_samples")
