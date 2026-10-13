"""Unit tests for Agent Enrollment in NodeService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    EnrollmentStatus,
    EnrollmentTokenCreateRequest,
)
from sentinelx_controller.modules.nodes.models import AgentEnrollmentModel, NodeModel
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
async def test_create_enrollment_token_success(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test generating an enrollment token for an existing node."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    node_repo.get_by_id.return_value = node

    token_record = AgentEnrollmentModel(
        id=uuid.uuid4(),
        node_id=node_id,
        enrollment_token="sx_enroll_testtoken123",
        status=EnrollmentStatus.PENDING.value,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        created_at=datetime.now(UTC),
    )
    enrollment_repo.create_token.return_value = token_record

    resp = await service.create_enrollment_token(
        node_id_str=str(node_id),
        request=EnrollmentTokenCreateRequest(expires_in_hours=24),
    )

    assert resp.node_id == str(node_id)
    assert resp.enrollment_token == "sx_enroll_testtoken123"
    assert resp.status == EnrollmentStatus.PENDING
    enrollment_repo.create_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_enrollment_token_node_not_found_raises_404(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test token creation raises 404 if node does not exist."""
    node_repo, _, _, service = mock_deps
    node_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.create_enrollment_token(
            node_id_str=str(uuid.uuid4()),
            request=EnrollmentTokenCreateRequest(),
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_enroll_agent_success(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test successful agent enrollment with valid pending token."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    node_repo.get_by_id.return_value = node

    token_record = AgentEnrollmentModel(
        id=uuid.uuid4(),
        node_id=node_id,
        enrollment_token="valid_secret_token",
        status=EnrollmentStatus.PENDING.value,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
    )
    enrollment_repo.get_by_token.return_value = token_record

    req = AgentEnrollRequest(
        node_id=str(node_id),
        enrollment_token="valid_secret_token",
        agent_version="0.2.0",
        hostname="srv-01-prod",
        os_info="Ubuntu 24.04 LTS",
    )

    resp = await service.enroll_agent(req)

    assert resp.node_id == str(node_id)
    assert resp.status == "enrolled"
    assert resp.heartbeat_interval_seconds == 10
    enrollment_repo.mark_approved.assert_awaited_once()
    node_repo.update_agent_metadata.assert_awaited_once_with(
        node_id=node_id,
        agent_version="0.2.0",
        hostname="srv-01-prod",
        os_info="Ubuntu 24.04 LTS",
    )


@pytest.mark.asyncio
async def test_enroll_agent_invalid_token_raises_403(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test enrollment with invalid token raises 403 Forbidden."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    enrollment_repo.get_by_token.return_value = None

    req = AgentEnrollRequest(
        node_id=str(node_id),
        enrollment_token="wrong_token",
        hostname="srv-01",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.enroll_agent(req)

    assert exc_info.value.status_code == 403
    assert "Invalid enrollment token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_enroll_agent_revoked_token_raises_403(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test enrollment with revoked token raises 403 Forbidden."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    token_record = AgentEnrollmentModel(
        id=uuid.uuid4(),
        node_id=node_id,
        enrollment_token="revoked_token",
        status=EnrollmentStatus.REVOKED.value,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
    )
    enrollment_repo.get_by_token.return_value = token_record

    req = AgentEnrollRequest(
        node_id=str(node_id),
        enrollment_token="revoked_token",
        hostname="srv-01",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.enroll_agent(req)

    assert exc_info.value.status_code == 403
    assert "revoked" in exc_info.value.detail


@pytest.mark.asyncio
async def test_enroll_agent_expired_token_raises_403(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test enrollment with expired token raises 403 Forbidden."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    token_record = AgentEnrollmentModel(
        id=uuid.uuid4(),
        node_id=node_id,
        enrollment_token="expired_token",
        status=EnrollmentStatus.PENDING.value,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),  # in past
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    enrollment_repo.get_by_token.return_value = token_record

    req = AgentEnrollRequest(
        node_id=str(node_id),
        enrollment_token="expired_token",
        hostname="srv-01",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.enroll_agent(req)

    assert exc_info.value.status_code == 403
    assert "expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_enroll_agent_token_reuse_raises_409(
    mock_deps: tuple[AsyncMock, AsyncMock, AsyncMock, NodeService],
) -> None:
    """Test attempting to reuse an already approved token raises 409 Conflict."""
    node_repo, enrollment_repo, _, service = mock_deps
    node_id = uuid.uuid4()
    node_repo.get_by_id.return_value = NodeModel(
        id=node_id,
        project_id=uuid.uuid4(),
        hostname="srv-01",
        ip_address="192.168.1.10",
    )
    token_record = AgentEnrollmentModel(
        id=uuid.uuid4(),
        node_id=node_id,
        enrollment_token="already_used_token",
        status=EnrollmentStatus.APPROVED.value,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
    )
    enrollment_repo.get_by_token.return_value = token_record

    req = AgentEnrollRequest(
        node_id=str(node_id),
        enrollment_token="already_used_token",
        hostname="srv-01",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.enroll_agent(req)

    assert exc_info.value.status_code == 409
    assert "already been used" in exc_info.value.detail
