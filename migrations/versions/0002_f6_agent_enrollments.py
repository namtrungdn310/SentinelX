"""Create agent_enrollments table for Milestone F6."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic
revision: str = "0002_f6_agent_enrollments"
down_revision: str | None = "0001_f5_projects_and_nodes"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create agent_enrollments table and indexes."""
    op.create_table(
        "agent_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("enrollment_token", name="uq_agent_enrollments_token"),
    )
    op.create_index("idx_agent_enrollments_node_id", "agent_enrollments", ["node_id"], unique=False)
    op.create_index("idx_agent_enrollments_status", "agent_enrollments", ["status"], unique=False)


def downgrade() -> None:
    """Drop agent_enrollments table."""
    op.drop_table("agent_enrollments")
