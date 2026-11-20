"""SQLAlchemy models for Defense Policy and IP Whitelist."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from sentinelx_controller.infrastructure.database.base import Base


class IPWhitelistModel(Base):
    """Database model for project IP whitelist entries."""

    __tablename__ = "ip_whitelist"
    __table_args__ = (Index("idx_ip_whitelist_project", "project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    ip_or_cidr: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class DefensePolicyModel(Base):
    """Database model for automatic defense policies."""

    __tablename__ = "defense_policies"
    __table_args__ = (Index("idx_defense_policies_project_event", "project_id", "event_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    target_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=dict,
    )
    is_auto_execute: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
    )
    block_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1800,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=100)


class PolicyExecutionStateModel(Base):
    """Transaction-owned cooldown, scoped to node/policy/target."""

    __tablename__ = "policy_execution_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        index=True,
    )
    last_authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class PolicyDecisionModel(Base):
    """Immutable snapshot explaining each real policy decision."""

    __tablename__ = "policy_decisions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    event_id: Mapped[str] = mapped_column(String(36))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
