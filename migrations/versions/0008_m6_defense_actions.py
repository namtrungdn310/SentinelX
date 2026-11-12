"""Create defense_actions table for Milestone M6."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_m6_defense_actions"
down_revision: str | None = "0007_m5_incidents_and_policies"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "defense_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("policy_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("node_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("target_ip", sa.String(length=45), nullable=True),
        sa.Column("command_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("agent_ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["defense_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_defense_actions_node_status",
        "defense_actions",
        ["node_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_defense_actions_created_at",
        "defense_actions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_defense_actions_incident_id",
        "defense_actions",
        ["incident_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_defense_actions_incident_id", table_name="defense_actions")
    op.drop_index("idx_defense_actions_created_at", table_name="defense_actions")
    op.drop_index("idx_defense_actions_node_status", table_name="defense_actions")
    op.drop_table("defense_actions")
