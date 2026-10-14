"""Unit tests for TelemetryService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.telemetry import MetricBatchRequest, MetricSample
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.telemetry.models import TelemetryMetricSampleModel
from sentinelx_controller.modules.telemetry.repository import TelemetryRepository
from sentinelx_controller.modules.telemetry.service import TelemetryService


@pytest.mark.asyncio
async def test_ingest_metrics_success() -> None:
    """Test successful metric batch ingestion."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_node_svc = AsyncMock(spec=NodeService)
    mock_node_svc.verify_agent.return_value = True
    mock_repo.save_batch.return_value = 2

    service = TelemetryService(telemetry_repo=mock_repo, node_service=mock_node_svc)

    node_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    request = MetricBatchRequest(
        node_id=node_id,
        agent_id=agent_id,
        sequence=1,
        sent_at=now,
        samples=[
            MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=40.0),
            MetricSample(observed_at=now, cpu_percent=25.0, memory_percent=45.0),
        ],
    )

    response = await service.ingest_metrics(request)
    assert response.status == "ok"
    assert response.processed_count == 2
    mock_node_svc.verify_agent.assert_awaited_once_with(
        node_id_str=node_id,
        agent_id_str=agent_id,
    )
    mock_repo.save_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_metrics_unverified_agent_raises_403() -> None:
    """Test ingestion fails with 403 if agent is not enrolled or verified."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_node_svc = AsyncMock(spec=NodeService)
    mock_node_svc.verify_agent.return_value = False

    service = TelemetryService(telemetry_repo=mock_repo, node_service=mock_node_svc)

    node_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    request = MetricBatchRequest(
        node_id=node_id,
        agent_id=agent_id,
        sequence=1,
        sent_at=now,
        samples=[MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=40.0)],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.ingest_metrics(request)

    assert exc_info.value.status_code == 403
    assert "Agent credentials invalid" in exc_info.value.detail
    mock_repo.save_batch.assert_not_called()


@pytest.mark.asyncio
async def test_query_metrics_success() -> None:
    """Test querying historical metrics returns MetricQueryResponse."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_node_svc = AsyncMock(spec=NodeService)
    mock_node_svc.get_node.return_value = MagicMock()

    node_uuid = uuid.uuid4()
    now = datetime.now(UTC)

    mock_record = TelemetryMetricSampleModel(
        id=1,
        node_id=node_uuid,
        observed_at=now,
        received_at=now,
        cpu_usage_pct=42.5,
        memory_usage_pct=60.0,
        disk_usage_pct=70.0,
        network_rx_bytes=1000,
        network_tx_bytes=2000,
    )
    mock_repo.query_by_node.return_value = [mock_record]

    service = TelemetryService(telemetry_repo=mock_repo, node_service=mock_node_svc)

    resp = await service.query_metrics(node_id_str=str(node_uuid))
    assert resp.node_id == str(node_uuid)
    assert resp.count == 1
    assert len(resp.samples) == 1
    assert resp.samples[0].cpu_percent == 42.5
    assert resp.samples[0].memory_percent == 60.0


@pytest.mark.asyncio
async def test_query_metrics_invalid_uuid_raises_422() -> None:
    """Test querying with malformed UUID raises 422."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_node_svc = AsyncMock(spec=NodeService)

    service = TelemetryService(telemetry_repo=mock_repo, node_service=mock_node_svc)

    with pytest.raises(HTTPException) as exc_info:
        await service.query_metrics(node_id_str="not-a-valid-uuid")

    assert exc_info.value.status_code == 422
