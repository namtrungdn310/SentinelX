"""Add optional per-project Load Balancer config and node LB backend role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_lb_control_plane"
down_revision: str | None = "0010_core_reliability"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("lb_config", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "nodes",
        sa.Column("lb_role", sa.String(20), nullable=False, server_default="standalone"),
    )
    op.add_column(
        "nodes",
        sa.Column("lb_backend_port", sa.Integer(), nullable=False, server_default="8080"),
    )
    op.add_column(
        "nodes",
        sa.Column("lb_health_path", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("nodes", "lb_health_path")
    op.drop_column("nodes", "lb_backend_port")
    op.drop_column("nodes", "lb_role")
    op.drop_column("projects", "lb_config")
