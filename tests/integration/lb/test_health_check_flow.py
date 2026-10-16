"""Integration tests for Load Balancer active health check, ejection, and re-add flow."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sentinelx_lb.config import BackendConfig, HealthCheckConfig, LBAlgorithm, LBSettings
from sentinelx_lb.pool import BackendHealthState
from sentinelx_lb.server import create_app


class StatefulBackendServer:
    """Mock backend server capable of toggling /health response dynamically."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_alive = True
        self.app = web.Application()
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/api/data", self.handle_service)
        self.server: TestServer | None = None

    async def handle_health(self, _request: web.Request) -> web.Response:
        if self.is_alive:
            return web.json_response({"status": "healthy", "server": self.name}, status=200)
        return web.json_response({"status": "down", "server": self.name}, status=500)

    async def handle_service(self, _request: web.Request) -> web.Response:
        return web.json_response({"served_by": self.name}, status=200)

    async def start(self) -> TestServer:
        self.server = TestServer(self.app)
        await self.server.start_server()
        return self.server

    async def stop(self) -> None:
        if self.server:
            await self.server.close()


@pytest.fixture
async def backend_1() -> AsyncGenerator[StatefulBackendServer, None]:
    b1 = StatefulBackendServer("backend-1")
    await b1.start()
    yield b1
    await b1.stop()


@pytest.fixture
async def backend_2() -> AsyncGenerator[StatefulBackendServer, None]:
    b2 = StatefulBackendServer("backend-2")
    await b2.start()
    yield b2
    await b2.stop()


@pytest.mark.asyncio
async def test_active_health_check_ejection_and_readd_lifecycle(
    backend_1: StatefulBackendServer,
    backend_2: StatefulBackendServer,
) -> None:
    """Full lifecycle test matching PBL4 Milestone F13 acceptance:

    1. Both backends healthy -> traffic alternates 01 / 02
    2. Backend 02 health check fails -> ejected -> 100% traffic routes to 01
    3. Backend 02 recovers -> re-added -> traffic resumes alternating 01 / 02
    """
    assert backend_1.server is not None
    assert backend_2.server is not None

    b1_port = backend_1.server.port
    b2_port = backend_2.server.port

    settings = LBSettings(
        backends=[
            BackendConfig(url=f"http://127.0.0.1:{b1_port}", name="srv-1"),
            BackendConfig(url=f"http://127.0.0.1:{b2_port}", name="srv-2"),
        ],
        algorithm=LBAlgorithm.ROUND_ROBIN,
        health_check=HealthCheckConfig(
            path="/health",
            interval_seconds=0.15,
            timeout_seconds=0.1,
            failure_threshold=2,
            success_threshold=2,
            enabled=True,
        ),
    )

    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        # Give health checker time to probe initial state (2 probes = ~0.35s)
        await asyncio.sleep(0.35)

        # -------------------------------------------------------------
        # STEP 1: Both backends healthy -> traffic alternates evenly
        # -------------------------------------------------------------
        res1 = await client.get("/api/data")
        assert res1.status == 200
        server1 = (await res1.json())["served_by"]

        res2 = await client.get("/api/data")
        assert res2.status == 200
        server2 = (await res2.json())["served_by"]

        assert {server1, server2} == {"backend-1", "backend-2"}

        # -------------------------------------------------------------
        # STEP 2: Stop backend 2 health -> Ejection occurs
        # -------------------------------------------------------------
        backend_2.is_alive = False

        # Wait for 2 probe cycles (0.15s * 2 = 0.3s + margin = 0.4s)
        await asyncio.sleep(0.4)

        # Inspect pool status via /lb/status
        status_res = await client.get("/lb/status")
        assert status_res.status == 200
        status_data = await status_res.json()

        assert status_data["pool"]["healthy_backends"] == 1
        b2_info = [b for b in status_data["pool"]["backends"] if b["name"] == "srv-2"][0]
        assert b2_info["is_healthy"] is False
        assert b2_info["health_state"] == BackendHealthState.UNHEALTHY.value

        # Client sends 4 consecutive requests: 100% must route to backend-1
        for _ in range(4):
            req = await client.get("/api/data")
            assert req.status == 200
            assert (await req.json())["served_by"] == "backend-1"

        # -------------------------------------------------------------
        # STEP 3: Recover backend 2 -> Re-add occurs
        # -------------------------------------------------------------
        backend_2.is_alive = True

        # Wait for 2 successful probe cycles (0.15s * 2 = 0.3s + margin = 0.4s)
        await asyncio.sleep(0.4)

        # Inspect pool status
        status_res2 = await client.get("/lb/status")
        status_data2 = await status_res2.json()
        assert status_data2["pool"]["healthy_backends"] == 2

        b2_recovered = [b for b in status_data2["pool"]["backends"] if b["name"] == "srv-2"][0]
        assert b2_recovered["is_healthy"] is True
        assert b2_recovered["health_state"] == BackendHealthState.HEALTHY.value

        # Traffic resumes distributing across both backends
        res_a = await client.get("/api/data")
        res_b = await client.get("/api/data")
        servers = {(await res_a.json())["served_by"], (await res_b.json())["served_by"]}
        assert servers == {"backend-1", "backend-2"}

    finally:
        await client.close()
