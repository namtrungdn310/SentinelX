"""Database repository for persisting and querying detection events."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_controller.modules.detection.models import DetectionEventModel


class DetectionRepository:
    """Data access layer for detection_events table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_events(
        self,
        events: list[DetectionEventContract],
    ) -> list[DetectionEventModel]:
        """Lưu một danh sách các detection events vào database."""
        models: list[DetectionEventModel] = []
        for ev in events:
            model = DetectionEventModel(
                id=uuid.UUID(ev.id),
                incident_id=None,
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
        if severity is not None:
            stmt = stmt.where(DetectionEventModel.severity == severity.upper())
        if start_time is not None:
            stmt = stmt.where(DetectionEventModel.detected_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(DetectionEventModel.detected_at <= end_time)

        stmt = stmt.order_by(DetectionEventModel.detected_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, event_id: uuid.UUID) -> DetectionEventModel | None:
        """Lấy một event theo UUID."""
        stmt = select(DetectionEventModel).where(DetectionEventModel.id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
