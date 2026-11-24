"""Unit tests for NodeService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.nodes import NodeRegisterRequest, NodeStatus
from sentinelx_common.contracts.projects import ProjectResponse
from sentinelx_controller.modules.nodes.models import NodeModel
from sentinelx_controller.modules.nodes.repository import NodeRepository
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.service import ProjectService


@pytest.mark.asyncio
async def test_register_node_project_not_found_raises_404() -> None:
    """Test register node raises 404 when project does not exist."""
    node_repo_mock = AsyncMock(spec=NodeRepository)
    project_service_mock = AsyncMock(spec=ProjectService)
    project_service_mock.get_project.side_effect = HTTPException(
        status_code=404,
        detail="Project not found",
    )

    service = NodeService(node_repo=node_repo_mock, project_service=project_service_mock)
    req = NodeRegisterRequest(
        project_id=str(uuid.uuid4()),
        hostname="web-01",
        ip_address="192.168.1.50",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.register_node(req)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_register_node_duplicate_ip_raises_conflict() -> None:
    """Test register node raises 409 conflict when IP already exists in project."""
    node_repo_mock = AsyncMock(spec=NodeRepository)
    project_service_mock = AsyncMock(spec=ProjectService)

    p_id = uuid.uuid4()
    project_service_mock.get_project.return_value = ProjectResponse(
        project_id=str(p_id),
        name="Test-Project",
        created_at=datetime.now(UTC),
    )

    existing_node = NodeModel(
        id=uuid.uuid4(),
        project_id=p_id,
        hostname="web-01",
        ip_address="192.168.1.50",
    )
    node_repo_mock.get_by_ip_in_project.return_value = existing_node

    service = NodeService(node_repo=node_repo_mock, project_service=project_service_mock)
    req = NodeRegisterRequest(
        project_id=str(p_id),
        hostname="web-02",
        ip_address="192.168.1.50",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.register_node(req)

    assert exc_info.value.status_code == 409
    assert "already registered" in exc_info.value.detail


def test_to_response_marks_stale_online_node_offline() -> None:
    now = datetime.now(UTC)
    fresh = NodeModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        hostname="fresh-01",
        ip_address="10.0.0.10",
        status=NodeStatus.ONLINE.value,
        last_seen_at=now - timedelta(seconds=10),
        created_at=now - timedelta(hours=1),
    )
    stale = NodeModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        hostname="stale-01",
        ip_address="10.0.0.11",
        status=NodeStatus.ONLINE.value,
        last_seen_at=now - timedelta(seconds=120),
        created_at=now - timedelta(hours=1),
    )

    assert NodeService._to_response(fresh).status == NodeStatus.ONLINE
    assert NodeService._to_response(stale).status == NodeStatus.OFFLINE
