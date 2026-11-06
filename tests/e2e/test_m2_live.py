"""Opt-in: real non-root libpcap Agent -> Controller/PostgreSQL -> REST/WS.

Only ephemeral loopback UDP traffic inside the dedicated M2 lab is generated.
"""

import asyncio
import os
import socket
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiohttp
import pytest

from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon

BASE = os.getenv("SENTINELX_M2_CONTROLLER_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="Requires isolated M2 libpcap/PostgreSQL lab")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_interface", [False, True])
async def test_m2_live_capture_and_failure_isolation(tmp_path: Path, bad_interface: bool) -> None:
    if sys.platform == "linux":
        assert os.getuid() != 0
    else:
        pytest.skip("Live libpcap capture requires Linux")
    capabilities = Path("/proc/self/status").read_text()
    for key in ("CapEff", "CapBnd", "CapAmb"):
        value = next(line.split()[1] for line in capabilities.splitlines() if line.startswith(key))
        assert int(value, 16) == 1 << 13  # ONLY CAP_NET_RAW; no NET_ADMIN/root/SET* left.
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:

        async def post(path: str, data: dict[str, Any]) -> dict[str, Any]:
            async with session.post(BASE + path, json=data) as response:
                response.raise_for_status()
                result: dict[str, Any] = await response.json()
                return result

        name = "m2-" + uuid4().hex[:8]
        project = await post("/api/v1/projects", {"name": name})
        node = await post(
            "/api/v1/nodes",
            {"project_id": project["project_id"], "hostname": name, "ip_address": "127.0.0.1"},
        )
        token = await post(f"/api/v1/nodes/{node['node_id']}/enrollment-tokens", {})
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        port = receiver.getsockname()[1]
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        settings = AgentSettings(
            controller_url=BASE,
            node_id=node["node_id"],
            enrollment_token=token["enrollment_token"],
            identity_path=tmp_path / "identity.json",
            telemetry_interval_seconds=0.2,
            telemetry_batch_size=2,
            network_capture_enabled=True,
            network_interface="sentinelx-missing" if bad_interface else "lo",
            network_bpf_filter=f"udp and dst port {port}",
            network_window_seconds=2,
            network_step_seconds=1,
        )
        daemon, stop = AgentDaemon(settings), asyncio.Event()

        async def traffic() -> None:
            while not stop.is_set():
                sender.sendto(b"m2-private-payload-never-persist", ("127.0.0.1", port))
                await asyncio.sleep(0.1)

        async with session.ws_connect(BASE + "/api/v1/ws") as ws:
            task = asyncio.create_task(daemon.run(stop))
            generator = asyncio.create_task(traffic())
            try:
                received: dict[str, Any] = {}
                async with asyncio.timeout(25):
                    while True:
                        message = await ws.receive_json()
                        assert "m2-private-payload" not in str(message)
                        if message["data"].get("node_id") != node["node_id"]:
                            continue
                        if bad_interface and message["event"] == "metric_update":
                            break
                        if message["event"] == "network_feature_update" and any(
                            w["features"] for w in message["data"]["windows"]
                        ):
                            received = message
                            break
                endpoint = f"/api/v1/telemetry/nodes/{node['node_id']}/network-features"
                if bad_interface:
                    async with session.get(BASE + endpoint) as response:
                        assert (await response.json())["count"] == 0  # unavailable != healthy empty
                    return
                window = next(w for w in received["data"]["windows"] if w["features"])
                feature = window["features"][0]
                assert feature["protocol"] == "udp" and feature["packet_count"] > 0
                assert feature["destination_ports"] == [port]
                assert feature["source_ip"] == feature["destination_ip"] == "127.0.0.1"
                assert feature["byte_count"] > 0 and daemon.identity is not None
                # A repeat blocks on the initial insert's commit if WS preceded HTTP success.
                retry = await post(
                    "/api/v1/telemetry/network-features",
                    {
                        "node_id": node["node_id"],
                        "agent_id": daemon.identity.agent_id,
                        "sequence": 1,
                        "sent_at": window["window_end"],
                        "windows": [window],
                    },
                )
                assert retry["processed_count"] == 0
                async with session.get(BASE + endpoint) as response:
                    persisted = await response.json()
                stored = next(
                    w for w in persisted["windows"] if w["window_id"] == window["window_id"]
                )
                assert stored == window
                assert "m2-private-payload" not in str(persisted)
            finally:
                stop.set()
                await generator
                sender.close()
                receiver.close()
                await asyncio.wait_for(task, timeout=10)
