"""Bounded retention owned by telemetry; operational audit records are untouched."""

from datetime import datetime

from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.telemetry.models import TelemetryMetricSampleModel
from sentinelx_controller.modules.telemetry.network_models import NetworkWindowModel


async def prune_telemetry(
    session: AsyncSession,
    metric_cutoff: datetime,
    network_cutoff: datetime,
    limit: int,
    *,
    apply: bool,
) -> dict[str, int]:
    metrics = list(
        (
            await session.execute(
                select(TelemetryMetricSampleModel.id)
                .where(TelemetryMetricSampleModel.received_at < metric_cutoff)
                .order_by(TelemetryMetricSampleModel.received_at, TelemetryMetricSampleModel.id)
                .limit(limit)
                .with_for_update(skip_locked=True),
            )
        )
        .scalars()
        .all()
    )
    windows = list(
        (
            await session.execute(
                select(NetworkWindowModel.node_id, NetworkWindowModel.window_id)
                .where(NetworkWindowModel.received_at < network_cutoff)
                .order_by(NetworkWindowModel.received_at)
                .limit(limit)
                .with_for_update(skip_locked=True),
            )
        ).all()
    )
    if apply:
        if metrics:
            await session.execute(
                delete(TelemetryMetricSampleModel).where(TelemetryMetricSampleModel.id.in_(metrics))
            )
        if windows:
            await session.execute(
                delete(NetworkWindowModel).where(
                    tuple_(NetworkWindowModel.node_id, NetworkWindowModel.window_id).in_(windows),
                )
            )
    return {"metrics": len(metrics), "network_windows": len(windows)}
