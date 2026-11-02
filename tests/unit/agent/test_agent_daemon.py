"""Unit tests for AgentDaemon."""

import asyncio
import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_common.contracts.agents import AgentEnrollResponse, HeartbeatResponse
from sentinelx_common.contracts.telemetry import (
    MetricBatchRequest,
    MetricBatchResponse,
    MetricSample,
)


@pytest.mark.asyncio
async def test_daemon_bootstrap_from_existing_file(tmp_path: Path) -> None:
    """Test daemon loads existing identity without enrolling."""
    id_file = tmp_path / "agent_identity.json"
    existing = AgentIdentity(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        enrolled_at=datetime.now(UTC),
    )
    AgentIdentityManager.save(id_file, existing)

    settings = AgentSettings(identity_path=id_file)
    mock_client = AsyncMock(spec=ControllerClient)

    daemon = AgentDaemon(settings=settings, client=mock_client)
    identity = await daemon.bootstrap_identity()

    assert identity.node_id == existing.node_id
    assert identity.agent_id == existing.agent_id
    mock_client.enroll.assert_not_called()


@pytest.mark.asyncio
async def test_daemon_bootstrap_performs_enrollment_when_no_file(tmp_path: Path) -> None:
    """Test daemon calls enroll and saves identity when no local file exists."""
    id_file = tmp_path / "agent_identity.json"
    settings = AgentSettings(
        identity_path=id_file,
        node_id="11111111-2222-3333-4444-555555555555",
        enrollment_token="my-secret-token",
    )
    mock_client = AsyncMock(spec=ControllerClient)
    now = datetime.now(UTC)
    mock_client.enroll.return_value = AgentEnrollResponse(
        agent_id="33333333-4444-5555-6666-777777777777",
        node_id="11111111-2222-3333-4444-555555555555",
        status="enrolled",
        heartbeat_interval_seconds=10,
        enrolled_at=now,
    )

    daemon = AgentDaemon(settings=settings, client=mock_client)
    identity = await daemon.bootstrap_identity()

    assert identity.agent_id == "33333333-4444-5555-6666-777777777777"
    assert id_file.is_file()
    mock_client.enroll.assert_awaited_once()


@pytest.mark.asyncio
async def test_daemon_run_stops_on_event(tmp_path: Path) -> None:
    """Test daemon runs heartbeat loop and cleanly shuts down on event."""
    id_file = tmp_path / "agent_identity.json"
    existing = AgentIdentity(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        enrolled_at=datetime.now(UTC),
    )
    AgentIdentityManager.save(id_file, existing)

    settings = AgentSettings(identity_path=id_file, heartbeat_interval_seconds=1)
    mock_client = AsyncMock(spec=ControllerClient)
    mock_client.send_heartbeat.return_value = HeartbeatResponse(
        status="ok",
        received_at=datetime.now(UTC),
        next_interval_seconds=1,
    )

    daemon = AgentDaemon(settings=settings, client=mock_client)
    stop_event = asyncio.Event()

    async def trigger_stop() -> None:
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(trigger_stop())
    await daemon.run(stop_event=stop_event)

    assert mock_client.send_heartbeat.await_count >= 1


@pytest.mark.asyncio
async def test_daemon_run_collects_and_sends_telemetry(tmp_path: Path) -> None:
    """Test daemon runs telemetry loop, batches samples, and sends to controller."""
    from sentinelx_common.contracts.telemetry import MetricBatchResponse

    id_file = tmp_path / "agent_identity.json"
    existing = AgentIdentity(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        enrolled_at=datetime.now(UTC),
    )
    AgentIdentityManager.save(id_file, existing)

    settings = AgentSettings(
        identity_path=id_file,
        heartbeat_interval_seconds=10,
        telemetry_interval_seconds=0.01,
        telemetry_batch_size=2,
    )
    mock_client = AsyncMock(spec=ControllerClient)
    mock_client.send_heartbeat.return_value = HeartbeatResponse(
        status="ok",
        received_at=datetime.now(UTC),
        next_interval_seconds=10,
    )
    mock_client.send_metrics.return_value = MetricBatchResponse(
        status="ok",
        processed_count=2,
        received_at=datetime.now(UTC),
    )

    daemon = AgentDaemon(settings=settings, client=mock_client)
    stop_event = asyncio.Event()

    async def trigger_stop() -> None:
        # Wait until send_metrics is called at least once
        for _ in range(50):
            if mock_client.send_metrics.await_count >= 1:
                break
            await asyncio.sleep(0.01)
        stop_event.set()

    asyncio.create_task(trigger_stop())
    await daemon.run(stop_event=stop_event)

    assert mock_client.send_metrics.await_count >= 1
    call_args = mock_client.send_metrics.call_args[0][0]
    assert call_args.node_id == existing.node_id
    assert call_args.agent_id == existing.agent_id
    assert len(call_args.samples) == 2


def test_daemon_initializes_real_collector_by_default() -> None:
    """Test daemon initializes RealResourceCollector by default."""
    from sentinelx_agent.collectors.real import RealResourceCollector

    settings = AgentSettings()
    mock_client = AsyncMock(spec=ControllerClient)
    daemon = AgentDaemon(settings=settings, client=mock_client)
    assert isinstance(daemon.collector, RealResourceCollector)


def test_daemon_initializes_fake_collector_when_configured() -> None:
    """Test daemon initializes FakeMetricGenerator when configured."""
    from sentinelx_agent.collectors.fake import FakeMetricGenerator

    settings = AgentSettings(telemetry_collector_type="fake")
    mock_client = AsyncMock(spec=ControllerClient)
    daemon = AgentDaemon(settings=settings, client=mock_client)
    assert isinstance(daemon.collector, FakeMetricGenerator)


@pytest.mark.asyncio
async def test_collection_failure_and_send_retry_preserve_batch_order(tmp_path: Path) -> None:
    """A transient OS failure doesn't stop heartbeats or corrupt a retried batch."""
    from sentinelx_agent.client import ControllerClientError
    from sentinelx_agent.telemetry import TelemetryBatcher

    identity = AgentIdentity(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        enrolled_at=datetime.now(UTC),
    )
    path = tmp_path / "identity.json"
    AgentIdentityManager.save(path, identity)
    settings = AgentSettings(
        identity_path=path,
        telemetry_interval_seconds=0.01,
        telemetry_batch_size=2,
        retry_initial_delay_seconds=0.1,
    )
    collector = MagicMock()
    count = 0
    loop_thread = threading.get_ident()
    collection_threads: list[int] = []

    def collect() -> MetricSample:
        nonlocal count
        collection_threads.append(threading.get_ident())
        count += 1
        if count == 1:
            raise OSError("Transient collector error")
        return MetricSample(
            observed_at=datetime.now(UTC),
            cpu_percent=float(count),
            memory_percent=50,
        )

    collector.collect.side_effect = collect
    stop = asyncio.Event()
    client = AsyncMock(spec=ControllerClient)
    client.send_heartbeat.return_value = HeartbeatResponse(
        status="ok",
        received_at=datetime.now(UTC),
        next_interval_seconds=1,
    )
    sent: list[MetricBatchRequest] = []

    async def send(request: MetricBatchRequest) -> MetricBatchResponse:
        sent.append(request)
        if len(sent) == 1:
            raise ControllerClientError(503, "Temporary outage")
        stop.set()
        return MetricBatchResponse(processed_count=2, received_at=datetime.now(UTC))

    client.send_metrics.side_effect = send
    batcher = TelemetryBatcher()
    daemon = AgentDaemon(settings, client=client, collector=collector, batcher=batcher)
    assert daemon.batcher is batcher
    await asyncio.wait_for(daemon.run(stop), timeout=3)
    assert len(sent) == 2
    assert sent[0].sequence == sent[1].sequence == 1
    assert sent[0].samples == sent[1].samples
    assert [sample.cpu_percent for sample in sent[1].samples] == [2, 3]
    assert client.send_heartbeat.await_count >= 1
    assert collection_threads and all(thread != loop_thread for thread in collection_threads)
