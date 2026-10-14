"""Unit tests for AgentDaemon."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_common.contracts.agents import AgentEnrollResponse, HeartbeatResponse


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
