"""SQLAlchemy model for Telemetry metric samples."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from sentinelx_controller.infrastructure.database.base import Base


class TelemetryMetricSampleModel(Base):
    """Database table storing time-series metric measurements from nodes."""

    __tablename__ = "telemetry_metric_samples"
    __table_args__ = (
        Index("idx_telemetry_node_time", "node_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    cpu_usage_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    memory_usage_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    disk_usage_pct: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    network_rx_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    network_tx_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
