"""Integration tests for Recovery and Unblock REST API endpoints."""

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
async def test_manual_recovery_revert_flow(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project and node
        p_res = await client.post("/api/v1/projects", json={"name": "Recovery Lab"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "worker-node-01",
                "ip_address": "192.168.10.50",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        # 2. Create a manual defense action (BLOCK_IP_NFTABLES)
        act_res = await client.post(
            "/api/v1/defense/actions",
            json={
                "node_id": node_id,
                "action_type": "BLOCK_IP_NFTABLES",
                "target_ip": "203.0.113.88",
                "command_payload": {"block_duration_seconds": 3600},
            },
        )
        assert act_res.status_code == 201
        action_id = act_res.json()["id"]

        # 3. Simulate action applied
        ack_res = await client.post(
            f"/api/v1/defense/actions/{action_id}/ack",
            json={
                "action_id": action_id,
                "status": "APPLIED",
                "execution_metadata": {"simulated": True},
            },
        )
        assert ack_res.status_code == 200

        # 4. Trigger manual revert via recovery endpoint
        rev_res = await client.post(
            f"/api/v1/recovery/actions/{action_id}/revert",
            json={"reason": "MANUAL_UNBLOCK"},
        )
        assert rev_res.status_code == 201
        rev_data = rev_res.json()
        assert rev_data["defense_action_id"] == action_id
        assert rev_data["reason"] == "MANUAL_UNBLOCK"
        assert rev_data["status"] == "PENDING"
        recovery_id = rev_data["id"]

        # 5. Verify recovery action can be retrieved by ID
        get_res = await client.get(f"/api/v1/recovery/actions/{recovery_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == recovery_id

        # 6. Verify recovery actions list endpoint
        list_res = await client.get("/api/v1/recovery/actions")
        assert list_res.status_code == 200
        assert list_res.json()["total"] >= 1

        # 7. Verify an unblock action was created in defense actions queue
        actions_res = await client.get(f"/api/v1/defense/actions?node_id={node_id}")
        assert actions_res.status_code == 200
        items = actions_res.json()["items"]
        unblock_items = [it for it in items if it["action_type"] == "UNBLOCK_IP_NFTABLES"]
        assert len(unblock_items) == 1
        assert unblock_items[0]["status"] == "PENDING"
        assert unblock_items[0]["target_ip"] == "203.0.113.88"


@pytest.mark.asyncio
async def test_scan_expired_actions_endpoint(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        scan_res = await client.post("/api/v1/recovery/scan-expired")
        assert scan_res.status_code == 200
        assert isinstance(scan_res.json(), list)
