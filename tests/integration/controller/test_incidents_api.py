"""Integration tests for Incidents REST API."""

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
from sentinelx_controller.modules.incidents.models import IncidentModel


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
async def test_incidents_crud_flow(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup project
        p_res = await client.post("/api/v1/projects", json={"name": "Incidents Project"})
        assert p_res.status_code == 201
        project_id = uuid.UUID(p_res.json()["project_id"])

        # Insert test incident directly
        incident_id = uuid.uuid4()
        async with session_factory() as session:
            inc = IncidentModel(
                id=incident_id,
                project_id=project_id,
                title="Brute Force Attempt",
                status="DETECTED",
                severity="HIGH",
                started_at=datetime.now(UTC),
                summary="Initial detection",
            )
            session.add(inc)
            await session.commit()

        # 2. List incidents
        list_res = await client.get("/api/v1/incidents", params={"project_id": str(project_id)})
        assert list_res.status_code == 200
        data = list_res.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(incident_id)
        assert data["items"][0]["status"] == "DETECTED"

        # 3. Get single incident detail
        get_res = await client.get(f"/api/v1/incidents/{incident_id}")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["id"] == str(incident_id)
        assert "events" in detail

        # 4. Patch incident status to RESOLVED
        patch_res = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "RESOLVED", "summary": "Mitigation applied successfully"},
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["status"] == "RESOLVED"
        assert updated["resolved_at"] is not None
        assert updated["summary"] == "Mitigation applied successfully"

        # 5. Invalid UUID format returns 422
        bad_res = await client.get("/api/v1/incidents/not-a-valid-uuid")
        assert bad_res.status_code == 422

        # 6. Not found returns 404
        missing_res = await client.get(f"/api/v1/incidents/{uuid.uuid4()}")
        assert missing_res.status_code == 404
