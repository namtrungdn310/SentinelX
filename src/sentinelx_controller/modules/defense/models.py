"""SQLAlchemy model for DefenseAction in SentinelX."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class DefenseActionModel(Base):
    """Database model storing defense actions dispatched to agents."""

    __tablename__ = "defense_actions"
    __table_args__ = (
        Index("idx_defense_actions_node_status", "node_id", "status"),
        Index("idx_defense_actions_created_at", "created_at"),
        Index("idx_defense_actions_incident_id", "incident_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("defense_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    target_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    command_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
    )
    agent_ack_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
