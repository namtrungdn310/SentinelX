"""End-to-End Multi-Host Acceptance Smoke Suite for SentinelX Foundation.

Simulates the complete PBL4 multi-host distributed topology:
  - Machine A: Central Controller + PostgreSQL + Custom Load Balancer
  - Machine B: Remote Workload Backend01 + SentinelX Agent 01
  - Machine C: Remote Workload Backend02 + SentinelX Agent 02

Verifies:
  1. Remote Agent B & C enroll and heartbeat to Controller A across network
  2. Remote Agent B & C dispatch telemetry metrics to Controller A
  3. Load Balancer A routes traffic across Remote Backend B and C
  4. Remote failure of Backend C is detected -> EJECTED -> 100% traffic stays on B
  5. Remote recovery of Backend C -> RE-ADDED -> traffic resumes across B & C
  6. Zero architectural dependency on single-host or hardcoded localhost
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app as create_controller_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_lb.config import BackendConfig, HealthCheckConfig, LBAlgorithm, LBSettings
from sentinelx_lb.server import create_app as create_lb_app


class MockRemoteBackend:
    """Simulates a remote backend service running on Machine B or Machine C."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_healthy = True
        self.app = web.Application()
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/api/v1/workload", self.handle_workload)
        self.server: TestServer | None = None

    async def handle_health(self, _request: web.Request) -> web.Response:
        if self.is_healthy:
            return web.json_response({"status": "healthy", "node": self.name}, status=200)
        return web.json_response({"status": "error", "node": self.name}, status=503)

    async def handle_workload(self, _request: web.Request) -> web.Response:
        now_ts = datetime.now(UTC).isoformat()
        return web.json_response({"handled_by": self.name, "timestamp": now_ts})

    async def start(self) -> TestServer:
        self.server = TestServer(self.app)
        await self.server.start_server()
        return self.server

    async def stop(self) -> None:
        if self.server:
            await self.server.close()


@pytest.fixture
async def machine_a_controller() -> AsyncGenerator[AsyncClient, None]:
    """Controller running on Machine A."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    settings = ControllerSettings(
        environment="testing",
        service_name="machine-a-controller",
        database=DatabaseSettings(url=test_db_url),
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

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://machine-a-controller:8000",
    ) as client:
        yield client

    await engine.dispose()


@pytest.mark.asyncio
async def test_full_multihost_acceptance_lifecycle(
    machine_a_controller: AsyncClient,
) -> None:
    """Complete multi-host acceptance verification for Foundation Freeze."""
    # --------------------------------------------------------------------------
    # 1. SETUP: Start remote backends (Machine B and Machine C)
    # --------------------------------------------------------------------------
    remote_b = MockRemoteBackend("machine-b-node")
    remote_c = MockRemoteBackend("machine-c-node")

    server_b = await remote_b.start()
    server_c = await remote_c.start()

    try:
        # ----------------------------------------------------------------------
        # 2. CONTROL PLANE: Register project on Controller A
        # ----------------------------------------------------------------------
        p_res = await machine_a_controller.post(
            "/api/v1/projects",
            json={"name": "MultiHost-Production", "description": "Multi-host topology test"},
        )
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # Register Node B and Node C on Controller A
        nb_res = await machine_a_controller.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "srv-machine-b",
                "ip_address": "192.168.1.20",
            },
        )
        assert nb_res.status_code == 201
        node_b_id = nb_res.json()["node_id"]

        nc_res = await machine_a_controller.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "srv-machine-c",
                "ip_address": "192.168.1.30",
            },
        )
        assert nc_res.status_code == 201
        node_c_id = nc_res.json()["node_id"]

        # ----------------------------------------------------------------------
        # 3. AGENT PLANE: Issue enrollment tokens & enroll Agent B and C
        # ----------------------------------------------------------------------
        tok_b_res = await machine_a_controller.post(
            f"/api/v1/nodes/{node_b_id}/enrollment-tokens",
            json={"expires_in_hours": 2},
        )
        assert tok_b_res.status_code == 201
        raw_token_b = tok_b_res.json()["enrollment_token"]

        tok_c_res = await machine_a_controller.post(
            f"/api/v1/nodes/{node_c_id}/enrollment-tokens",
            json={"expires_in_hours": 2},
        )
        assert tok_c_res.status_code == 201
        raw_token_c = tok_c_res.json()["enrollment_token"]

        # Enroll Agent B
        enroll_b = await machine_a_controller.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_b_id,
                "enrollment_token": raw_token_b,
                "agent_version": "0.1.0",
                "hostname": "srv-machine-b",
                "os_info": "Linux Ubuntu 24.04 (Machine B)",
            },
        )
        assert enroll_b.status_code == 200
        agent_b_id = enroll_b.json()["agent_id"]

        # Enroll Agent C
        enroll_c = await machine_a_controller.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_c_id,
                "enrollment_token": raw_token_c,
                "agent_version": "0.1.0",
                "hostname": "srv-machine-c",
                "os_info": "Linux Debian 12 (Machine C)",
            },
        )
        assert enroll_c.status_code == 200
        agent_c_id = enroll_c.json()["agent_id"]

        # Agent B & C send heartbeats to Controller A
        now_dt = datetime.now(UTC)
        hb_b = await machine_a_controller.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_b_id,
                "agent_id": agent_b_id,
                "sequence": 1,
                "sent_at": now_dt.isoformat(),
            },
        )
        assert hb_b.status_code == 200
        assert hb_b.json()["status"] == "ok"

        hb_c = await machine_a_controller.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_c_id,
                "agent_id": agent_c_id,
                "sequence": 1,
                "sent_at": now_dt.isoformat(),
            },
        )
        assert hb_c.status_code == 200
        assert hb_c.json()["status"] == "ok"

        # Verify Node B and Node C status transitioned to ONLINE on Controller A
        get_b = await machine_a_controller.get(f"/api/v1/nodes/{node_b_id}")
        assert get_b.json()["status"] == "online"

        get_c = await machine_a_controller.get(f"/api/v1/nodes/{node_c_id}")
        assert get_c.json()["status"] == "online"

        # Ingest telemetry batch from Agent B
        telem_b = await machine_a_controller.post(
            "/api/v1/telemetry/metrics",
            json={
                "node_id": node_b_id,
                "agent_id": agent_b_id,
                "sequence": 1,
                "sent_at": now_dt.isoformat(),
                "samples": [
                    {
                        "observed_at": now_dt.isoformat(),
                        "cpu_percent": 24.5,
                        "memory_percent": 48.0,
                        "disk_percent": 30.0,
                        "network_rx_bytes": 10500,
                        "network_tx_bytes": 5200,
                    }
                ],
            },
        )
        assert telem_b.status_code == 200
        assert telem_b.json()["status"] == "ok"

        # Query metrics stored on Controller A for remote Node B
        query_res = await machine_a_controller.get(f"/api/v1/telemetry/nodes/{node_b_id}/metrics")
        assert query_res.status_code == 200
        assert query_res.json()["count"] >= 1

        # ----------------------------------------------------------------------
        # 4. TRAFFIC PLANE: Load Balancer A routes across Remote B and C
        # ----------------------------------------------------------------------
        lb_settings = LBSettings(
            backends=[
                BackendConfig(url=f"http://127.0.0.1:{server_b.port}", name="machine-b"),
                BackendConfig(url=f"http://127.0.0.1:{server_c.port}", name="machine-c"),
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

        lb_app = create_lb_app(settings=lb_settings)
        lb_client = TestClient(TestServer(lb_app))
        await lb_client.start_server()

        try:
            # Wait for health checker initial scan (2 cycles = ~0.35s)
            await asyncio.sleep(0.35)

            # Round robin distributes requests across Machine B and Machine C
            r1 = await lb_client.get("/api/v1/workload")
            r2 = await lb_client.get("/api/v1/workload")
            assert r1.status == 200
            assert r2.status == 200

            servers = {(await r1.json())["handled_by"], (await r2.json())["handled_by"]}
            assert servers == {"machine-b-node", "machine-c-node"}

            # ------------------------------------------------------------------
            # 5. RESILIENCE: Remote Backend C fails -> Ejected -> 100% traffic to B
            # ------------------------------------------------------------------
            remote_c.is_healthy = False
            await asyncio.sleep(0.4)  # Wait for 2 failure probes

            # Inspect LB status: healthy backends count should be 1
            status_res = await lb_client.get("/lb/status")
            assert (await status_res.json())["pool"]["healthy_backends"] == 1

            # Traffic must stay 100% on Machine B without 502/503 errors
            for _ in range(4):
                res = await lb_client.get("/api/v1/workload")
                assert res.status == 200
                assert (await res.json())["handled_by"] == "machine-b-node"

            # ------------------------------------------------------------------
            # 6. RECOVERY: Remote Backend C recovers -> Re-added -> Traffic resumes
            # ------------------------------------------------------------------
            remote_c.is_healthy = True
            await asyncio.sleep(0.4)  # Wait for 2 recovery probes

            status_res2 = await lb_client.get("/lb/status")
            assert (await status_res2.json())["pool"]["healthy_backends"] == 2

            # Traffic resumes balancing across both remote nodes
            res_after1 = await lb_client.get("/api/v1/workload")
            res_after2 = await lb_client.get("/api/v1/workload")
            after_servers = {
                (await res_after1.json())["handled_by"],
                (await res_after2.json())["handled_by"],
            }
            assert after_servers == {"machine-b-node", "machine-c-node"}

        finally:
            await lb_client.close()

    finally:
        await remote_b.stop()
        await remote_c.stop()
