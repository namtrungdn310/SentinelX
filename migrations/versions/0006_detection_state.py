"""Persist detection cursors, windows and cooldown in the ingestion transaction."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_detection_state"
down_revision: str = "0005_merge_m2_m3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detection_node_state",
        sa.Column("node_id", sa.Uuid(), primary_key=True),
        sa.Column("state", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("detection_node_state")
