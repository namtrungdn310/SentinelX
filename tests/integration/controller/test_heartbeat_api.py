"""Integration tests for Heartbeat REST API."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session


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
async def test_heartbeat_lifecycle_and_node_online_transition(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test full heartbeat flow:

    1. Create project & register node
    2. Verify initial status is 'unenrolled' and last_seen is None
    3. Generate token & enroll agent
    4. Send heartbeat -> returns 200 OK
    5. Query node -> status has transitioned to 'online' with last_seen set
    6. Send heartbeat with fake agent_id -> 403 Forbidden
    """
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project & register node
        p_res = await client.post("/api/v1/projects", json={"name": "Heartbeat-Project"})
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "linux-agent-01",
                "ip_address": "10.0.0.15",
            },
        )
        node_id = n_res.json()["node_id"]

        # 2. Verify initial state
        get_n_res = await client.get(f"/api/v1/nodes/{node_id}")
        assert get_n_res.json()["status"] == "unenrolled"
        assert get_n_res.json()["last_seen"] is None

        # 3. Issue enrollment token and enroll
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        raw_token = token_res.json()["enrollment_token"]

        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": raw_token,
                "agent_version": "0.1.0",
                "hostname": "linux-agent-01",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]

        # 4. Send valid heartbeat
        now = datetime.now(UTC)
        hb_res = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": now.isoformat(),
            },
        )
        assert hb_res.status_code == 200
        hb_data = hb_res.json()
        assert hb_data["status"] == "ok"
        assert hb_data["next_interval_seconds"] == 10
        assert "received_at" in hb_data

        # 5. Verify node status transitioned to ONLINE and last_seen is set
        node_after_hb = await client.get(f"/api/v1/nodes/{node_id}")
        assert node_after_hb.status_code == 200
        node_data = node_after_hb.json()
        assert node_data["status"] == "online"
        assert node_data["last_seen"] is not None

        # 6. Heartbeat with unapproved/random agent_id -> 403 Forbidden
        bad_agent_id = str(uuid.uuid4())
        bad_hb_res = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": bad_agent_id,
                "sequence": 2,
                "sent_at": now.isoformat(),
            },
        )
        assert bad_hb_res.status_code == 403
        assert "credentials invalid" in bad_hb_res.json()["detail"]
