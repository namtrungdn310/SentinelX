"""Integration tests for Detection REST API and telemetry pipeline."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.types import Message, Receive, Scope, Send

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.modules.detection.models import (
    DetectionEventModel,
    DetectionNodeStateModel,
)
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.telemetry.models import TelemetryMetricSampleModel


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


async def register(client: AsyncClient) -> tuple[str, str]:
    project = (await client.post("/api/v1/projects", json={"name": "regression"})).json()
    node = (
        await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project["project_id"],
                "hostname": "host",
                "ip_address": "192.0.2.1",
            },
        )
    ).json()["node_id"]
    token = (await client.post(f"/api/v1/nodes/{node}/enrollment-tokens", json={})).json()
    agent = (
        await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node,
                "enrollment_token": token["enrollment_token"],
                "agent_version": "test",
                "hostname": "host",
            },
        )
    ).json()["agent_id"]
    return node, agent


def metric_batch(
    node: str, agent: str, values: list[float], *, disk: float = 20
) -> dict[str, object]:
    now = datetime.now(UTC) - timedelta(seconds=30)
    return {
        "node_id": node,
        "agent_id": agent,
        "sequence": 1,
        "sent_at": now.isoformat(),
        "samples": [
            {
                "observed_at": (now + timedelta(seconds=i * 5)).isoformat(),
                "cpu_percent": value,
                "memory_percent": 40,
                "disk_percent": disk,
            }
            for i, value in enumerate(values)
        ],
    }


@pytest.mark.asyncio
async def test_prefix_overload_replay_pagination_and_validation(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        node, agent = await register(client)
        batch = metric_batch(node, agent, [98, 98, 98, 20, 20], disk=99)
        assert (await client.post("/api/v1/telemetry/metrics", json=batch)).status_code == 200
        # Simulate a fresh Controller evaluator: persisted cursor must still reject replay.
        del app.state.detection_engine
        assert (await client.post("/api/v1/telemetry/metrics", json=batch)).status_code == 200
        endpoint = f"/api/v1/detection-events?node_id={node}"
        all_events = (await client.get(endpoint)).json()
        assert all_events["total"] == 2
        assert {item["detector_name"] for item in all_events["items"]} == {
            "cpu_threshold_detector",
            "disk_saturation_detector",
        }
        limited = (await client.get(endpoint + "&limit=1")).json()
        assert limited["total"] == 2 and len(limited["items"]) == 1
        assert (await client.get(endpoint + "&severity=invalid")).status_code == 422
        assert (await client.get(endpoint + "&start_time=2026-11-06T00:00:00")).status_code == 422
        assert (
            await client.get(
                endpoint + "&start_time=2026-11-07T00:00:00Z&end_time=2026-11-06T00:00:00Z"
            )
        ).status_code == 422
        naive = metric_batch(node, agent, [98])
        naive["samples"] = [
            {"observed_at": "2026-11-06T00:00:00", "cpu_percent": 98, "memory_percent": 40}
        ]
        assert (await client.post("/api/v1/telemetry/metrics", json=naive)).status_code == 422


@pytest.mark.asyncio
async def test_retry_of_one_sample_is_not_three_observations(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        node, agent = await register(client)
        batch = metric_batch(node, agent, [98])
        for _ in range(3):
            assert (await client.post("/api/v1/telemetry/metrics", json=batch)).status_code == 200
        assert (await client.get(f"/api/v1/detection-events?node_id={node}")).json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["save", "commit"])
async def test_metric_detection_state_atomicity_commit_boundary_and_retry(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    app, factory = test_app
    hub = AsyncMock()
    app.dependency_overrides[get_realtime_hub] = lambda: hub
    failing = False
    counters = {"sessions": 0, "commits": 0}

    async def database() -> AsyncGenerator[AsyncSession, None]:
        counters["sessions"] += 1
        async with factory() as session:
            try:
                yield session
                if failing and failure == "commit":
                    raise RuntimeError("Controlled commit failure")
                await session.commit()
                counters["commits"] += 1
            except BaseException:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = database

    async def checked_app(scope: Scope, receive: Receive, send: Send) -> None:
        async def checked_send(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] < 400:
                assert counters == {"sessions": 1, "commits": 1}
            await send(message)

        await app(scope, receive, checked_send)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as setup:
        node, agent = await register(setup)
    batch = metric_batch(node, agent, [98] * 3)
    hub.broadcast.reset_mock()
    original = DetectionRepository.save_events
    if failure == "save":
        monkeypatch.setattr(
            DetectionRepository,
            "save_events",
            AsyncMock(side_effect=RuntimeError("Controlled save failure")),
        )
    failing = True
    counters.update(sessions=0, commits=0)
    async with AsyncClient(
        transport=ASGITransport(app=checked_app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        assert (await client.post("/api/v1/telemetry/metrics", json=batch)).status_code == 500
        hub.broadcast.assert_not_awaited()
        async with factory() as session:
            for model in (TelemetryMetricSampleModel, DetectionEventModel, DetectionNodeStateModel):
                assert (
                    await session.execute(select(func.count()).select_from(model))
                ).scalar_one() == 0
        monkeypatch.setattr(DetectionRepository, "save_events", original)
        failing = False
        counters.update(sessions=0, commits=0)
        assert (await client.post("/api/v1/telemetry/metrics", json=batch)).status_code == 200
        assert counters == {"sessions": 1, "commits": 1}
        assert hub.broadcast.await_count == 3
        events_sent = [call.args[0].event for call in hub.broadcast.await_args_list]
        assert "metric_update" in events_sent
        assert "detection_alert" in events_sent
        assert "incident_alert" in events_sent
    async with factory() as session:
        assert (
            await session.execute(select(func.count()).select_from(DetectionEventModel))
        ).scalar_one() == 1
        state = (await session.execute(select(DetectionNodeStateModel))).scalar_one()
        assert len(state.state["samples"]) == 3 and state.state["alerts"]


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

        # Each newly registered node has independent transaction-owned DB state.

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
