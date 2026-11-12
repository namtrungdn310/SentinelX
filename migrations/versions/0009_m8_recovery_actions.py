"""Create recovery_actions table for Milestone M8."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_m8_recovery_actions"
down_revision: str | None = "0008_m6_defense_actions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("defense_action_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["defense_action_id"],
            ["defense_actions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_recovery_actions_defense_action_id",
        "recovery_actions",
        ["defense_action_id"],
        unique=False,
    )
    op.create_index(
        "idx_recovery_actions_executed_at",
        "recovery_actions",
        ["executed_at"],
        unique=False,
    )
    op.create_index(
        "idx_recovery_actions_status",
        "recovery_actions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_recovery_actions_status", table_name="recovery_actions")
    op.drop_index("idx_recovery_actions_executed_at", table_name="recovery_actions")
    op.drop_index("idx_recovery_actions_defense_action_id", table_name="recovery_actions")
    op.drop_table("recovery_actions")
