"""SQLAlchemy model for Project entity."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelx_controller.infrastructure.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sentinelx_controller.modules.nodes.models import NodeModel


class ProjectModel(Base, TimestampMixin):
    """Bảng lưu trữ thông tin phân vùng dự án/hạ tầng."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    nodes: Mapped[list["NodeModel"]] = relationship(
        "NodeModel",
        back_populates="project",
        cascade="all, delete-orphan",
    )
