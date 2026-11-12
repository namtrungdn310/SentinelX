"""Database repository for persisting and querying detection events."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_controller.modules.detection.models import (
    DetectionEventModel,
    DetectionNodeStateModel,
)


class DetectionRepository:
    """Data access layer for detection_events table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_state(self, node_id: uuid.UUID) -> DetectionNodeStateModel:
        """Serialize this node across concurrent requests and Controller workers."""
        insert = sqlite_insert if self._session.get_bind().dialect.name == "sqlite" else pg_insert
        await self._session.execute(
            insert(DetectionNodeStateModel)
            .values(
                node_id=node_id,
                state={},
            )
            .on_conflict_do_nothing(index_elements=["node_id"])
        )
        statement = (
            select(DetectionNodeStateModel)
            .where(
                DetectionNodeStateModel.node_id == node_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(statement)).scalar_one()

    async def save_events(
        self,
        events: list[DetectionEventContract],
    ) -> list[DetectionEventModel]:
        """Lưu một danh sách các detection events vào database."""
        models: list[DetectionEventModel] = []
        for ev in events:
            model = DetectionEventModel(
                id=uuid.UUID(ev.id),
                incident_id=uuid.UUID(ev.incident_id) if ev.incident_id else None,
                node_id=uuid.UUID(ev.node_id),
                detector_name=ev.detector_name,
                severity=ev.severity.value,
                attacker_ip=ev.attacker_ip,
                confidence_score=ev.confidence_score,
                details=ev.details.model_dump(mode="json"),
                detected_at=ev.detected_at,
            )
            models.append(model)

        self._session.add_all(models)
        await self._session.flush()
        return models

    async def query_events(
        self,
        node_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
        severity: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DetectionEventModel]:
        """Truy vấn danh sách sự kiện có phân trang và bộ lọc."""
        stmt = select(DetectionEventModel)

        if node_id is not None:
            stmt = stmt.where(DetectionEventModel.node_id == node_id)
        if incident_id is not None:
            stmt = stmt.where(DetectionEventModel.incident_id == incident_id)
        if severity is not None:
            stmt = stmt.where(DetectionEventModel.severity == severity.upper())
        if start_time is not None:
            stmt = stmt.where(DetectionEventModel.detected_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(DetectionEventModel.detected_at <= end_time)

        stmt = (
            stmt.order_by(
                DetectionEventModel.detected_at.desc(),
                DetectionEventModel.id,
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def link_events_to_incident(
        self,
        event_ids: list[uuid.UUID],
        incident_id: uuid.UUID,
    ) -> None:
        """Liên kết danh sách event IDs với một incident ID."""
        if not event_ids:
            return
        from sqlalchemy import update
        stmt = (
            update(DetectionEventModel)
            .where(DetectionEventModel.id.in_(event_ids))
            .values(incident_id=incident_id)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_by_id(self, event_id: uuid.UUID) -> DetectionEventModel | None:
        """Lấy một event theo UUID."""
        stmt = select(DetectionEventModel).where(DetectionEventModel.id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_events(
        self,
        node_id: uuid.UUID | None,
        severity: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> int:
        statement = select(func.count()).select_from(DetectionEventModel)
        if node_id is not None:
            statement = statement.where(DetectionEventModel.node_id == node_id)
        if severity is not None:
            statement = statement.where(DetectionEventModel.severity == severity.upper())
        if start_time is not None:
            statement = statement.where(DetectionEventModel.detected_at >= start_time)
        if end_time is not None:
            statement = statement.where(DetectionEventModel.detected_at <= end_time)
        return int((await self._session.execute(statement)).scalar_one())
