"""Idempotent ingestion and bounded time-range queries for network windows."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.network import NetworkWindow
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.modules.telemetry.network_models import NetworkWindowModel


class NetworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self, node_id: UUID, windows: list[NetworkWindow], received_at: datetime
    ) -> list[NetworkWindow]:
        insert = sqlite_insert if self._session.get_bind().dialect.name == "sqlite" else pg_insert
        values = [
            {
                "node_id": node_id,
                "window_id": w.window_id,
                "window_start": w.window_start,
                "window_end": w.window_end,
                "interface": w.interface,
                "features": [f.model_dump(mode="json") for f in w.features],
                "omitted_packets": w.omitted_packets,
                "skipped_windows": w.skipped_windows,
                "received_at": received_at,
            }
            for w in windows
        ]
        statement = (
            insert(NetworkWindowModel)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=["node_id", "window_id"],
            )
            .returning(NetworkWindowModel.window_id)
        )
        saved = set((await self._session.execute(statement)).scalars().all())
        return [window for window in windows if window.window_id in saved]

    async def query(
        self, node_id: UUID, start_time: datetime | None, end_time: datetime | None, limit: int
    ) -> list[NetworkWindow]:
        statement = select(NetworkWindowModel).where(NetworkWindowModel.node_id == node_id)
        if start_time is not None:
            statement = statement.where(NetworkWindowModel.window_end >= start_time)
        if end_time is not None:
            statement = statement.where(NetworkWindowModel.window_end <= end_time)
        statement = statement.order_by(
            NetworkWindowModel.window_end.desc(),
            NetworkWindowModel.window_id,
        ).limit(limit)
        records = (await self._session.execute(statement)).scalars().all()
        return [
            NetworkWindow.model_validate(
                {
                    "window_id": r.window_id,
                    "window_start": ensure_utc(r.window_start),
                    "window_end": ensure_utc(r.window_end),
                    "interface": r.interface,
                    "features": r.features,
                    "omitted_packets": r.omitted_packets,
                    "skipped_windows": r.skipped_windows,
                }
            )
            for r in records
        ]
