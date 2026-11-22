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
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.models import IncidentModel
from sentinelx_controller.modules.incidents.repository import IncidentRepository

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {
    DetectionSeverity.MEDIUM.value: 2,
    DetectionSeverity.HIGH.value: 3,
    DetectionSeverity.CRITICAL.value: 4,
}

DETECTOR_TITLES: dict[str, str] = {
    "syn_flood_detector": "Tấn công SYN Flood",
    "port_scan_detector": "Dò quét cổng",
    "traffic_spike_detector": "Tấn công UDP Flood",
    "cpu_threshold_detector": "Quá tải CPU",
    "memory_exhaustion_detector": "Cạn kiệt RAM",
    "disk_saturation_detector": "Tràn dung lượng ổ đĩa",
}


class IncidentService:
    """Service orchestrating Incident correlation, lifecycle, and queries."""

    def __init__(
        self,
        repository: IncidentRepository,
        detection_service: DetectionService | None = None,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
        correlation_window_minutes: int = 10,
    ) -> None:
        self._repo = repository
        self._detection_service = detection_service
        self._realtime_hub = realtime_hub
        self._publisher = publisher
        self._correlation_window = timedelta(minutes=correlation_window_minutes)

    async def correlate_events(
        self,
        project_id: uuid.UUID,
        node_id: uuid.UUID,
        events: list[DetectionEventContract],
    ) -> list[tuple[IncidentResponse, list[DetectionEventContract]]]:
        """Gom nhóm các detection events vào incident hiện có hoặc tạo mới."""
        if not events:
            return []

        now = datetime.now(UTC)
        since = now - self._correlation_window

        # 1. Tìm incident đang hoạt động gần nhất của project
        await self._repo.lock_node(node_id)
        correlation_key = (
            "network:" + events[0].attacker_ip if events[0].attacker_ip else "resource"
        )
        # Split different attacker contexts rather than grouping every project event together.
        groups: dict[str, list[DetectionEventContract]] = {}
        for event in events:
            key = "network:" + event.attacker_ip if event.attacker_ip else "resource"
            groups.setdefault(key, []).append(event)
        if len(groups) > 1:
            combined: list[tuple[IncidentResponse, list[DetectionEventContract]]] = []
            for group in groups.values():
                combined.extend(await self.correlate_events(project_id, node_id, group))
            return combined
        active_incident = await self._repo.find_active_incident(
            project_id,
            since,
            node_id=node_id,
            correlation_key=correlation_key,
        )
        is_new = False

        if active_incident is None:
            is_new = True
            first_event = events[0]
            if first_event.detector_name == "traffic_spike_detector":
                attack_type = getattr(first_event.details, "attack_type", None)
                if not attack_type and isinstance(first_event.details, dict):
                    attack_type = first_event.details.get("attack_type")
                if attack_type == "TRAFFIC_SPIKE":
                    title = "Đột biến lưu lượng mạng"
                else:
                    title = "Tấn công UDP Flood"
            else:
                title = DETECTOR_TITLES.get(
                    first_event.detector_name,
                    f"Sự cố {first_event.detector_name}",
                )
            active_incident = IncidentModel(
                project_id=project_id,
                title=title,
                status=IncidentStatus.DETECTED.value,
                severity=max(
                    events, key=lambda e: SEVERITY_WEIGHT[e.severity.value]
                ).severity.value,
                started_at=first_event.detected_at,
                summary=f"Khởi phát bởi {first_event.detector_name}",
                node_id=node_id,
                correlation_key=correlation_key,
                last_event_at=max(e.detected_at for e in events),
            )
            await self._repo.create(active_incident)
        else:
            # Kiểm tra leo thang mức độ nghiêm trọng (Escalation)
            current_weight = SEVERITY_WEIGHT.get(active_incident.severity, 0)
            highest_event_weight = max(SEVERITY_WEIGHT.get(e.severity.value, 0) for e in events)
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
        active_incident.last_event_at = max(e.detected_at for e in events)

        # 2. Cập nhật incident_id cho từng event và lưu vào DB
        event_uuids: list[uuid.UUID] = []
        for ev in events:
            ev.incident_id = str(active_incident.id)
            event_uuids.append(uuid.UUID(ev.id))

        if self._detection_service is not None:
            await self._detection_service.link_to_incident(event_uuids, active_incident.id)

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

        return [
            (
                IncidentResponse(
                    id=str(active_incident.id),
                    project_id=str(active_incident.project_id),
                    title=active_incident.title,
                    status=IncidentStatus(active_incident.status),
                    severity=DetectionSeverity(active_incident.severity),
                    started_at=active_incident.started_at,
                    resolved_at=active_incident.resolved_at,
                    summary=active_incident.summary,
                    event_count=len(events),
                ),
                events,
            )
        ]

    async def mark_mitigating(self, incident_id: uuid.UUID) -> None:
        incident = await self._repo.get_by_id(incident_id)
        if incident is not None and incident.status == "DETECTED":
            incident.status = "MITIGATING"
            await self._repo.save(incident)

    async def resolve_if_quiet(self, incident_id: uuid.UUID, quiet_after: datetime) -> bool:
        incident = await self._repo.get_by_id(incident_id)
        if incident is None or incident.status not in {"DETECTED", "MITIGATING"}:
            return True
        if self._detection_service is None or not await self._detection_service.observed_quiet(
            incident_id,
            quiet_after,
            network=bool(
                incident.correlation_key and incident.correlation_key.startswith("network:")
            ),
        ):
            return False
        await self.update_incident(
            str(incident_id), IncidentUpdateRequest(status=IncidentStatus.RESOLVED)
        )
        return True

    async def validate_action_context(self, incident_id: uuid.UUID, node_id: uuid.UUID) -> None:
        incident = await self._repo.get_by_id(incident_id)
        if incident is None:
            raise HTTPException(404, "Incident not found")
        if incident.node_id != node_id:
            raise HTTPException(409, "Incident is not correlated to this node")
        if incident.status not in {"DETECTED", "MITIGATING"}:
            raise HTTPException(409, "Incident is already closed")

    async def _event_count(self, incident_id: uuid.UUID) -> int:
        if self._detection_service is None:
            return 0
        return (await self._detection_service.incident_counts([incident_id])).get(incident_id, 0)

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
        counts = (
            await self._detection_service.incident_counts([m.id for m in models])
            if self._detection_service is not None
            else {}
        )
        for m in models:
            count = counts.get(m.id, 0)
            items.append(
                IncidentResponse(
                    id=str(m.id),
                    project_id=str(m.project_id),
                    node_id=str(m.node_id) if m.node_id else None,
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

        count = await self._event_count(model.id)
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
            node_id=str(model.node_id) if model.node_id else None,
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

        count = await self._event_count(model.id)
        return IncidentResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            node_id=str(model.node_id) if model.node_id else None,
            title=model.title,
            status=IncidentStatus(model.status),
            severity=DetectionSeverity(model.severity),
            started_at=model.started_at,
            resolved_at=model.resolved_at,
            summary=model.summary,
            event_count=count,
        )
