"""Integration tests for Defense Actions and Command Pipeline REST API."""

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
async def test_defense_action_lifecycle_and_heartbeat_dispatch(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        proj_res = await client.post(
            "/api/v1/projects",
            json={"name": "Defense Lab"},
        )
        assert proj_res.status_code == 201
        project_id = proj_res.json()["project_id"]

        # 2. Register node
        node_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "node-target",
                "ip_address": "192.168.1.55",
            },
        )
        assert node_res.status_code == 201
        node_id = node_res.json()["node_id"]

        # 3. Create enrollment token & enroll agent
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        assert token_res.status_code == 201
        token = token_res.json()["enrollment_token"]

        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": token,
                "hostname": "node-target",
                "agent_version": "0.1.0",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]
        assert enroll_res.json()["heartbeat_interval_seconds"] == 7

        # 4. Create a manual defense action
        action_payload = {
            "node_id": node_id,
            "action_type": "BLOCK_IP_NFTABLES",
            "target_ip": "198.51.100.22",
            "command_payload": {"duration_seconds": 600},
        }
        create_res = await client.post("/api/v1/defense/actions", json=action_payload)
        assert create_res.status_code == 201
        action_data = create_res.json()
        action_id = action_data["id"]
        assert action_data["status"] == "PENDING"
        assert action_data["target_ip"] == "198.51.100.22"

        # 5. Query action detail
        get_res = await client.get(f"/api/v1/defense/actions/{action_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == action_id

        # 6. List actions
        list_res = await client.get(f"/api/v1/defense/actions?node_id={node_id}")
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1

        # 7. Agent sends Heartbeat -> receives piggybacked command
        hb_res = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": datetime.now(UTC).isoformat(),
            },
        )
        assert hb_res.status_code == 200
        hb_data = hb_res.json()
        assert hb_data["next_interval_seconds"] == 7
        assert len(hb_data["commands"]) == 1
        cmd = hb_data["commands"][0]
        assert cmd["id"] == action_id
        assert cmd["action_type"] == "BLOCK_IP_NFTABLES"
        assert cmd["target_ip"] == "198.51.100.22"

        # 8. Check action transitioned to SENT
        action_sent = (await client.get(f"/api/v1/defense/actions/{action_id}")).json()
        assert action_sent["status"] == "SENT"

        # 9. Agent submits ACK
        ack_res = await client.post(
            f"/api/v1/defense/actions/{action_id}/ack",
            json={
                "action_id": action_id,
                "status": "APPLIED",
                "execution_metadata": {"rule_handle": 105},
            },
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == "ok"

        # 10. Check action transitioned to APPLIED
        action_applied = (await client.get(f"/api/v1/defense/actions/{action_id}")).json()
        assert action_applied["status"] == "APPLIED"
        assert action_applied["agent_ack_at"] is not None

        # 11. Subsequent Heartbeat has no more pending commands
        hb_res2 = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 2,
                "sent_at": datetime.now(UTC).isoformat(),
            },
        )
        assert hb_res2.status_code == 200
        assert len(hb_res2.json()["commands"]) == 0
