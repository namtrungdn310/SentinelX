"""SQLAlchemy model for Node entity."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelx_common.contracts.agents import EnrollmentStatus
from sentinelx_common.contracts.nodes import NodeStatus
from sentinelx_controller.infrastructure.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sentinelx_controller.modules.projects.models import ProjectModel


class NodeModel(Base, TimestampMixin):
    """Database table storing managed Linux nodes."""

    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("project_id", "ip_address", name="uq_node_project_ip"),
        Index("idx_nodes_status", "status"),
        Index("idx_nodes_project_id", "project_id"),
    )

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
    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )
    os_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    agent_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=NodeStatus.UNENROLLED.value,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project: Mapped["ProjectModel"] = relationship(
        "ProjectModel",
        back_populates="nodes",
    )
    enrollments: Mapped[list["AgentEnrollmentModel"]] = relationship(
        "AgentEnrollmentModel",
        back_populates="node",
        cascade="all, delete-orphan",
    )


class AgentEnrollmentModel(Base, TimestampMixin):
    """Database table storing agent enrollment tokens and their lifecycle."""

    __tablename__ = "agent_enrollments"
    __table_args__ = (
        UniqueConstraint("enrollment_token", name="uq_agent_enrollments_token"),
        Index("idx_agent_enrollments_node_id", "node_id"),
        Index("idx_agent_enrollments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrollment_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=EnrollmentStatus.PENDING.value,
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    node: Mapped["NodeModel"] = relationship(
        "NodeModel",
        back_populates="enrollments",
    )

