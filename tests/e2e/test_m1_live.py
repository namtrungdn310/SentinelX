"""Opt-in M1 acceptance against an isolated live Controller + PostgreSQL.

Run with deploy/m1/compose.acceptance.yaml. Creates test nodes in the target DB.
The ordinary test suite skips this test unless SENTINELX_M1_CONTROLLER_URL is set.
"""

import asyncio
import os
import socket
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiohttp
import pytest

from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_common.contracts.telemetry import MetricSample

CONTROLLER_URL = os.getenv("SENTINELX_M1_CONTROLLER_URL", "")
pytestmark = pytest.mark.skipif(not CONTROLLER_URL, reason="Requires isolated M1 live lab")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_disk", [False, True])
async def test_real_agent_to_postgres_rest_and_websocket(
    tmp_path: Path, missing_disk: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real daemon enrolls, batches OS samples, broadcasts and persists nullable data."""
    base = CONTROLLER_URL.rstrip("/")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:

        async def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
            async with session.post(f"{base}{path}", json=payload) as response:
                response.raise_for_status()
                result: dict[str, Any] = await response.json()
                return result

        name = f"m1-acceptance-{uuid4().hex[:8]}"
        project = await post("/api/v1/projects", {"name": name})
        node = await post(
            "/api/v1/nodes",
            {
                "project_id": project["project_id"],
                "hostname": name,
                "ip_address": socket.gethostbyname(socket.gethostname()),
            },
        )
        node_id = node["node_id"]
        token = await post(f"/api/v1/nodes/{node_id}/enrollment-tokens", {})
        settings = AgentSettings(
            controller_url=base,
            node_id=node_id,
            enrollment_token=token["enrollment_token"],
            hostname=name,
            identity_path=tmp_path / "identity.json",
            telemetry_interval_seconds=0.2,
            telemetry_batch_size=2,
            telemetry_collector_type="real",
            telemetry_disk_path="/sentinelx-m1-missing-mount" if missing_disk else "/",
        )
        if missing_disk:
            # Disk failure is real; network absence is injected to exercise SQL NULL.
            monkeypatch.setattr("psutil.net_io_counters", lambda: None)
        daemon = AgentDaemon(settings)
        stop = asyncio.Event()
        async with session.ws_connect(f"{base}/api/v1/ws") as ws:
            task = asyncio.create_task(daemon.run(stop))
            try:
                async with asyncio.timeout(20):
                    while True:
                        message = await ws.receive_json()
                        if (
                            message["event"] == "metric_update"
                            and message["data"]["node_id"] == node_id
                        ):
                            break
                pushed = [MetricSample.model_validate(s) for s in message["data"]["samples"]]
                assert len(pushed) == 2  # Batched real samples, not fake or one POST per sample.
                assert settings.identity_path.is_file()
                assert pushed[0].observed_at < pushed[1].observed_at
                for sample in pushed:
                    assert 0 <= sample.cpu_percent <= 100
                    assert 0 <= sample.memory_percent <= 100
                    if missing_disk:
                        assert sample.disk_percent is None
                    else:
                        assert sample.disk_percent is not None
                        assert 0 <= sample.disk_percent <= 100
                    if missing_disk:
                        assert sample.network_rx_bytes is None
                        assert sample.network_tx_bytes is None
                    else:
                        assert sample.network_rx_bytes is not None and sample.network_rx_bytes >= 0
                        assert sample.network_tx_bytes is not None and sample.network_tx_bytes >= 0
                # A WebSocket broadcast may precede the POST response/commit.
                persisted: list[MetricSample] = []
                async with asyncio.timeout(10):
                    while len(persisted) < len(pushed):
                        async with session.get(
                            f"{base}/api/v1/telemetry/nodes/{node_id}/metrics"
                        ) as response:
                            response.raise_for_status()
                            data = await response.json()
                        persisted = [MetricSample.model_validate(s) for s in data["samples"]]
                        if len(persisted) < len(pushed):
                            await asyncio.sleep(0.05)
                for sample in pushed:
                    assert sample in persisted
                async with session.get(f"{base}/api/v1/nodes/{node_id}") as response:
                    response.raise_for_status()
                    assert (await response.json())["last_seen"] is not None
            finally:
                stop.set()
                await asyncio.wait_for(task, timeout=5)
