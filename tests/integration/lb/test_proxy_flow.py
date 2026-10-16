"""Integration tests for SentinelX HTTP Reverse Proxy and Load Balancer flow."""

from collections.abc import AsyncGenerator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sentinelx_lb.config import BackendConfig, LBAlgorithm, LBSettings
from sentinelx_lb.server import create_app


@pytest.fixture
async def mock_upstream_a() -> AsyncGenerator[TestServer, None]:
    """Mock upstream backend server A."""
    app = web.Application()

    async def handle_ping(_request: web.Request) -> web.Response:
        return web.json_response({"server": "backend_a", "status": "ok"})

    async def handle_echo(request: web.Request) -> web.Response:
        body = await request.json()
        headers = dict(request.headers)
        return web.json_response({
            "server": "backend_a",
            "received_body": body,
            "received_headers": headers,
        })

    app.router.add_get("/ping", handle_ping)
    app.router.add_post("/echo", handle_echo)

    server = TestServer(app)
    await server.start_server()
    yield server
    await server.close()


@pytest.fixture
async def mock_upstream_b() -> AsyncGenerator[TestServer, None]:
    """Mock upstream backend server B."""
    app = web.Application()

    async def handle_ping(_request: web.Request) -> web.Response:
        return web.json_response({"server": "backend_b", "status": "ok"})

    app.router.add_get("/ping", handle_ping)

    server = TestServer(app)
    await server.start_server()
    yield server
    await server.close()


@pytest.mark.asyncio
async def test_lb_health_and_status_endpoints() -> None:
    """Verify /health and /lb/status management routes on Load Balancer."""
    settings = LBSettings(
        backends=[BackendConfig(url="http://10.0.1.1:8000", name="srv1")],
        algorithm=LBAlgorithm.ROUND_ROBIN,
    )
    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        # 1. Health check
        res_health = await client.get("/health")
        assert res_health.status == 200
        health_data = await res_health.json()
        assert health_data["status"] == "healthy"
        assert health_data["service"] == "sentinelx-lb"

        # 2. Status inspection
        res_status = await client.get("/lb/status")
        assert res_status.status == 200
        status_data = await res_status.json()
        assert status_data["algorithm"] == "round_robin"
        assert status_data["pool"]["total_backends"] == 1
        assert status_data["pool"]["healthy_backends"] == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_round_robin_distribution(
    mock_upstream_a: TestServer,
    mock_upstream_b: TestServer,
) -> None:
    """Verify Round Robin alternates traffic across backend A and backend B."""
    settings = LBSettings(
        backends=[
            BackendConfig(url=f"http://127.0.0.1:{mock_upstream_a.port}", name="upstream-a"),
            BackendConfig(url=f"http://127.0.0.1:{mock_upstream_b.port}", name="upstream-b"),
        ],
        algorithm=LBAlgorithm.ROUND_ROBIN,
    )
    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        # Request 1 -> Backend A
        r1 = await client.get("/ping")
        assert r1.status == 200
        assert (await r1.json())["server"] == "backend_a"

        # Request 2 -> Backend B
        r2 = await client.get("/ping")
        assert r2.status == 200
        assert (await r2.json())["server"] == "backend_b"

        # Request 3 -> Backend A (loop)
        r3 = await client.get("/ping")
        assert r3.status == 200
        assert (await r3.json())["server"] == "backend_a"

        # Request 4 -> Backend B (loop)
        r4 = await client.get("/ping")
        assert r4.status == 200
        assert (await r4.json())["server"] == "backend_b"

        # Check telemetry stats on pool
        stats_res = await client.get("/lb/status")
        stats = (await stats_res.json())["pool"]
        assert stats["total_requests"] == 4
        assert stats["total_success"] == 4
        assert stats["total_in_flight"] == 0  # All released cleanly
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_headers_and_body_forwarding(mock_upstream_a: TestServer) -> None:
    """Verify proxy forwards JSON payload, adds X-Forwarded-*, and strips hop-by-hop headers."""
    settings = LBSettings(
        backends=[BackendConfig(url=f"http://127.0.0.1:{mock_upstream_a.port}")],
    )
    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        custom_payload = {"action": "scale_up", "instances": 3}
        resp = await client.post(
            "/echo",
            json=custom_payload,
            headers={
                "X-Custom-Client": "Agent-007",
                "Connection": "close",
                "Upgrade": "websocket",
            },
        )
        assert resp.status == 200
        data = await resp.json()

        # Body forwarded correctly
        assert data["received_body"] == custom_payload

        # Hop-by-hop stripped
        rcv_headers = data["received_headers"]
        assert "upgrade" not in [k.lower() for k in rcv_headers]

        # Standard proxy headers injected
        assert "x-forwarded-for" in [k.lower() for k in rcv_headers]
        assert "x-forwarded-proto" in [k.lower() for k in rcv_headers]
        assert "x-forwarded-host" in [k.lower() for k in rcv_headers]
        assert rcv_headers.get("X-Custom-Client") == "Agent-007"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_empty_pool_returns_503() -> None:
    """Verify proxy returns 503 Service Unavailable when no healthy backends exist."""
    settings = LBSettings(backends=[])
    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        resp = await client.get("/any/route")
        assert resp.status == 503
        data = await resp.json()
        assert data["error"] == "Service Unavailable"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_unreachable_backend_returns_502() -> None:
    """Verify proxy returns 502 Bad Gateway when upstream server refuses connection."""
    # Port 59999 is unbound on localhost
    settings = LBSettings(backends=[BackendConfig(url="http://127.0.0.1:59999")])
    app = create_app(settings=settings)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        resp = await client.get("/ping")
        assert resp.status == 502
        data = await resp.json()
        assert data["error"] == "Bad Gateway"

        # Error count should be recorded in pool stats
        stats_res = await client.get("/lb/status")
        stats = (await stats_res.json())["pool"]
        assert stats["total_errors"] == 1
        assert stats["total_in_flight"] == 0  # In-flight must still be 0!
    finally:
        await client.close()
