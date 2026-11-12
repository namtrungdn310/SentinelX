"""Application service layer for Incidents module."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from fastapi import status as http_status

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionEventResponse,
    DetectionSeverity,
)
from sentinelx_common.contracts.incidents import (
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatus,
    IncidentUpdateRequest,
)
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.models import IncidentModel
from sentinelx_controller.modules.incidents.repository import IncidentRepository

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {
    DetectionSeverity.LOW.value: 1,
    DetectionSeverity.MEDIUM.value: 2,
    DetectionSeverity.HIGH.value: 3,
    DetectionSeverity.CRITICAL.value: 4,
}


class IncidentService:
    """Service orchestrating Incident correlation, lifecycle, and queries."""

    def __init__(
        self,
        repository: IncidentRepository,
        detection_repo: DetectionRepository,
        detection_service: DetectionService | None = None,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
        correlation_window_minutes: int = 10,
    ) -> None:
        self._repo = repository
        self._detection_repo = detection_repo
        self._detection_service = detection_service
        self._realtime_hub = realtime_hub
        self._publisher = publisher
        self._correlation_window = timedelta(minutes=correlation_window_minutes)

    async def correlate_events(
        self,
        project_id: uuid.UUID,
        node_id: uuid.UUID,
        events: list[DetectionEventContract],
    ) -> list[tuple[IncidentModel, list[DetectionEventContract]]]:
        """Gom nhóm các detection events vào incident hiện có hoặc tạo mới."""
        if not events:
            return []

        now = datetime.now(UTC)
        since = now - self._correlation_window

        # 1. Tìm incident đang hoạt động gần nhất của project
        active_incident = await self._repo.find_active_incident(project_id, since)
        is_new = False

        if active_incident is None:
            is_new = True
            first_event = events[0]
            active_incident = IncidentModel(
                project_id=project_id,
                title=f"Sự cố an ninh: {first_event.detector_name} trên node {str(node_id)[:8]}",
                status=IncidentStatus.DETECTED.value,
                severity=first_event.severity.value,
                started_at=first_event.detected_at,
                summary=f"Khởi phát bởi {first_event.detector_name}",
            )
            await self._repo.create(active_incident)
        else:
            # Kiểm tra leo thang mức độ nghiêm trọng (Escalation)
            current_weight = SEVERITY_WEIGHT.get(active_incident.severity, 0)
            highest_event_weight = max(
                SEVERITY_WEIGHT.get(e.severity.value, 0) for e in events
            )
            if highest_event_weight > current_weight:
                for k, v in SEVERITY_WEIGHT.items():
                    if v == highest_event_weight:
                        active_incident.severity = k
                        break
            time_str = now.strftime("%H:%M:%S UTC")
            active_incident.summary = (
                f"Đã ghi nhận thêm {len(events)} sự kiện bất thường lúc {time_str}"
            )
            await self._repo.save(active_incident)

        # 2. Cập nhật incident_id cho từng event và lưu vào DB
        event_uuids: list[uuid.UUID] = []
        for ev in events:
            ev.incident_id = str(active_incident.id)
            event_uuids.append(uuid.UUID(ev.id))

        await self._detection_repo.link_events_to_incident(event_uuids, active_incident.id)

        # 3. Phát WebSocket thông báo
        event_type = (
            RealtimeEventType.INCIDENT_ALERT.value
            if is_new
            else RealtimeEventType.INCIDENT_UPDATE.value
        )
        msg = RealtimeMessage(
            event=event_type,
            data={
                "id": str(active_incident.id),
                "project_id": str(active_incident.project_id),
                "title": active_incident.title,
                "status": active_incident.status,
                "severity": active_incident.severity,
                "started_at": active_incident.started_at.isoformat(),
                "event_count": len(events),
            },
            timestamp=now,
        )
        if self._publisher is not None:
            self._publisher.enqueue(msg)
        elif self._realtime_hub is not None:
            await self._realtime_hub.broadcast(msg)

        logger.info(
            "Incident %s: %s (id=%s, severity=%s, new=%s)",
            "created" if is_new else "updated",
            active_incident.title,
            active_incident.id,
            active_incident.severity,
            is_new,
        )

        return [(active_incident, events)]

    async def list_incidents(
        self,
        project_id_str: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentListResponse:
        """Query list of incidents with filters and pagination."""
        project_uuid: uuid.UUID | None = None
        if project_id_str is not None:
            try:
                project_uuid = uuid.UUID(project_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid project UUID format",
                ) from err

        total, models = await self._repo.query_incidents(
            project_id=project_uuid,
            status=status,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

        items: list[IncidentResponse] = []
        for m in models:
            count = await self._repo.count_events_for_incident(m.id)
            items.append(
                IncidentResponse(
                    id=str(m.id),
                    project_id=str(m.project_id),
                    title=m.title,
                    status=IncidentStatus(m.status),
                    severity=DetectionSeverity(m.severity),
                    started_at=m.started_at,
                    resolved_at=m.resolved_at,
                    summary=m.summary,
                    event_count=count,
                )
            )

        return IncidentListResponse(total=total, items=items)

    async def get_incident(self, incident_id_str: str) -> IncidentDetailResponse:
        """Lấy chi tiết sự cố kèm danh sách detection events."""
        try:
            incident_uuid = uuid.UUID(incident_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid incident UUID format",
            ) from err

        model = await self._repo.get_by_id(incident_uuid)
        if model is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        count = await self._repo.count_events_for_incident(model.id)
        events_list: list[DetectionEventResponse] = []
        if self._detection_service is not None:
            events_resp = await self._detection_service.list_events(
                incident_id_str=incident_id_str,
                limit=100,
            )
            events_list = events_resp.items

        return IncidentDetailResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            title=model.title,
            status=IncidentStatus(model.status),
            severity=DetectionSeverity(model.severity),
            started_at=model.started_at,
            resolved_at=model.resolved_at,
            summary=model.summary,
            event_count=count,
            events=events_list,
        )

    async def update_incident(
        self,
        incident_id_str: str,
        request: IncidentUpdateRequest,
    ) -> IncidentResponse:
        """Cập nhật trạng thái hoặc tóm tắt sự cố (vd: RESOLVED, FALSE_POSITIVE)."""
        try:
            incident_uuid = uuid.UUID(incident_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid incident UUID format",
            ) from err

        model = await self._repo.get_by_id(incident_uuid)
        if model is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        now = datetime.now(UTC)
        if request.status is not None:
            model.status = request.status.value
            if request.status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE):
                model.resolved_at = now
            elif request.status in (IncidentStatus.DETECTED, IncidentStatus.MITIGATING):
                model.resolved_at = None

        if request.summary is not None:
            model.summary = request.summary

        await self._repo.save(model)

        # Broadcast update
        msg = RealtimeMessage(
            event=RealtimeEventType.INCIDENT_UPDATE.value,
            data={
                "id": str(model.id),
                "project_id": str(model.project_id),
                "title": model.title,
                "status": model.status,
                "severity": model.severity,
                "resolved_at": model.resolved_at.isoformat() if model.resolved_at else None,
            },
            timestamp=now,
        )
        if self._publisher is not None:
            self._publisher.enqueue(msg)
        elif self._realtime_hub is not None:
            await self._realtime_hub.broadcast(msg)

        count = await self._repo.count_events_for_incident(model.id)
        return IncidentResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            title=model.title,
            status=IncidentStatus(model.status),
            severity=DetectionSeverity(model.severity),
            started_at=model.started_at,
            resolved_at=model.resolved_at,
            summary=model.summary,
            event_count=count,
        )
