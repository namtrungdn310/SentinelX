"""Integration tests for Telemetry REST API."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

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
async def test_telemetry_vertical_slice(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test full telemetry vertical slice:

    1. Register project, node, and enroll agent
    2. Dispatch batch of 3 metric samples via POST /api/v1/telemetry/metrics
    3. Query metrics via GET /api/v1/telemetry/nodes/{node_id}/metrics
    4. Verify sample data, ordering, and limit parameter
    """
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup project & node
        p_res = await client.post("/api/v1/projects", json={"name": "Telemetry-Project"})
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "monitored-server-01",
                "ip_address": "192.168.1.100",
            },
        )
        node_id = n_res.json()["node_id"]

        # Enroll agent
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        enrollment_token = token_res.json()["enrollment_token"]

        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": enrollment_token,
                "agent_version": "0.1.0",
                "hostname": "monitored-server-01",
            },
        )
        agent_id = enroll_res.json()["agent_id"]

        # 2. Post batch of 3 metrics
        t0 = datetime(2026, 10, 14, 10, 0, 0, tzinfo=UTC)
        samples_data = [
            {
                "observed_at": (t0 + timedelta(seconds=1)).isoformat(),
                "cpu_percent": 15.5,
                "memory_percent": 30.2,
                "disk_percent": 45.0,
                "network_rx_bytes": 1000,
                "network_tx_bytes": 500,
            },
            {
                "observed_at": (t0 + timedelta(seconds=2)).isoformat(),
                "cpu_percent": 25.0,
                "memory_percent": 32.0,
                "disk_percent": 45.0,
                "network_rx_bytes": 2000,
                "network_tx_bytes": 1200,
            },
            {
                "observed_at": (t0 + timedelta(seconds=3)).isoformat(),
                "cpu_percent": 55.8,
                "memory_percent": 35.1,
                "disk_percent": 45.0,
                "network_rx_bytes": 3500,
                "network_tx_bytes": 2100,
            },
        ]

        batch_res = await client.post(
            "/api/v1/telemetry/metrics",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": (t0 + timedelta(seconds=4)).isoformat(),
                "samples": samples_data,
            },
        )
        assert batch_res.status_code == 200
        batch_body = batch_res.json()
        assert batch_body["status"] == "ok"
        assert batch_body["processed_count"] == 3
        assert "received_at" in batch_body

        # 3. Query all metrics for node
        query_res = await client.get(f"/api/v1/telemetry/nodes/{node_id}/metrics")
        assert query_res.status_code == 200
        query_data = query_res.json()
        assert query_data["node_id"] == node_id
        assert query_data["count"] == 3
        assert len(query_data["samples"]) == 3

        # Samples ordered by observed_at descending: newest first
        assert query_data["samples"][0]["cpu_percent"] == 55.8
        assert query_data["samples"][1]["cpu_percent"] == 25.0
        assert query_data["samples"][2]["cpu_percent"] == 15.5

        # 4. Query with limit=2
        limit_res = await client.get(f"/api/v1/telemetry/nodes/{node_id}/metrics?limit=2")
        assert limit_res.status_code == 200
        limit_data = limit_res.json()
        assert limit_data["count"] == 2
        assert len(limit_data["samples"]) == 2
        assert limit_data["samples"][0]["cpu_percent"] == 55.8


@pytest.mark.asyncio
async def test_telemetry_unverified_agent_rejected_403(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test telemetry ingestion fails with 403 when agent is not enrolled."""
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project and node
        p_res = await client.post("/api/v1/projects", json={"name": "P-Unverified"})
        project_id = p_res.json()["project_id"]
        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "node-unverified",
                "ip_address": "10.0.0.99",
            },
        )
        node_id = n_res.json()["node_id"]

        now = datetime.now(UTC)
        fake_agent_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/telemetry/metrics",
            json={
                "node_id": node_id,
                "agent_id": fake_agent_id,
                "sequence": 1,
                "sent_at": now.isoformat(),
                "samples": [
                    {
                        "observed_at": now.isoformat(),
                        "cpu_percent": 10.0,
                        "memory_percent": 20.0,
                    }
                ],
            },
        )
        assert resp.status_code == 403
        assert "Agent credentials invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_telemetry_query_nonexistent_node_404(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test querying metrics for nonexistent node returns 404."""
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        non_existent_node_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/telemetry/nodes/{non_existent_node_id}/metrics")
        assert resp.status_code == 404
