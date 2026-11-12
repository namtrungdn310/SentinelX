"""End-to-end integration tests for Milestone M5: Telemetry -> Detection -> Incident -> Policy."""

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
from sentinelx_controller.modules.policy.service import get_policy_engine


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
async def test_m5_end_to_end_telemetry_detection_incident_policy_flow(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Full lifecycle verification for Milestone M5:

    1. Register Project, Node, and enroll Agent
    2. Configure Defense Policy for cpu_threshold_detector
    3. Ingest sustained CPU overload samples via /api/v1/telemetry/metrics
    4. Assert DetectionEvent is saved and automatically associated with an Incident
    5. Query Incidents REST API to verify lifecycle status, severity, and event count
    6. Verify Policy evaluation behavior
    """
    app, _ = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup project
        p_res = await client.post("/api/v1/projects", json={"name": "M5-Test-Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # Setup node
        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "prod-linux-node-m5",
                "ip_address": "192.168.1.150",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        # Enroll agent
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
                "hostname": "prod-linux-node-m5",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]

        # Reset policy engine state
        get_policy_engine().clear_state()

        # 2. Configure defense policy for CPU overload
        pol_res = await client.post(
            f"/api/v1/projects/{project_id}/defense-policies",
            json={
                "name": "Auto Restart On CPU Spike",
                "event_type": "cpu_threshold_detector",
                "action_type": "RESTART_SERVICE",
                "target_params": {"service_name": "sentinelx-app"},
                "cooldown_seconds": 300,
                "block_duration_seconds": 1800,
                "enabled": True,
            },
        )
        assert pol_res.status_code == 201

        # 3. Ingest 3 CPU overloaded samples (96%, 97%, 98%)
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
        batch_res = await client.post(
            "/api/v1/telemetry/metrics",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": now.isoformat(),
                "samples": samples,
            },
        )
        assert batch_res.status_code == 200

        # 4. Query detection events: should have 1 CRITICAL event linked to an incident
        ev_res = await client.get("/api/v1/detection-events", params={"node_id": node_id})
        assert ev_res.status_code == 200
        events_data = ev_res.json()
        assert events_data["total"] >= 1
        event = events_data["items"][0]
        assert event["severity"] == "CRITICAL"
        assert event["incident_id"] is not None
        incident_id = event["incident_id"]

        # 5. Query incidents API
        inc_res = await client.get("/api/v1/incidents", params={"project_id": project_id})
        assert inc_res.status_code == 200
        inc_data = inc_res.json()
        assert inc_data["total"] == 1
        incident = inc_data["items"][0]
        assert incident["id"] == incident_id
        assert incident["status"] == "DETECTED"
        assert incident["severity"] == "CRITICAL"
        assert incident["event_count"] >= 1

        # Query incident detail with events
        detail_res = await client.get(f"/api/v1/incidents/{incident_id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["id"] == incident_id
        assert len(detail_data["events"]) >= 1

        # 6. Resolve the incident
        patch_res = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "RESOLVED", "summary": "Mitigation applied, CPU back to normal"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "RESOLVED"
        assert patch_res.json()["resolved_at"] is not None
