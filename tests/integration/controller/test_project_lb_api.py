"""Integration tests for Controller per-project dynamic Load Balancer APIs."""

from collections.abc import AsyncGenerator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app as create_controller_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_lb.config import HealthCheckConfig, LBAlgorithm, LBSettings
from sentinelx_lb.server import create_app as create_lb_app


@pytest.fixture
async def live_lb_server() -> AsyncGenerator[str, None]:
    """Run a live in-process sentinelx_lb instance for Controller sync verification."""
    lb_app = create_lb_app(
        LBSettings(
            backends=[],
            algorithm=LBAlgorithm.ROUND_ROBIN,
            admin_token="ctrl-sync-secret",
            health_check=HealthCheckConfig(enabled=False),
        )
    )
    server = TestServer(lb_app)
    await server.start_server()
    yield str(server.make_url("")).rstrip("/")
    await server.close()


@pytest.fixture
async def dummy_backend() -> AsyncGenerator[tuple[str, int], None]:
    async def _health(_req: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_get("/health", _health)
    server = TestServer(app)
    await server.start_server()
    assert server.host is not None and server.port is not None
    yield server.host, server.port
    await server.close()


@pytest.fixture
async def controller_app() -> AsyncGenerator[FastAPI, None]:
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller-lb",
        database=DatabaseSettings(url=test_db_url),
        lb_admin_token="ctrl-sync-secret",
    )
    app = create_controller_app(settings=settings)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield app
    await engine.dispose()


@pytest.mark.asyncio
async def test_controller_per_project_dynamic_lb_lifecycle(
    controller_app: FastAPI,
    live_lb_server: str,
    dummy_backend: tuple[str, int],
) -> None:
    host_ip, backend_port = dummy_backend
    transport = ASGITransport(app=controller_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a Type-1 standalone project (LB disabled by default)
        p_standalone = await client.post(
            "/api/v1/projects",
            json={"name": "DB Standalone", "description": "Single node monitoring"},
        )
        assert p_standalone.status_code == 201
        standalone_id = p_standalone.json()["project_id"]
        assert p_standalone.json()["load_balancer"]["enabled"] is False

        disabled_status = await client.get(f"/api/v1/projects/{standalone_id}/load-balancer")
        assert disabled_status.status_code == 200
        assert disabled_status.json()["sync_status"] == "disabled"

        # 2. Enable LB on the project afterward and attach live LB URL
        enable_res = await client.put(
            f"/api/v1/projects/{standalone_id}/load-balancer",
            json={
                "enabled": True,
                "lb_url": live_lb_server,
                "algorithm": "round_robin",
                "health_path": "/health",
                "health_interval_seconds": 3.0,
                "failure_threshold": 3,
                "success_threshold": 2,
            },
        )
        assert enable_res.status_code == 200
        assert enable_res.json()["reachable"] is True
        assert enable_res.json()["sync_status"] == "synced"

        # 3. Register two nodes with distinct IPs: one standalone, one lb_backend
        n1_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": standalone_id,
                "hostname": "worker-standalone",
                "ip_address": "127.0.0.2" if host_ip != "127.0.0.2" else "127.0.0.3",
                "lb_role": "standalone",
            },
        )
        assert n1_res.status_code == 201
        n1_id = n1_res.json()["node_id"]

        n2_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": standalone_id,
                "hostname": "web-backend-01",
                "ip_address": host_ip,
                "lb_role": "lb_backend",
                "lb_backend_port": backend_port,
            },
        )
        assert n2_res.status_code == 201
        n2_id = n2_res.json()["node_id"]

        # Runtime status from LB must now have web-backend-01 in pool
        lb_status = await client.get(f"/api/v1/projects/{standalone_id}/load-balancer")
        assert lb_status.status_code == 200
        status_json = lb_status.json()
        assert status_json["total_backends"] == 1
        assert status_json["backends"][0]["node_id"] == n2_id
        assert status_json["backends"][0]["url"].endswith(f":{backend_port}")

        # 4. Promote worker-standalone to lb_backend via PATCH /nodes/{id}
        promote_res = await client.patch(
            f"/api/v1/nodes/{n1_id}",
            json={"lb_role": "lb_backend", "lb_backend_port": backend_port + 1},
        )
        assert promote_res.status_code == 200
        assert promote_res.json()["lb_role"] == "lb_backend"

        # 5. Switch algorithm via Controller API
        algo_res = await client.patch(
            f"/api/v1/projects/{standalone_id}/load-balancer/algorithm",
            json={"algorithm": "least_in_flight"},
        )
        assert algo_res.status_code == 200
        assert algo_res.json()["algorithm"] == "least_in_flight"
        assert algo_res.json()["total_backends"] == 2

        # 6. Drain n1 from Controller API
        drain_res = await client.post(
            f"/api/v1/projects/{standalone_id}/load-balancer/backends/{n1_id}/state",
            json={"enabled": False},
        )
        assert drain_res.status_code == 200
        drained = next(b for b in drain_res.json()["backends"] if b["node_id"] == n1_id)
        assert drained["admin_enabled"] is False
        assert drained["is_healthy"] is True


@pytest.mark.asyncio
async def test_controller_fails_soft_when_lb_unreachable(controller_app: FastAPI) -> None:
    transport = ASGITransport(app=controller_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post(
            "/api/v1/projects",
            json={
                "name": "Offline LB Project",
                "load_balancer": {
                    "enabled": True,
                    "lb_url": "http://127.0.0.1:59999",
                    "algorithm": "round_robin",
                    "health_path": "/health",
                    "health_interval_seconds": 3.0,
                    "failure_threshold": 3,
                    "success_threshold": 2,
                },
            },
        )
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        status_res = await client.get(f"/api/v1/projects/{project_id}/load-balancer")
        assert status_res.status_code == 200
        body = status_res.json()
        assert body["enabled"] is True
        assert body["reachable"] is False
        assert body["sync_status"] == "unreachable"


@pytest.mark.asyncio
async def test_controller_uses_system_default_lb_url_when_project_url_is_null(
    controller_app: FastAPI,
    live_lb_server: str,
) -> None:
    controller_app.state.settings.default_lb_url = live_lb_server
    transport = ASGITransport(app=controller_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post(
            "/api/v1/projects",
            json={
                "name": "System Default LB Project",
                "load_balancer": {
                    "enabled": True,
                    "lb_url": None,
                    "algorithm": "least_in_flight",
                },
            },
        )
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        status_res = await client.get(f"/api/v1/projects/{project_id}/load-balancer")
        assert status_res.status_code == 200
        body = status_res.json()
        assert body["enabled"] is True
        assert body["reachable"] is True
        assert body["sync_status"] == "synced"
        assert body["lb_url"] == live_lb_server
        assert body["algorithm"] == "least_in_flight"
