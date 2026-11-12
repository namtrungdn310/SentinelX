"""Create incidents, defense_policies, and ip_whitelist tables for Milestone M5."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_m5_incidents_and_policies"
down_revision: str | None = "0006_detection_state"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="DETECTED", nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_incidents_project_status",
        "incidents",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_incidents_project_started",
        "incidents",
        ["project_id", "started_at"],
        unique=False,
    )

    # 2. Add foreign key constraint to detection_events.incident_id
    with op.batch_alter_table("detection_events") as batch_op:
        batch_op.create_foreign_key(
            "fk_detection_events_incident_id",
            "incidents",
            ["incident_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 3. Create ip_whitelist table
    op.create_table(
        "ip_whitelist",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ip_or_cidr", sa.String(length=45), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_ip_whitelist_project",
        "ip_whitelist",
        ["project_id"],
        unique=False,
    )

    # 4. Create defense_policies table
    op.create_table(
        "defense_policies",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column(
            "target_params",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("is_auto_execute", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("block_duration_seconds", sa.Integer(), server_default="1800", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_defense_policies_project_event",
        "defense_policies",
        ["project_id", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_defense_policies_project_event", table_name="defense_policies")
    op.drop_table("defense_policies")

    op.drop_index("idx_ip_whitelist_project", table_name="ip_whitelist")
    op.drop_table("ip_whitelist")

    with op.batch_alter_table("detection_events") as batch_op:
        batch_op.drop_constraint("fk_detection_events_incident_id", type_="foreignkey")

    op.drop_index("idx_incidents_project_started", table_name="incidents")
    op.drop_index("idx_incidents_project_status", table_name="incidents")
    op.drop_table("incidents")
