"""SQLAlchemy models for Incidents module."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class IncidentModel(Base):
    """Database model storing security incidents."""

    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_project_status", "project_id", "status"),
        Index("idx_incidents_project_started", "project_id", "started_at"),
        Index(
            "uq_active_incident_context",
            "node_id",
            "correlation_key",
            unique=True,
            postgresql_where=text("status IN ('DETECTED','MITIGATING')"),
            sqlite_where=text("status IN ('DETECTED','MITIGATING')"),
        ),
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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="DETECTED",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="SET NULL"),
    )
    correlation_key: Mapped[str | None] = mapped_column(String(100))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
