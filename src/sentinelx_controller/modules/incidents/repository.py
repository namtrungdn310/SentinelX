"""Database repository for persisting and querying security incidents."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.detection.models import DetectionEventModel
from sentinelx_controller.modules.incidents.models import IncidentModel


class IncidentRepository:
    """Data access layer for incidents table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, incident: IncidentModel) -> IncidentModel:
        """Thêm mới một sự cố vào database."""
        self._session.add(incident)
        await self._session.flush()
        return incident

    async def save(self, incident: IncidentModel) -> IncidentModel:
        """Cập nhật trạng thái sự cố."""
        await self._session.flush()
        return incident

    async def get_by_id(self, incident_id: uuid.UUID) -> IncidentModel | None:
        """Tìm sự cố theo UUID."""
        stmt = select(IncidentModel).where(IncidentModel.id == incident_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active_incident(
        self,
        project_id: uuid.UUID,
        since: datetime,
    ) -> IncidentModel | None:
        """Tìm sự cố đang mở (DETECTED hoặc MITIGATING) gần nhất trong project."""
        stmt = (
            select(IncidentModel)
            .where(
                IncidentModel.project_id == project_id,
                IncidentModel.status.in_(["DETECTED", "MITIGATING"]),
                IncidentModel.started_at >= since,
            )
            .order_by(IncidentModel.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def query_incidents(
        self,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[IncidentModel]]:
        """Truy vấn danh sách sự cố có lọc và phân trang."""
        stmt = select(IncidentModel)
        count_stmt = select(func.count()).select_from(IncidentModel)

        if project_id is not None:
            stmt = stmt.where(IncidentModel.project_id == project_id)
            count_stmt = count_stmt.where(IncidentModel.project_id == project_id)
        if status is not None:
            stmt = stmt.where(IncidentModel.status == status.upper())
            count_stmt = count_stmt.where(IncidentModel.status == status.upper())
        if severity is not None:
            stmt = stmt.where(IncidentModel.severity == severity.upper())
            count_stmt = count_stmt.where(IncidentModel.severity == severity.upper())
        if start_time is not None:
            stmt = stmt.where(IncidentModel.started_at >= start_time)
            count_stmt = count_stmt.where(IncidentModel.started_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(IncidentModel.started_at <= end_time)
            count_stmt = count_stmt.where(IncidentModel.started_at <= end_time)

        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(
                IncidentModel.started_at.desc(),
                IncidentModel.id,
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return total, list(result.scalars().all())

    async def count_events_for_incident(self, incident_id: uuid.UUID) -> int:
        """Đếm số lượng detection events thuộc incident."""
        stmt = (
            select(func.count())
            .select_from(DetectionEventModel)
            .where(DetectionEventModel.incident_id == incident_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0
