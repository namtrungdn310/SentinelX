"""SQLAlchemy model for Node entity."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelx_common.contracts.nodes import NodeStatus
from sentinelx_controller.infrastructure.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sentinelx_controller.modules.projects.models import ProjectModel


class NodeModel(Base, TimestampMixin):
    """Bảng lưu trữ danh bạ máy chủ Linux được quản trị."""

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
