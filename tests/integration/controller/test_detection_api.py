"""Integration tests for Detection REST API and telemetry pipeline."""

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
from sentinelx_controller.modules.detection.service import get_detection_engine


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
async def test_telemetry_overload_triggers_detection_event(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Test full detection integration:

    1. Register project, node, and enroll agent
    2. Dispatch 3 overloaded CPU metric samples via POST /api/v1/telemetry/metrics
    3. Query detection events via GET /api/v1/detection-events
    4. Verify detection event data, severity and detector name
    5. Query single event by ID via GET /api/v1/detection-events/{event_id}
    """
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup project & node
        p_res = await client.post("/api/v1/projects", json={"name": "Detection-Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "monitored-server-m3",
                "ip_address": "192.168.1.120",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        # Enroll agent via nodes router
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        assert token_res.status_code == 201
        enrollment_token = token_res.json()["enrollment_token"]

        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": enrollment_token,
                "agent_version": "0.1.0",
                "hostname": "monitored-server-m3",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]

        # Reset detection engine state for this node
        engine = get_detection_engine()
        engine.clear_node_state(uuid.UUID(node_id))

        # 2. Ingest 3 CPU overloaded samples (96%, 97%, 98%)
        now = datetime.now(UTC)
        samples = [
            {
                "observed_at": now.isoformat(),
                "cpu_percent": 96.0,
                "memory_percent": 45.0,
                "disk_percent": 30.0,
            },
            {
                "observed_at": (now + timedelta(seconds=5)).isoformat(),
                "cpu_percent": 97.0,
                "memory_percent": 45.0,
                "disk_percent": 30.0,
            },
            {
                "observed_at": (now + timedelta(seconds=10)).isoformat(),
                "cpu_percent": 98.0,
                "memory_percent": 45.0,
                "disk_percent": 30.0,
            },
        ]
        metric_batch = {
            "node_id": node_id,
            "agent_id": agent_id,
            "sequence": 1,
            "sent_at": (now + timedelta(seconds=10)).isoformat(),
            "samples": samples,
        }

        ingest_res = await client.post("/api/v1/telemetry/metrics", json=metric_batch)
        assert ingest_res.status_code == 200
        assert ingest_res.json()["processed_count"] == 3

        # 3. Query GET /api/v1/detection-events
        events_res = await client.get(f"/api/v1/detection-events?node_id={node_id}")
        assert events_res.status_code == 200
        data = events_res.json()
        assert data["total"] >= 1
        event = data["items"][0]
        assert event["node_id"] == node_id
        assert event["detector_name"] == "cpu_threshold_detector"
        assert event["severity"] == "CRITICAL"
        assert event["details"]["metric_name"] == "cpu_percent"
        assert event["details"]["current_value"] == 98.0

        # 4. Query single event by ID
        event_id = event["id"]
        single_res = await client.get(f"/api/v1/detection-events/{event_id}")
        assert single_res.status_code == 200
        single_data = single_res.json()
        assert single_data["id"] == event_id
        assert single_data["severity"] == "CRITICAL"
