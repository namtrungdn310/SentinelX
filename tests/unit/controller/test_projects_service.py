"""Unit tests for ProjectService."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.projects import ProjectCreateRequest
from sentinelx_controller.modules.projects.models import ProjectModel
from sentinelx_controller.modules.projects.repository import ProjectRepository
from sentinelx_controller.modules.projects.service import ProjectService


@pytest.mark.asyncio
async def test_create_project_duplicate_name_raises_conflict() -> None:
    repo_mock = AsyncMock(spec=ProjectRepository)
    existing_model = ProjectModel(
        id=uuid.uuid4(),
        name="Existing-Project",
        description="Test",
    )
    repo_mock.get_by_name.return_value = existing_model

    service = ProjectService(repo_mock)
    req = ProjectCreateRequest(name="Existing-Project", description="New description")

    with pytest.raises(HTTPException) as exc_info:
        await service.create_project(req)

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_project_invalid_uuid_raises_422() -> None:
    repo_mock = AsyncMock(spec=ProjectRepository)
    service = ProjectService(repo_mock)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_project("invalid-uuid-string")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_get_project_not_found_raises_404() -> None:
    repo_mock = AsyncMock(spec=ProjectRepository)
    repo_mock.get_by_id.return_value = None

    service = ProjectService(repo_mock)
    test_id = str(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await service.get_project(test_id)

    assert exc_info.value.status_code == 404
