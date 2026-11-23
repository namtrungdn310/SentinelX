"""Integration tests for Projects and Nodes REST APIs."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session


@pytest.fixture
async def test_app() -> AsyncGenerator[FastAPI, None]:
    """Create isolated in-memory SQLite database for integration tests."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller",
        database=DatabaseSettings(url=test_db_url),
    )
    app = create_app(settings=settings)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session

    yield app

    await engine.dispose()


@pytest.mark.asyncio
async def test_projects_and_nodes_flow(test_app: FastAPI) -> None:
    """Test flow: create project -> register node -> query lists."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        create_p_res = await client.post(
            "/api/v1/projects",
            json={"name": "Production-Alpha", "description": "Primary DC"},
        )
        assert create_p_res.status_code == 201
        p_data = create_p_res.json()
        assert p_data["name"] == "Production-Alpha"
        assert "project_id" in p_data
        project_id = p_data["project_id"]

        # 2. Register node into created project
        create_n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "srv-prod-01",
                "ip_address": "192.168.1.100",
                "os_info": "Ubuntu 22.04 LTS",
            },
        )
        assert create_n_res.status_code == 201
        n_data = create_n_res.json()
        assert n_data["hostname"] == "srv-prod-01"
        assert n_data["status"] == "unenrolled"
        node_id = n_data["node_id"]

        # 3. Duplicate IP in same project -> 409 Conflict
        dup_n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "srv-prod-02",
                "ip_address": "192.168.1.100",
            },
        )
        assert dup_n_res.status_code == 409

        # 4. Get node details
        get_n_res = await client.get(f"/api/v1/nodes/{node_id}")
        assert get_n_res.status_code == 200
        assert get_n_res.json()["ip_address"] == "192.168.1.100"

        # 5. List nodes filtered by project
        list_n_res = await client.get(f"/api/v1/nodes?project_id={project_id}")
        assert list_n_res.status_code == 200
        assert len(list_n_res.json()) == 1

        # 6. Persist project & node settings and push telemetry cadence on heartbeat
        default_settings = await client.get(f"/api/v1/projects/{project_id}/settings")
        assert default_settings.status_code == 200
        assert default_settings.json()["active_profile"] == "balanced"

        update_proj = await client.put(
            f"/api/v1/projects/{project_id}/settings",
            json={"active_profile": "high_sensitivity", "updated_by": "admin@sentinelx.com"},
        )
        assert update_proj.status_code == 200
        assert update_proj.json()["active_profile"] == "high_sensitivity"

        get_proj_settings = await client.get(f"/api/v1/projects/{project_id}/settings")
        assert get_proj_settings.status_code == 200
        assert get_proj_settings.json()["active_profile"] == "high_sensitivity"

        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        assert token_res.status_code == 201
        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": token_res.json()["enrollment_token"],
                "agent_version": "0.1.0",
                "hostname": "srv-prod-01",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]

        hb1 = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": "2026-11-23T10:00:00Z",
                "command_protocol_version": 2,
            },
        )
        assert hb1.status_code == 200
        assert hb1.json()["next_interval_seconds"] == 3
        assert hb1.json()["telemetry_interval_seconds"] == 2.0

        node_override = await client.put(
            f"/api/v1/nodes/{node_id}/settings",
            json={"active_profile": "resource_saving"},
        )
        assert node_override.status_code == 200
        hb2 = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 2,
                "sent_at": "2026-11-23T10:00:10Z",
                "command_protocol_version": 2,
            },
        )
        assert hb2.status_code == 200
        assert hb2.json()["next_interval_seconds"] == 10
        assert hb2.json()["telemetry_interval_seconds"] == 10.0
