"""Create detection_events table for Milestone M3."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_m3_detection_events"
down_revision: str | None = "0003_f8_telemetry_metric_samples"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create detection_events table and composite index."""
    op.create_table(
        "detection_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("node_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("detector_name", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("attacker_ip", sa.String(length=45), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_detection_events_node_time",
        "detection_events",
        ["node_id", "detected_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop detection_events table."""
    op.drop_index("idx_detection_events_node_time", table_name="detection_events")
    op.drop_table("detection_events")
