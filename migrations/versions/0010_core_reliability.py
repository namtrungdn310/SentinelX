"""Durable command leases, outcomes, cooldowns and bounded recovery attempts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_core_reliability"
down_revision: str | None = "0009_m8_recovery_actions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nodes", sa.Column("agent_capabilities", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_index("idx_telemetry_retention", "telemetry_metric_samples", ["received_at"])
    op.create_index("idx_network_retention", "telemetry_network_windows", ["received_at"])
    op.add_column(
        "defense_policies",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "incidents", sa.Column("node_id", sa.Uuid(), sa.ForeignKey("nodes.id", ondelete="SET NULL"))
    )
    op.add_column("incidents", sa.Column("correlation_key", sa.String(100)))
    op.add_column("incidents", sa.Column("last_event_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE incidents SET last_event_at=started_at")
    op.create_index(
        "uq_active_incident_context",
        "incidents",
        ["node_id", "correlation_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('DETECTED','MITIGATING')"),
        sqlite_where=sa.text("status IN ('DETECTED','MITIGATING')"),
    )
    op.add_column("defense_actions", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("defense_actions", sa.Column("leased_until", sa.DateTime(timezone=True)))
    op.add_column("defense_actions", sa.Column("delivery_token", sa.String(64)))
    op.add_column(
        "defense_actions", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("defense_actions", sa.Column("applied_at", sa.DateTime(timezone=True)))
    op.add_column("defense_actions", sa.Column("executed_at", sa.DateTime(timezone=True)))
    op.add_column("defense_actions", sa.Column("effective_until", sa.DateTime(timezone=True)))
    op.add_column(
        "defense_actions",
        sa.Column("execution_metadata", sa.JSON(), nullable=False, server_default="{}"),
    )
    # Never silently re-deliver legacy commands without identity/expiry protection.
    op.execute("UPDATE defense_actions SET status='EXPIRED' WHERE status IN ('PENDING','SENT')")
    op.execute("UPDATE defense_actions SET expires_at=created_at")
    op.execute("UPDATE defense_actions SET applied_at=agent_ack_at WHERE status='APPLIED'")
    op.create_table(
        "policy_execution_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column(
            "node_id", sa.Uuid(), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("last_authorized_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_policy_execution_state_node_id", "policy_execution_state", ["node_id"])
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "node_id", sa.Uuid(), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )
    op.create_index("ix_policy_decisions_node_id", "policy_decisions", ["node_id"])
    op.create_index("ix_policy_decisions_created_at", "policy_decisions", ["created_at"])
    op.create_index(
        "ix_policy_execution_state_last_authorized_at",
        "policy_execution_state",
        ["last_authorized_at"],
    )
    op.add_column(
        "recovery_actions", sa.Column("attempts", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("recovery_actions", sa.Column("next_retry_at", sa.DateTime(timezone=True)))
    op.add_column("recovery_actions", sa.Column("error_message", sa.String(1000)))
    op.add_column("recovery_actions", sa.Column("command_id", sa.Uuid()))
    op.add_column("recovery_actions", sa.Column("incident_id", sa.Uuid()))
    op.add_column("recovery_actions", sa.Column("node_id", sa.Uuid()))
    op.add_column(
        "recovery_actions",
        sa.Column("resolution_done", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_recovery_actions_incident_id", "recovery_actions", ["incident_id"])
    # Historical duplicate attempts are retained; only the newest remains pending.
    op.execute("""UPDATE recovery_actions SET status='FAILED'
        WHERE status='PENDING' AND id IN (
            SELECT id FROM (SELECT id, row_number() OVER (
                PARTITION BY defense_action_id ORDER BY executed_at DESC, id DESC
            ) AS ordinal FROM recovery_actions WHERE status='PENDING') AS ranked
            WHERE ordinal > 1
        )""")
    op.create_index(
        "uq_recovery_pending",
        "recovery_actions",
        ["defense_action_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_column("nodes", "agent_capabilities")
    op.drop_index("idx_telemetry_retention", table_name="telemetry_metric_samples")
    op.drop_index("idx_network_retention", table_name="telemetry_network_windows")
    op.drop_column("defense_policies", "priority")
    op.drop_index("uq_active_incident_context", table_name="incidents")
    for column in ("last_event_at", "correlation_key", "node_id"):
        op.drop_column("incidents", column)
    op.drop_index("ix_recovery_actions_incident_id", table_name="recovery_actions")
    op.drop_index("uq_recovery_pending", table_name="recovery_actions")
    for column in (
        "resolution_done",
        "node_id",
        "incident_id",
        "command_id",
        "error_message",
        "next_retry_at",
        "attempts",
    ):
        op.drop_column("recovery_actions", column)
    op.drop_table("policy_decisions")
    op.drop_table("policy_execution_state")
    for column in (
        "execution_metadata",
        "effective_until",
        "executed_at",
        "applied_at",
        "attempts",
        "delivery_token",
        "leased_until",
        "expires_at",
    ):
        op.drop_column("defense_actions", column)
