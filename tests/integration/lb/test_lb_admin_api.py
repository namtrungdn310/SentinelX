"""Integration tests for SentinelX Load Balancer dynamic Admin Control Plane APIs."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sentinelx_lb.config import BackendConfig, HealthCheckConfig, LBAlgorithm, LBSettings
from sentinelx_lb.server import create_app


class MockBackend:
    def __init__(self, name: str) -> None:
        self.name = name
        self.alive = True
        self.app = web.Application()
        self.app.router.add_get("/health", self._health)
        self.app.router.add_get("/api/ping", self._ping)
        self.server: TestServer | None = None

    async def _health(self, _req: web.Request) -> web.Response:
        if self.alive:
            return web.json_response({"status": "ok", "node": self.name}, status=200)
        return web.json_response({"status": "down", "node": self.name}, status=503)

    async def _ping(self, _req: web.Request) -> web.Response:
        return web.json_response({"node": self.name}, status=200)

    async def start(self) -> str:
        self.server = TestServer(self.app)
        await self.server.start_server()
        return str(self.server.make_url("")).rstrip("/")

    async def stop(self) -> None:
        if self.server:
            await self.server.close()


@pytest.fixture
async def two_backends() -> AsyncGenerator[tuple[MockBackend, MockBackend, str, str], None]:
    b1 = MockBackend("node-1")
    b2 = MockBackend("node-2")
    url1 = await b1.start()
    url2 = await b2.start()
    yield b1, b2, url1, url2
    await b1.stop()
    await b2.stop()


@pytest.mark.asyncio
async def test_lb_admin_auth_and_dynamic_config_sync(
    two_backends: tuple[MockBackend, MockBackend, str, str],
) -> None:
    _b1, _b2, url1, url2 = two_backends
    settings = LBSettings(
        backends=[BackendConfig(url=url1)],
        algorithm=LBAlgorithm.ROUND_ROBIN,
        admin_token="secret-lb-token",
        health_check=HealthCheckConfig(enabled=False),
    )
    app = create_app(settings)

    async with TestClient(TestServer(app)) as client:
        # Missing/wrong token is rejected with 401
        unauth = await client.patch("/lb/admin/algorithm", json={"algorithm": "least_in_flight"})
        assert unauth.status == 401

        headers = {"Authorization": "Bearer secret-lb-token"}

        # Hot-sync 2 backends + switch algorithm via PUT /lb/admin/config
        put_res = await client.put(
            "/lb/admin/config",
            headers=headers,
            json={
                "algorithm": "least_in_flight",
                "backends": [{"url": url1}, {"url": url2}],
                "health_check": {
                    "enabled": False,
                    "path": "/health",
                    "interval_seconds": 3.0,
                    "failure_threshold": 3,
                    "success_threshold": 2,
                },
            },
        )
        assert put_res.status == 200
        body = await put_res.json()
        assert body["algorithm"] == "least_in_flight"
        assert body["pool"]["total_backends"] == 2
        assert body["pool"]["routable_backends"] == 2

        # Verify both backends actually serve traffic
        seen_nodes = set()
        for _ in range(4):
            res = await client.get("/api/ping")
            assert res.status == 200
            seen_nodes.add((await res.json())["node"])
        assert seen_nodes == {"node-1", "node-2"}


@pytest.mark.asyncio
async def test_lb_admin_drain_guard_and_health_check_isolation(
    two_backends: tuple[MockBackend, MockBackend, str, str],
) -> None:
    b1, b2, url1, url2 = two_backends
    settings = LBSettings(
        backends=[BackendConfig(url=url1), BackendConfig(url=url2)],
        algorithm=LBAlgorithm.ROUND_ROBIN,
        health_check=HealthCheckConfig(
            enabled=True,
            path="/health",
            interval_seconds=0.1,
            failure_threshold=2,
            success_threshold=1,
        ),
    )
    app = create_app(settings)

    async with TestClient(TestServer(app)) as client:
        # Drain node-2 -> 100% traffic goes to node-1
        drain_res = await client.post(
            "/lb/admin/backends/state",
            json={"identifier": url2, "enabled": False},
        )
        assert drain_res.status == 200
        assert (await drain_res.json())["pool"]["routable_backends"] == 1

        # Healthy probe on node-2 must NOT override admin_enabled=False
        await asyncio.sleep(0.35)
        status_after = await (await client.get("/lb/status")).json()
        b2_state = next(
            item
            for item in status_after["pool"]["backends"]
            if item["url"] == url2
        )
        assert b2_state["is_healthy"] is True
        assert b2_state["admin_enabled"] is False
        assert status_after["pool"]["routable_backends"] == 1

        # Attempting to drain the last routable backend without force=true fails with 409
        last_drain = await client.post(
            "/lb/admin/backends/state",
            json={"identifier": url1, "enabled": False},
        )
        assert last_drain.status == 409

        # With force=true, draining succeeds (traffic now returns 503 when none routable)
        forced_drain = await client.post(
            "/lb/admin/backends/state",
            json={"identifier": url1, "enabled": False, "force": True},
        )
        assert forced_drain.status == 200
        assert (await forced_drain.json())["pool"]["routable_backends"] == 0
        no_backend_res = await client.get("/api/ping")
        assert no_backend_res.status == 503

        # Keep b1 healthy when re-enabled
        re_enable = await client.post(
            "/lb/admin/backends/state",
            json={"identifier": url1, "enabled": True},
        )
        assert re_enable.status == 200
        assert (await client.get("/api/ping")).status == 200
