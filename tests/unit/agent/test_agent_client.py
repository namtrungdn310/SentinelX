"""Unit tests for ControllerClient."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_common.contracts.agents import AgentEnrollRequest, HeartbeatRequest


@pytest.mark.asyncio
async def test_client_enroll_success() -> None:
    """Test enroll sends POST request and parses AgentEnrollResponse."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    now = datetime.now(UTC)
    mock_response.json = AsyncMock(
        return_value={
            "agent_id": "22222222-3333-4444-5555-666666666666",
            "node_id": "11111111-2222-3333-4444-555555555555",
            "status": "enrolled",
            "heartbeat_interval_seconds": 10,
            "enrolled_at": now.isoformat(),
        }
    )
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_ctx

    client = ControllerClient(controller_url="http://test-controller:8000", session=mock_session)
    req = AgentEnrollRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        enrollment_token="valid_token",
        hostname="test-node",
    )

    resp = await client.enroll(req)
    assert resp.agent_id == "22222222-3333-4444-5555-666666666666"
    assert resp.status == "enrolled"


@pytest.mark.asyncio
async def test_client_send_heartbeat_error_raises_exception() -> None:
    """Test heartbeat failure raises ControllerClientError."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.json = AsyncMock(return_value={"detail": "Agent credentials invalid"})
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_ctx

    client = ControllerClient(controller_url="http://test-controller:8000", session=mock_session)
    req = HeartbeatRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        sequence=1,
        sent_at=datetime.now(UTC),
    )

    with pytest.raises(ControllerClientError) as exc_info:
        await client.send_heartbeat(req)

    assert exc_info.value.status_code == 403
    assert "Agent credentials invalid" in exc_info.value.message


@pytest.mark.asyncio
async def test_client_send_metrics_success() -> None:
    """Test send_metrics dispatches batch and parses MetricBatchResponse."""
    from sentinelx_common.contracts.telemetry import MetricBatchRequest, MetricSample

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    now = datetime.now(UTC)
    mock_response.json = AsyncMock(
        return_value={
            "status": "ok",
            "processed_count": 2,
            "received_at": now.isoformat(),
        }
    )
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_ctx

    client = ControllerClient(controller_url="http://test-controller:8000", session=mock_session)
    batch_req = MetricBatchRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        sequence=1,
        sent_at=now,
        samples=[
            MetricSample(observed_at=now, cpu_percent=25.0, memory_percent=50.0),
            MetricSample(observed_at=now, cpu_percent=30.0, memory_percent=55.0),
        ],
    )

    resp = await client.send_metrics(batch_req)
    assert resp.status == "ok"
    assert resp.processed_count == 2


@pytest.mark.asyncio
async def test_client_send_metrics_error_raises_exception() -> None:
    """Test send_metrics failure raises ControllerClientError."""
    from sentinelx_common.contracts.telemetry import MetricBatchRequest, MetricSample

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.json = AsyncMock(return_value={"detail": "Agent not enrolled"})
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_ctx

    client = ControllerClient(controller_url="http://test-controller:8000", session=mock_session)
    now = datetime.now(UTC)
    batch_req = MetricBatchRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        sequence=1,
        sent_at=now,
        samples=[MetricSample(observed_at=now, cpu_percent=25.0, memory_percent=50.0)],
    )

    with pytest.raises(ControllerClientError) as exc_info:
        await client.send_metrics(batch_req)

    assert exc_info.value.status_code == 403
    assert "Agent not enrolled" in exc_info.value.message

