"""Integration tests for Agent Enrollment REST APIs."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.nodes.models import AgentEnrollmentModel


@pytest.fixture
async def test_app() -> AsyncGenerator[tuple[FastAPI, async_sessionmaker[AsyncSession]], None]:
    """Create isolated in-memory SQLite database and test application."""
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

    yield app, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_enrollment_complete_lifecycle(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test full agent enrollment lifecycle:

    1. Create project
    2. Register node
    3. Issue enrollment token
    4. Verify list tokens
    5. Test invalid token failure (403)
    6. Enroll agent with valid token (200)
    7. Test token reuse prevention (409)
    8. Issue second token and revoke it
    9. Test revoked token failure (403)
    10. Verify node has updated agent metadata
    """
    app, session_factory = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        p_res = await client.post(
            "/api/v1/projects",
            json={"name": "Security-Lab", "description": "Enrollment test workspace"},
        )
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # 2. Register node
        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "linux-worker-01",
                "ip_address": "10.10.1.50",
                "os_info": "Ubuntu 22.04 LTS",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        # 3. Issue enrollment token
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 12},
        )
        assert token_res.status_code == 201
        token_data = token_res.json()
        assert token_data["node_id"] == node_id
        assert token_data["status"] == "pending"
        raw_token = token_data["enrollment_token"]
        assert raw_token.startswith("sx_enroll_")
        token_id = token_data["token_id"]

        # 4. List tokens for node
        list_tokens_res = await client.get(f"/api/v1/nodes/{node_id}/enrollment-tokens")
        assert list_tokens_res.status_code == 200
        tokens_list = list_tokens_res.json()
        assert len(tokens_list) == 1
        assert tokens_list[0]["token_id"] == token_id

        # 5. Invalid token fails with 403
        bad_enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": "sx_enroll_nonexistent_secret",
                "agent_version": "0.1.0",
                "hostname": "linux-worker-01",
            },
        )
        assert bad_enroll_res.status_code == 403

        # 6. Valid enrollment succeeds with 200
        valid_enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": raw_token,
                "agent_version": "0.1.5",
                "hostname": "linux-worker-01-prod",
                "os_info": "Ubuntu 24.04 LTS (kernel 6.8)",
            },
        )
        assert valid_enroll_res.status_code == 200
        enroll_data = valid_enroll_res.json()
        assert enroll_data["node_id"] == node_id
        assert "agent_id" in enroll_data
        assert enroll_data["status"] == "enrolled"
        assert enroll_data["heartbeat_interval_seconds"] == 10

        # 7. Token reuse rejected with 409 Conflict
        reuse_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": raw_token,
                "agent_version": "0.1.5",
                "hostname": "linux-worker-01-prod",
            },
        )
        assert reuse_res.status_code == 409
        assert "already been used" in reuse_res.json()["detail"]

        # 8. Issue second token and revoke it
        token2_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        assert token2_res.status_code == 201
        token2_id = token2_res.json()["token_id"]
        token2_secret = token2_res.json()["enrollment_token"]

        revoke_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens/{token2_id}/revoke"
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["status"] == "revoked"

        # 9. Enroll with revoked token fails with 403
        revoked_enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": token2_secret,
                "hostname": "linux-worker-01",
            },
        )
        assert revoked_enroll_res.status_code == 403
        assert "revoked" in revoked_enroll_res.json()["detail"]

        # 10. Verify node record details updated with reported agent metadata
        get_node_res = await client.get(f"/api/v1/nodes/{node_id}")
        assert get_node_res.status_code == 200
        node_details = get_node_res.json()
        assert node_details["hostname"] == "linux-worker-01-prod"
        assert node_details["os_info"] == "Ubuntu 24.04 LTS (kernel 6.8)"


@pytest.mark.asyncio
async def test_agent_enrollment_expired_token(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test that expired token returns 403 Forbidden."""
    app, session_factory = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project & node
        p_res = await client.post(
            "/api/v1/projects",
            json={"name": "Expiry-Lab"},
        )
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "linux-worker-expiry",
                "ip_address": "10.10.1.60",
            },
        )
        node_id = n_res.json()["node_id"]

        # Issue token
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        raw_token = token_res.json()["enrollment_token"]

        # Update token to be expired in the DB
        async with session_factory() as session:
            stmt = select(AgentEnrollmentModel).where(
                AgentEnrollmentModel.enrollment_token == raw_token
            )
            record = (await session.execute(stmt)).scalar_one()
            record.expires_at = datetime.now(UTC) - timedelta(hours=2)
            await session.commit()

        # Try to enroll with expired token -> 403
        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": raw_token,
                "hostname": "linux-worker-expiry",
            },
        )
        assert enroll_res.status_code == 403
        assert "expired" in enroll_res.json()["detail"]
