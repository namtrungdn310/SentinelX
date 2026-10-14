"""Repository for telemetry metric samples persistence."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.telemetry.models import TelemetryMetricSampleModel


class TelemetryRepository:
    """Handle database operations for Telemetry metric samples."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_batch(
        self,
        node_id: uuid.UUID,
        received_at: datetime,
        samples: list[MetricSample],
    ) -> int:
        """Persist a batch of metric samples for a node."""
        models = [
            TelemetryMetricSampleModel(
                node_id=node_id,
                observed_at=sample.observed_at,
                received_at=received_at,
                cpu_usage_pct=sample.cpu_percent,
                memory_usage_pct=sample.memory_percent,
                disk_usage_pct=sample.disk_percent,
                network_rx_bytes=sample.network_rx_bytes,
                network_tx_bytes=sample.network_tx_bytes,
            )
            for sample in samples
        ]
        self._session.add_all(models)
        await self._session.flush()
        return len(models)

    async def query_by_node(
        self,
        node_id: uuid.UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[TelemetryMetricSampleModel]:
        """Query metric samples for a node ordered by observed_at descending."""
        stmt = select(TelemetryMetricSampleModel).where(
            TelemetryMetricSampleModel.node_id == node_id
        )

        if start_time is not None:
            stmt = stmt.where(TelemetryMetricSampleModel.observed_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(TelemetryMetricSampleModel.observed_at <= end_time)

        stmt = stmt.order_by(TelemetryMetricSampleModel.observed_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()
