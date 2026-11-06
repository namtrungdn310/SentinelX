"""Persistence of aggregate windows only; no packet/payload tables."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class NetworkWindowModel(Base):
    __tablename__ = "telemetry_network_windows"
    __table_args__ = (Index("idx_network_node_time", "node_id", "window_end"),)

    node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    window_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interface: Mapped[str] = mapped_column(String(64))
    features: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    omitted_packets: Mapped[int] = mapped_column(BigInteger)
    skipped_windows: Mapped[int] = mapped_column(BigInteger)
