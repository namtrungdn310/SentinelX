"""Unit tests for NodeService."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.nodes import NodeRegisterRequest
from sentinelx_controller.modules.nodes.models import NodeModel
from sentinelx_controller.modules.nodes.repository import NodeRepository
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.models import ProjectModel
from sentinelx_controller.modules.projects.repository import ProjectRepository


@pytest.mark.asyncio
async def test_register_node_project_not_found_raises_404() -> None:
    node_repo_mock = AsyncMock(spec=NodeRepository)
    project_repo_mock = AsyncMock(spec=ProjectRepository)
    project_repo_mock.get_by_id.return_value = None

    service = NodeService(node_repo=node_repo_mock, project_repo=project_repo_mock)
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
    node_repo_mock = AsyncMock(spec=NodeRepository)
    project_repo_mock = AsyncMock(spec=ProjectRepository)

    p_id = uuid.uuid4()
    project_repo_mock.get_by_id.return_value = ProjectModel(
        id=p_id, name="Test-Project"
    )

    existing_node = NodeModel(
        id=uuid.uuid4(),
        project_id=p_id,
        hostname="web-01",
        ip_address="192.168.1.50",
    )
    node_repo_mock.get_by_ip_in_project.return_value = existing_node

    service = NodeService(node_repo=node_repo_mock, project_repo=project_repo_mock)
    req = NodeRegisterRequest(
        project_id=str(p_id),
        hostname="web-02",
        ip_address="192.168.1.50",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.register_node(req)

    assert exc_info.value.status_code == 409
    assert "already registered" in exc_info.value.detail
