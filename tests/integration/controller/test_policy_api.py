"""Integration tests for Defense Policy and IP Whitelist REST API."""

import uuid
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
async def test_defense_policy_crud_flow(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup project
        p_res = await client.post("/api/v1/projects", json={"name": "Policy Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # 1. Create defense policy
        pol_payload = {
            "name": "Auto Restart Nginx on High CPU",
            "event_type": "cpu_threshold_detector",
            "action_type": "RESTART_SERVICE",
            "target_params": {"service_name": "nginx"},
            "cooldown_seconds": 300,
            "block_duration_seconds": 1800,
            "enabled": True,
        }
        create_res = await client.post(
            f"/api/v1/projects/{project_id}/defense-policies",
            json=pol_payload,
        )
        assert create_res.status_code == 201
        policy_id = create_res.json()["id"]
        assert create_res.json()["name"] == "Auto Restart Nginx on High CPU"
        assert create_res.json()["action_type"] == "RESTART_SERVICE"

        # 2. List policies
        list_res = await client.get("/api/v1/defense-policies", params={"project_id": project_id})
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1

        # 3. Get single policy
        get_res = await client.get(f"/api/v1/defense-policies/{policy_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == policy_id

        # 4. Patch policy
        patch_res = await client.patch(
            f"/api/v1/defense-policies/{policy_id}",
            json={"cooldown_seconds": 600, "enabled": False},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["cooldown_seconds"] == 600
        assert patch_res.json()["enabled"] is False

        # 5. Delete policy
        del_res = await client.delete(f"/api/v1/defense-policies/{policy_id}")
        assert del_res.status_code == 204

        # Confirm deleted
        get_after = await client.get(f"/api/v1/defense-policies/{policy_id}")
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_ip_whitelist_and_dryrun_evaluation(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup project
        p_res = await client.post("/api/v1/projects", json={"name": "Whitelist Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # 1. Add whitelist entry
        wl_payload = {
            "ip_or_cidr": "192.168.10.0/24",
            "description": "Trusted Dev Subnet",
        }
        create_wl_res = await client.post(
            f"/api/v1/projects/{project_id}/ip-whitelist",
            json=wl_payload,
        )
        assert create_wl_res.status_code == 201
        wl_id = create_wl_res.json()["id"]
        assert create_wl_res.json()["ip_or_cidr"] == "192.168.10.0/24"

        # 2. Invalid CIDR format returns 422
        bad_wl_res = await client.post(
            f"/api/v1/projects/{project_id}/ip-whitelist",
            json={"ip_or_cidr": "invalid-cidr-string"},
        )
        assert bad_wl_res.status_code == 422

        # 3. List whitelist
        list_wl_res = await client.get(f"/api/v1/projects/{project_id}/ip-whitelist")
        assert list_wl_res.status_code == 200
        assert list_wl_res.json()["total"] == 1

        # 4. Dry-run evaluation: Whitelisted IP must be denied
        dry_payload = {
            "event": {
                "node_id": str(uuid.uuid4()),
                "detector_name": "syn_flood_detector",
                "severity": "CRITICAL",
                "attacker_ip": "192.168.10.42",
                "confidence_score": 0.99,
                "details": {
                    "metric_name": "syn_rate",
                    "current_value": 95.0,
                    "threshold_value": 80.0,
                    "window_duration_seconds": 10,
                    "consecutive_samples": 2,
                },
                "detected_at": "2026-11-06T12:00:00Z",
            }
        }
        eval_res = await client.post(
            f"/api/v1/projects/{project_id}/policy/evaluate",
            json=dry_payload,
        )
        assert eval_res.status_code == 200
        eval_data = eval_res.json()
        assert eval_data["authorized"] is False
        assert eval_data["status"] == "DENIED_WHITELIST"
        assert "192.168.10.0/24" in eval_data["reason"]

        # 5. Delete whitelist
        del_wl_res = await client.delete(f"/api/v1/ip-whitelist/{wl_id}")
        assert del_wl_res.status_code == 204
