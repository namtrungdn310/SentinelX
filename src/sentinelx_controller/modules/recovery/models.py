"""SQLAlchemy ORM models for Recovery module."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class RecoveryActionModel(Base):
    """Database model for recovery and unblock audit records."""

    __tablename__ = "recovery_actions"
    __table_args__ = (
        Index("idx_recovery_actions_defense_action_id", "defense_action_id"),
        Index("idx_recovery_actions_executed_at", "executed_at"),
        Index("idx_recovery_actions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    defense_action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("defense_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
