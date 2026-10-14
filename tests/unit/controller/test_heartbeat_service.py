"""Unit tests for NodeService heartbeat processing."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.agents import HeartbeatRequest
from sentinelx_controller.modules.nodes.models import NodeModel
from sentinelx_controller.modules.nodes.repository import (
    AgentEnrollmentRepository,
    NodeRepository,
)
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.service import ProjectService


@pytest.fixture
def mock_deps() -> tuple[AsyncMock, AsyncMock, AsyncMock, NodeService]:
    """Create mocked dependencies and NodeService instance."""
    node_repo = AsyncMock(spec=NodeRepository)
    enrollment_repo = AsyncMock(spec=AgentEnrollmentRepository)
    project_service = AsyncMock(spec=ProjectService)
    service = NodeService(
        node_repo=node_repo,
        enrollment_repo=enrollment_repo,
        project_service=project_service,
    )
    return node_repo, enrollment_repo, project_service, service


@pytest.mark.asyncio
async def test_process_heartbeat_success(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test successful heartbeat updates node liveness and status to ONLINE."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-prod-01",
        ip_address="192.168.1.10",
        status="unenrolled",
    )
    enrollment_repo.verify_agent_credentials.return_value = True

    req = HeartbeatRequest(
        node_id=str(node_id),
        agent_id=str(agent_id),
        sequence=1,
        sent_at=datetime.now(UTC),
    )

    resp = await service.process_heartbeat(req)

    assert resp.status == "ok"
    assert resp.next_interval_seconds == 10
    node_repo.record_heartbeat.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_heartbeat_node_not_found_raises_404(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test heartbeat for non-existent node raises 404."""
    node_repo, _, _, service = mock_deps
    node_repo.get_by_id.return_value = None

    req = HeartbeatRequest(
        node_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        sequence=1,
        sent_at=datetime.now(UTC),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.process_heartbeat(req)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_process_heartbeat_invalid_credentials_raises_403(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test heartbeat with unapproved or mismatched agent_id raises 403."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()

    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-prod-01",
        ip_address="192.168.1.10",
    )
    enrollment_repo.verify_agent_credentials.return_value = False

    req = HeartbeatRequest(
        node_id=str(node_id),
        agent_id=str(uuid.uuid4()),
        sequence=1,
        sent_at=datetime.now(UTC),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.process_heartbeat(req)

    assert exc_info.value.status_code == 403
    assert "credentials invalid" in exc_info.value.detail
