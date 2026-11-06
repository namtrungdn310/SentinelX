"""Join the independently deployed M2 and M3 migration branches."""

from collections.abc import Sequence

revision: str = "0005_merge_m2_m3"
down_revision: tuple[str, str] = ("0004_m2_network_windows", "0004_m3_detection_events")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
