"""Application service layer for Incidents module."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from fastapi import status as http_status

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionEventResponse,
    DetectionSeverity,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.incidents import (
    IncidentDefenseStatus,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatus,
    IncidentUpdateRequest,
)
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.utils.time import ensure_utc
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

_METRIC_LABELS: dict[str, str] = {
    "cpu_percent": "CPU",
    "memory_percent": "RAM",
    "disk_percent": "Ổ đĩa",
}

_DELIVERY_FAILED_MARKER = "lỗi tải lệnh:"
_EXECUTION_FAILED_MARKER = "lỗi kích hoạt:"
_CLOSED_SUPPRESSION_WINDOW = timedelta(seconds=60)
_CRITICAL_ESCALATION_WINDOW = timedelta(seconds=60)


def _strip_error_lines(summary: str | None) -> str:
    if not summary:
        return ""
    kept = [
        line
        for line in summary.splitlines()
        if not line.startswith((_DELIVERY_FAILED_MARKER, _EXECUTION_FAILED_MARKER))
    ]
    return "\n".join(kept).strip()


def _extract_defense_status(summary: str | None, status: str) -> IncidentDefenseStatus | None:
    if status != IncidentStatus.DETECTED.value or not summary:
        return None
    if _DELIVERY_FAILED_MARKER in summary:
        return IncidentDefenseStatus.DELIVERY_FAILED
    if _EXECUTION_FAILED_MARKER in summary:
        return IncidentDefenseStatus.EXECUTION_FAILED
    return None


def _expected_title(event: DetectionEventContract) -> str:
    if event.detector_name == "traffic_spike_detector":
        attack_type = getattr(event.details, "attack_type", None)
        if not attack_type and isinstance(event.details, dict):
            attack_type = event.details.get("attack_type")
        return (
            "Đột biến lưu lượng mạng"
            if attack_type == "TRAFFIC_SPIKE"
            else "Tấn công UDP Flood"
        )
    return DETECTOR_TITLES.get(event.detector_name, f"Sự cố {event.detector_name}")


def _format_port_list(ports: list[int]) -> str:
    if not ports:
        return ""
    shown = ", ".join(str(p) for p in ports[:3])
    return f"{shown} (+{len(ports) - 3})" if len(ports) > 3 else shown


def _format_rate(bytes_per_sec: float) -> str:
    if bytes_per_sec >= 1_000_000:
        return f"{bytes_per_sec / 1_000_000:.1f} MB/s"
    if bytes_per_sec >= 1_000:
        return f"{bytes_per_sec / 1_000:.1f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


def _format_event_summary(event: DetectionEventContract) -> str:
    """Tạo chuỗi tóm tắt ngắn gọn, tập trung thông số kỹ thuật từ sự kiện phát hiện."""
    details = event.details
    extra = details.extra_context or {}

    if isinstance(details, ResourceAnomalyDetail):
        label = _METRIC_LABELS.get(details.metric_name, details.metric_name)
        mount = extra.get("mount_point")
        head = f"{label} {mount}" if mount else label
        parts = [f"{head}: {details.current_value:.1f}% (>= {details.threshold_value:.1f}%)"]
        if details.consecutive_samples > 1:
            sample_txt = f"{details.consecutive_samples} mẫu"
            if details.window_duration_seconds > 0:
                sample_txt += f"/{details.window_duration_seconds}s"
            parts.append(sample_txt)
        proc_name = extra.get("process_name")
        if proc_name:
            pid = extra.get("pid")
            proc_pct = extra.get("process_percent")
            proc_label = f"{proc_name} (PID {pid})" if pid is not None else str(proc_name)
            if isinstance(proc_pct, int | float):
                proc_label += f": {proc_pct:.1f}%"
            parts.append(proc_label)
        return " · ".join(parts)

    # NetworkAnomalyDetail
    attack = details.attack_type.upper()
    ip = details.source_ip
    ports_str = _format_port_list(details.targeted_ports)
    if attack == "SYN_FLOOD":
        parts = [f"SYN: {details.syn_count}", f"ACK: {details.ack_count}"]
        if details.metric_ratio is not None:
            parts.append(f"Tỷ lệ SYN/ACK: {details.metric_ratio:.1f}")
        parts.append(f"IP: {ip}")
        if ports_str:
            parts.append(f"Port: {ports_str}")
        return " · ".join(parts)

    if attack == "PORT_SCAN":
        port_cnt = extra.get("ports_scanned_count") or len(details.targeted_ports)
        trunc = "+" if extra.get("ports_truncated") else ""
        return " · ".join(
            [
                f"IP: {ip}",
                f"{port_cnt}{trunc} cổng ({details.protocol.upper()})",
                f"{details.packet_count} pkt",
            ]
        )

    parts = [details.protocol.upper(), f"IP: {ip}"]
    pps = extra.get("packets_per_second")
    bps = extra.get("bytes_per_second")
    if isinstance(pps, int | float):
        parts.append(f"{pps:,.0f} pps".replace(",", "."))
    else:
        parts.append(f"{details.packet_count} pkt")
    if isinstance(bps, int | float):
        parts.append(_format_rate(float(bps)))
    if ports_str:
        parts.append(f"Port: {ports_str}")
    return " · ".join(parts)


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
            closed_incident = await self._repo.find_recently_closed_incident(
                project_id,
                since,
                node_id=node_id,
                correlation_key=correlation_key,
            )
            if (
                isinstance(closed_incident, IncidentModel)
                and closed_incident.resolved_at is not None
            ):
                resolved_at = ensure_utc(closed_incident.resolved_at)
                in_grace = (now - resolved_at) < _CLOSED_SUPPRESSION_WINDOW
                surviving: list[DetectionEventContract] = []
                for ev in events:
                    detected_at = ensure_utc(ev.detected_at)
                    if detected_at <= resolved_at:
                        continue
                    same_context = (
                        correlation_key.startswith("network:")
                        or _expected_title(ev) == closed_incident.title
                    )
                    if in_grace and same_context:
                        continue
                    surviving.append(ev)
                if not surviving:
                    return []
                events = surviving

            is_new = True
            first_event = events[0]
            title = _expected_title(first_event)
            peak_event = max(events, key=lambda e: SEVERITY_WEIGHT[e.severity.value])
            latest_batch_event = max(events, key=lambda e: e.detected_at)
            batch_span = ensure_utc(latest_batch_event.detected_at) - ensure_utc(
                first_event.detected_at
            )
            initial_severity = (
                DetectionSeverity.CRITICAL.value
                if batch_span >= _CRITICAL_ESCALATION_WINDOW
                else peak_event.severity.value
            )
            active_incident = IncidentModel(
                project_id=project_id,
                title=title,
                status=IncidentStatus.DETECTED.value,
                severity=initial_severity,
                started_at=first_event.detected_at,
                summary=_format_event_summary(peak_event),
                node_id=node_id,
                correlation_key=correlation_key,
                last_event_at=latest_batch_event.detected_at,
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
            latest_event = max(events, key=lambda e: e.detected_at)
            sustained_duration = ensure_utc(latest_event.detected_at) - ensure_utc(
                active_incident.started_at
            )
            if (
                active_incident.severity != DetectionSeverity.CRITICAL.value
                and sustained_duration >= _CRITICAL_ESCALATION_WINDOW
            ):
                active_incident.severity = DetectionSeverity.CRITICAL.value
            new_summary = _format_event_summary(latest_event)
            existing_summary = active_incident.summary or ""
            preserved_suffix: str | None = None
            for marker in (
                "\nnftables:",
                "\nservice:",
                "\nos-cache:",
                f"\n{_DELIVERY_FAILED_MARKER}",
                f"\n{_EXECUTION_FAILED_MARKER}",
            ):
                if marker in existing_summary:
                    preserved_suffix = marker + existing_summary.split(marker, 1)[1]
                    break
            if preserved_suffix is None and " · nftables:" in existing_summary:
                preserved_suffix = "\nnftables:" + existing_summary.split(" · nftables:", 1)[1]
            active_incident.summary = (
                f"{new_summary}{preserved_suffix}" if preserved_suffix else new_summary
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
                    defense_status=_extract_defense_status(
                        active_incident.summary, active_incident.status
                    ),
                    event_count=len(events),
                ),
                events,
            )
        ]

    async def mark_mitigating(
        self,
        incident_id: uuid.UUID,
        action_note: str | None = None,
    ) -> None:
        incident = await self._repo.get_by_id(incident_id)
        if incident is not None and incident.status == "DETECTED":
            incident.status = "MITIGATING"
            cleaned = _strip_error_lines(incident.summary)
            if action_note and action_note not in cleaned:
                incident.summary = f"{cleaned}\n{action_note}" if cleaned else action_note
            else:
                incident.summary = cleaned or None
            await self._repo.save(incident)

    async def mark_defense_failed(
        self,
        incident_id: uuid.UUID,
        *,
        stage: Literal["delivery", "execution"],
        error_detail: str | None = None,
    ) -> None:
        """Ghi nhận trạng thái lỗi tải lệnh hoặc lỗi kích hoạt cho sự cố đang mở."""
        incident = await self._repo.get_by_id(incident_id)
        if incident is None or incident.status != IncidentStatus.DETECTED.value:
            return
        prefix = _DELIVERY_FAILED_MARKER if stage == "delivery" else _EXECUTION_FAILED_MARKER
        fallback = (
            "Hết hạn tải hoặc quá số lần gửi lệnh tới Agent"
            if stage == "delivery"
            else "Agent thực thi lệnh thất bại"
        )
        detail = (error_detail or "").strip() or fallback
        note = f"{prefix} {detail}"
        base_summary = _strip_error_lines(incident.summary)
        incident.summary = f"{base_summary}\n{note}" if base_summary else note
        await self._repo.save(incident)

        defense_status = _extract_defense_status(incident.summary, incident.status)
        msg = RealtimeMessage(
            event=RealtimeEventType.INCIDENT_UPDATE.value,
            data={
                "id": str(incident.id),
                "project_id": str(incident.project_id),
                "title": incident.title,
                "status": incident.status,
                "severity": incident.severity,
                "defense_status": defense_status.value if defense_status else None,
                "summary": incident.summary,
            },
            timestamp=datetime.now(UTC),
        )
        if self._publisher is not None:
            self._publisher.enqueue(msg)
        elif self._realtime_hub is not None:
            await self._realtime_hub.broadcast(msg)

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
        counts = await self._detection_service.incident_counts([incident_id])
        if isinstance(counts, dict):
            val = counts.get(incident_id, 0)
            return int(val) if isinstance(val, int) else 0
        return 0

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
                    defense_status=_extract_defense_status(m.summary, m.status),
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
            defense_status=_extract_defense_status(model.summary, model.status),
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
            defense_status=_extract_defense_status(model.summary, model.status),
            event_count=count,
        )

    async def delete_incident(self, incident_id_str: str) -> None:
        """Xóa vĩnh viễn một sự cố đã giải quyết / đã đóng khỏi danh sách theo dõi."""
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
        if model.status not in (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.FALSE_POSITIVE.value,
        ):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Only resolved or closed incidents can be deleted",
            )
        await self._repo.delete(model)
