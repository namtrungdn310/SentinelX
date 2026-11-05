"""Unit tests for DetectionService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.modules.detection.engine import DetectionEngine
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.detection.service import DetectionService


@pytest.mark.asyncio
async def test_detection_service_evaluate_and_broadcast() -> None:
    """Test evaluating metrics, persisting events and broadcasting realtime alerts."""
    mock_repo = AsyncMock(spec=DetectionRepository)
    mock_engine = AsyncMock(spec=DetectionEngine)
    mock_hub = AsyncMock(spec=RealtimeHub)

    node_id = uuid.uuid4()
    now = datetime.now(UTC)
    mock_event = DetectionEventContract(
        node_id=str(node_id),
        detector_name="cpu_threshold_detector",
        severity=DetectionSeverity.HIGH,
        attacker_ip=None,
        confidence_score=0.88,
        details=ResourceAnomalyDetail(
            metric_name="cpu_percent",
            current_value=88.0,
            threshold_value=80.0,
            window_duration_seconds=10,
            consecutive_samples=3,
        ),
        detected_at=now,
    )
    mock_engine.process_samples.return_value = [mock_event]

    service = DetectionService(
        repository=mock_repo,
        engine=mock_engine,
        realtime_hub=mock_hub,
    )

    samples = [MetricSample(observed_at=now, cpu_percent=88.0, memory_percent=40.0)]
    events = await service.evaluate_metrics(node_id=node_id, samples=samples)

    assert len(events) == 1
    mock_repo.save_events.assert_awaited_once_with([mock_event])
    mock_hub.broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_detection_service_get_event_not_found() -> None:
    """Test getting non-existent detection event raises 404."""
    mock_repo = AsyncMock(spec=DetectionRepository)
    mock_engine = AsyncMock(spec=DetectionEngine)
    mock_repo.get_by_id.return_value = None

    service = DetectionService(repository=mock_repo, engine=mock_engine)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_event(str(uuid.uuid4()))
    assert exc_info.value.status_code == 404
