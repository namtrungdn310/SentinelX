"""Unit tests for Incident correlation and lifecycle service."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    NetworkAnomalyDetail,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.incidents import (
    IncidentDefenseStatus,
    IncidentStatus,
    IncidentUpdateRequest,
)
from sentinelx_controller.modules.incidents.models import IncidentModel
from sentinelx_controller.modules.incidents.service import (
    IncidentService,
    _extract_defense_status,
    _format_event_summary,
)


def make_event(
    severity: DetectionSeverity = DetectionSeverity.MEDIUM,
    detector_name: str = "cpu_threshold_detector",
) -> DetectionEventContract:
    return DetectionEventContract(
        node_id=str(uuid.uuid4()),
        detector_name=detector_name,
        severity=severity,
        confidence_score=0.9,
        details=ResourceAnomalyDetail(
            metric_name="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            window_duration_seconds=15,
            consecutive_samples=3,
        ),
        detected_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_correlate_events_creates_new_incident_then_attaches() -> None:
    repo = AsyncMock()
    detection_service = AsyncMock()
    repo.find_active_incident.return_value = None

    created_incident = None

    async def mock_create(inc: IncidentModel) -> IncidentModel:
        nonlocal created_incident
        inc.id = uuid.uuid4()
        created_incident = inc
        return inc

    repo.create.side_effect = mock_create

    service = IncidentService(
        repository=repo,
        detection_service=detection_service,
        correlation_window_minutes=10,
    )

    project_id = uuid.uuid4()
    node_id = uuid.uuid4()

    # 1. First event -> creates new Incident
    event1 = make_event(severity=DetectionSeverity.MEDIUM)
    correlated1 = await service.correlate_events(project_id, node_id, [event1])
    assert len(correlated1) == 1
    inc1, events1 = correlated1[0]
    assert inc1.status == IncidentStatus.DETECTED.value
    assert inc1.severity == DetectionSeverity.MEDIUM.value
    assert event1.incident_id == str(inc1.id)
    assert repo.create.await_count == 1
    assert detection_service.link_to_incident.await_count == 1

    # 2. Second event arrives within correlation window -> links to same incident and escalates
    repo.find_active_incident.return_value = created_incident
    event2 = make_event(severity=DetectionSeverity.CRITICAL)
    correlated2 = await service.correlate_events(project_id, node_id, [event2])
    assert len(correlated2) == 1
    inc2, _ = correlated2[0]
    assert inc2.id == inc1.id
    assert inc2.severity == DetectionSeverity.CRITICAL.value
    assert event2.incident_id == str(inc1.id)
    assert repo.save.await_count == 1


@pytest.mark.asyncio
async def test_update_incident_lifecycle() -> None:
    repo = AsyncMock()
    detection_service = AsyncMock()
    incident_id = uuid.uuid4()
    project_id = uuid.uuid4()

    active_model = IncidentModel(
        id=incident_id,
        project_id=project_id,
        title="Test Incident",
        status=IncidentStatus.DETECTED.value,
        severity=DetectionSeverity.HIGH.value,
        started_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    repo.get_by_id.return_value = active_model
    detection_service.incident_counts.return_value = {incident_id: 2}

    service = IncidentService(
        repository=repo,
        detection_service=detection_service,
    )

    # Resolve incident
    resp = await service.update_incident(
        incident_id_str=str(incident_id),
        request=IncidentUpdateRequest(
            status=IncidentStatus.RESOLVED,
            summary="Manually resolved by administrator",
        ),
    )
    assert resp.status == IncidentStatus.RESOLVED
    assert resp.resolved_at is not None
    assert resp.summary == "Manually resolved by administrator"
    assert active_model.status == "RESOLVED"


@pytest.mark.asyncio
async def test_incident_technical_summary_and_mitigation_note() -> None:
    cpu_ev = make_event(severity=DetectionSeverity.HIGH)
    assert _format_event_summary(cpu_ev) == "CPU: 85.0% (>= 80.0%) · 3 mẫu/15s"

    syn_ev = DetectionEventContract(
        node_id=str(uuid.uuid4()),
        detector_name="syn_flood_detector",
        severity=DetectionSeverity.CRITICAL,
        attacker_ip="203.0.113.195",
        confidence_score=0.95,
        details=NetworkAnomalyDetail(
            attack_type="SYN_FLOOD",
            source_ip="203.0.113.195",
            destination_ip="10.0.1.15",
            protocol="tcp",
            packet_count=524,
            byte_count=31440,
            syn_count=520,
            ack_count=4,
            targeted_ports=[80, 443],
            metric_ratio=130.0,
        ),
        detected_at=datetime.now(UTC),
    )
    assert (
        _format_event_summary(syn_ev)
        == "SYN: 520 · ACK: 4 · Tỷ lệ SYN/ACK: 130.0 · IP: 203.0.113.195 · Port: 80, 443"
    )

    repo = AsyncMock()
    model = IncidentModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Tấn công SYN Flood",
        status=IncidentStatus.DETECTED.value,
        severity=DetectionSeverity.CRITICAL.value,
        started_at=datetime.now(UTC),
        summary=_format_event_summary(syn_ev),
    )
    repo.get_by_id.return_value = model

    service = IncidentService(repository=repo)
    await service.mark_mitigating(
        model.id, action_note="nftables: DROP 203.0.113.195 (thời hạn: 30 phút)"
    )
    assert model.status == IncidentStatus.MITIGATING.value
    assert model.summary == (
        "SYN: 520 · ACK: 4 · Tỷ lệ SYN/ACK: 130.0 · IP: 203.0.113.195"
        " · Port: 80, 443\nnftables: DROP 203.0.113.195 (thời hạn: 30 phút)"
    )

    mem_model = IncidentModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Cạn kiệt RAM",
        status=IncidentStatus.DETECTED.value,
        severity=DetectionSeverity.CRITICAL.value,
        started_at=datetime.now(UTC),
        summary="RAM: 90.4% (>= 85.0%) · 3 mẫu · java (PID 4112): 71.0%",
    )
    repo.get_by_id.return_value = mem_model
    await service.mark_mitigating(mem_model.id, action_note="service: RESTART java")
    assert mem_model.summary == (
        "RAM: 90.4% (>= 85.0%) · 3 mẫu · java (PID 4112): 71.0%\nservice: RESTART java"
    )


@pytest.mark.asyncio
async def test_recently_closed_incident_suppresses_immediate_retrigger_and_stale_events() -> None:
    repo = AsyncMock()
    detection_service = AsyncMock()
    repo.find_active_incident.return_value = None

    project_id = uuid.uuid4()
    node_id = uuid.uuid4()
    closed_at = datetime.now(UTC) - timedelta(seconds=10)
    repo.find_recently_closed_incident.return_value = IncidentModel(
        id=uuid.uuid4(),
        project_id=project_id,
        node_id=node_id,
        title="Quá tải CPU",
        status=IncidentStatus.RESOLVED.value,
        severity=DetectionSeverity.HIGH.value,
        started_at=closed_at - timedelta(minutes=2),
        resolved_at=closed_at,
        correlation_key="resource",
    )

    service = IncidentService(repository=repo, detection_service=detection_service)

    stale_event = make_event(severity=DetectionSeverity.HIGH)
    stale_event.detected_at = closed_at - timedelta(seconds=2)
    residual_event = make_event(severity=DetectionSeverity.HIGH)
    residual_event.detected_at = closed_at + timedelta(seconds=5)

    assert await service.correlate_events(project_id, node_id, [stale_event, residual_event]) == []
    assert repo.create.await_count == 0

    # Once outside the 60s grace window, a new event after resolved_at opens a fresh incident.
    repo.find_recently_closed_incident.return_value.resolved_at = datetime.now(UTC) - timedelta(
        seconds=90
    )

    async def mock_create(inc: IncidentModel) -> IncidentModel:
        inc.id = uuid.uuid4()
        return inc

    repo.create.side_effect = mock_create
    fresh_event = make_event(severity=DetectionSeverity.HIGH)
    fresh_event.detected_at = datetime.now(UTC)
    correlated = await service.correlate_events(project_id, node_id, [fresh_event])
    assert len(correlated) == 1
    assert repo.create.await_count == 1


@pytest.mark.asyncio
async def test_mark_defense_failed_delivery_and_execution_states() -> None:
    repo = AsyncMock()
    model = IncidentModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Tấn công SYN Flood",
        status=IncidentStatus.DETECTED.value,
        severity=DetectionSeverity.CRITICAL.value,
        started_at=datetime.now(UTC),
        summary="SYN: 520 · ACK: 4 · IP: 203.0.113.195",
    )
    repo.get_by_id.return_value = model

    service = IncidentService(repository=repo)
    await service.mark_defense_failed(
        model.id,
        stage="delivery",
        error_detail="Command expired",
    )
    assert model.status == IncidentStatus.DETECTED.value
    assert model.summary == "SYN: 520 · ACK: 4 · IP: 203.0.113.195\nlỗi tải lệnh: Command expired"
    assert _extract_defense_status(model.summary, model.status) == (
        IncidentDefenseStatus.DELIVERY_FAILED
    )

    await service.mark_defense_failed(
        model.id,
        stage="execution",
        error_detail="nft binary missing",
    )
    assert model.summary == (
        "SYN: 520 · ACK: 4 · IP: 203.0.113.195\nlỗi kích hoạt: nft binary missing"
    )
    assert _extract_defense_status(model.summary, model.status) == (
        IncidentDefenseStatus.EXECUTION_FAILED
    )

    await service.mark_mitigating(
        model.id,
        action_note="nftables: DROP 203.0.113.195 (thời hạn: 30 phút)",
    )
    assert model.status == IncidentStatus.MITIGATING.value
    assert model.summary == (
        "SYN: 520 · ACK: 4 · IP: 203.0.113.195\n"
        "nftables: DROP 203.0.113.195 (thời hạn: 30 phút)"
    )
    assert _extract_defense_status(model.summary, model.status) is None


@pytest.mark.asyncio
async def test_correlate_events_escalates_high_to_critical_after_60s() -> None:
    repo = AsyncMock()
    detection_service = AsyncMock()
    project_id = uuid.uuid4()
    node_id = uuid.uuid4()
    start_time = datetime.now(UTC) - timedelta(seconds=70)

    # 1. Within < 60s, a follow-up HIGH event keeps severity at HIGH
    active_recent = IncidentModel(
        id=uuid.uuid4(),
        project_id=project_id,
        node_id=node_id,
        title="Quá tải CPU",
        status=IncidentStatus.DETECTED.value,
        severity=DetectionSeverity.HIGH.value,
        started_at=start_time,
        correlation_key="resource",
    )
    repo.find_active_incident.return_value = active_recent
    service = IncidentService(repository=repo, detection_service=detection_service)

    early_follow_up = make_event(severity=DetectionSeverity.HIGH)
    early_follow_up.detected_at = start_time + timedelta(seconds=20)
    correlated_early = await service.correlate_events(project_id, node_id, [early_follow_up])
    assert correlated_early[0][0].severity == DetectionSeverity.HIGH
    assert active_recent.severity == DetectionSeverity.HIGH.value

    # 2. Sustained >= 60s escalates HIGH -> CRITICAL
    late_follow_up = make_event(severity=DetectionSeverity.HIGH)
    late_follow_up.detected_at = start_time + timedelta(seconds=65)
    correlated_late = await service.correlate_events(project_id, node_id, [late_follow_up])
    assert correlated_late[0][0].severity == DetectionSeverity.CRITICAL
    assert active_recent.severity == DetectionSeverity.CRITICAL.value
