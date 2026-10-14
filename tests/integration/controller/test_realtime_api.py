"""Integration tests for Realtime WebSocket API."""

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub, reset_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub


@pytest.fixture
def app_with_db() -> Generator[FastAPI, None, None]:
    """Create test application with in-memory SQLite and isolated RealtimeHub."""
    reset_realtime_hub()
    hub = RealtimeHub()

    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)

    import asyncio

    async def init_models() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_models())

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
    app.dependency_overrides[get_realtime_hub] = lambda: hub

    yield app

    reset_realtime_hub()


def test_websocket_ping_pong_protocol(app_with_db: FastAPI) -> None:
    """Test WebSocket accepts connection and responds to ping with pong."""
    client = TestClient(app_with_db)

    with client.websocket_connect("/api/v1/ws") as ws:
        # Check status endpoint reflects connection
        status_resp = client.get("/api/v1/ws/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["active_connections"] == 1

        # Send ping message
        ws.send_json({"event": "ping"})
        response = ws.receive_json()

        assert response["event"] == "pong"
        assert "timestamp" in response

    # After closing, active connections count updates
    status_after = client.get("/api/v1/ws/status")
    assert status_after.status_code == 200
    assert status_after.json()["active_connections"] == 0


def test_realtime_metric_broadcast_to_websocket(app_with_db: FastAPI) -> None:
    """Test full Milestone F9 vertical slice:

    1. Connect dashboard client via WebSocket
    2. Register project, node, and enroll agent via REST API
    3. Agent pushes telemetry metrics via POST /api/v1/telemetry/metrics
    4. Connected WebSocket immediately receives metric_update event with sample data
    """
    client = TestClient(app_with_db)

    # 1. Register project, node, and enroll agent
    p_res = client.post("/api/v1/projects", json={"name": "Realtime-Project"})
    assert p_res.status_code == 201
    project_id = p_res.json()["project_id"]

    n_res = client.post(
        "/api/v1/nodes",
        json={
            "project_id": project_id,
            "hostname": "realtime-node-01",
            "ip_address": "10.0.1.25",
        },
    )
    assert n_res.status_code == 201
    node_id = n_res.json()["node_id"]

    token_res = client.post(
        f"/api/v1/nodes/{node_id}/enrollment-tokens",
        json={"expires_in_hours": 1},
    )
    raw_token = token_res.json()["enrollment_token"]

    enroll_res = client.post(
        "/api/v1/nodes/enroll",
        json={
            "node_id": node_id,
            "enrollment_token": raw_token,
            "agent_version": "0.1.0",
            "hostname": "realtime-node-01",
        },
    )
    assert enroll_res.status_code == 200
    agent_id = enroll_res.json()["agent_id"]

    # 2. Connect dashboard WebSocket client
    with client.websocket_connect("/api/v1/ws") as ws:
        # 3. Agent posts metric batch
        now = datetime.now(UTC)
        batch_payload = {
            "node_id": node_id,
            "agent_id": agent_id,
            "sequence": 1,
            "sent_at": now.isoformat(),
            "samples": [
                {
                    "observed_at": now.isoformat(),
                    "cpu_percent": 68.5,
                    "memory_percent": 82.0,
                    "disk_percent": 45.0,
                    "network_rx_bytes": 10240,
                    "network_tx_bytes": 4096,
                }
            ],
        }

        metric_res = client.post("/api/v1/telemetry/metrics", json=batch_payload)
        assert metric_res.status_code == 200
        assert metric_res.json()["processed_count"] == 1

        # 4. WebSocket client receives realtime broadcast message
        ws_msg = ws.receive_json()
        assert ws_msg["event"] == "metric_update"
        assert "timestamp" in ws_msg
        assert ws_msg["data"]["node_id"] == node_id
        assert len(ws_msg["data"]["samples"]) == 1
        sample_received = ws_msg["data"]["samples"][0]
        assert sample_received["cpu_percent"] == 68.5
        assert sample_received["memory_percent"] == 82.0
