"""SQLAlchemy ORM models for Recovery module."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class RecoveryActionModel(Base):
    """Database model for recovery and unblock audit records."""

    __tablename__ = "recovery_actions"
    __table_args__ = (
        Index("idx_recovery_actions_defense_action_id", "defense_action_id"),
        Index("idx_recovery_actions_executed_at", "executed_at"),
        Index("idx_recovery_actions_status", "status"),
        Index(
            "uq_recovery_pending",
            "defense_action_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
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
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    command_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    node_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    resolution_done: Mapped[bool] = mapped_column(Boolean, default=False)
