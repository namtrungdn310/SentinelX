"""Opt-in actual PostgreSQL/controller + nftables + separate-container traffic proof."""

import asyncio
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiohttp
import pytest
from aiohttp import web

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_agent.identity import AgentIdentity
from sentinelx_common.contracts.defense import AgentCommandContract

URL = os.getenv("SENTINELX_CORE_CONTROLLER_URL", "")
PEER = os.getenv("SENTINELX_CORE_PEER_URL", "")
pytestmark = pytest.mark.skipif(not URL or not PEER, reason="Requires isolated core firewall lab")


@pytest.mark.asyncio
async def test_real_block_receipt_restart_and_owned_recovery(tmp_path: Path) -> None:
    status = Path("/proc/self/status").read_text()
    assert next(line.split()[1] for line in status.splitlines() if line.startswith("Uid:")) != "0"
    caps = int(
        next(line.split()[1] for line in status.splitlines() if line.startswith("CapEff:")), 16
    )
    assert caps == (1 << 12) | (1 << 13)  # Only NET_ADMIN and NET_RAW.
    server = web.Application()

    async def ok(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    server.router.add_get("/", ok)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 9088).start()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:

            async def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
                async with session.post(URL + "/api/v1" + path, json=payload) as response:
                    body = await response.json()
                    assert response.status < 300, body
                    return dict(body)

            async def probe() -> bool:
                async with session.get(PEER + "/probe") as response:
                    return bool((await response.json())["reachable"])

            for _ in range(20):
                if await probe():
                    break
                await asyncio.sleep(0.1)
            assert await probe()
            project = await post("/projects", {"name": "core-" + uuid4().hex[:8]})
            node = await post(
                "/nodes",
                {
                    "project_id": project["project_id"],
                    "hostname": "core-kernel",
                    "ip_address": socket.gethostbyname(socket.gethostname()),
                },
            )
            token = await post(f"/nodes/{node['node_id']}/enrollment-tokens", {})
            enrollment = await post(
                "/nodes/enroll",
                {
                    "node_id": node["node_id"],
                    "enrollment_token": token["enrollment_token"],
                    "hostname": "core-kernel",
                    "agent_version": "core-qa",
                },
            )
            identity = AgentIdentity(
                node_id=node["node_id"],
                agent_id=enrollment["agent_id"],
                enrolled_at=datetime.now(UTC),
            )
            settings = AgentSettings(
                controller_url=URL,
                node_id=identity.node_id,
                identity_path=tmp_path / "identity.json",
                defense_executor_type="nftables",
                nftables_table_name="sentinelx_core_qa",
            )
            worker = CommandProcessor(settings)
            worker.set_identity(identity)
            block_payload = {
                "node_id": identity.node_id,
                "action_type": "BLOCK_IP_NFTABLES",
                "target_ip": socket.gethostbyname("peer"),
                "command_payload": {"duration_seconds": 60},
            }

            async def create_block() -> tuple[int, dict[str, Any]]:
                async with session.post(
                    URL + "/api/v1/defense/actions", json=block_payload
                ) as response:
                    return response.status, dict(await response.json())

            concurrent = await asyncio.gather(create_block(), create_block())
            assert sorted(code for code, _ in concurrent) == [201, 409]
            action = next(body for code, body in concurrent if code == 201)

            async def heartbeat() -> list[dict[str, Any]]:
                response = await post(
                    "/nodes/heartbeat",
                    {
                        "node_id": identity.node_id,
                        "agent_id": identity.agent_id,
                        "sequence": 1,
                        "sent_at": datetime.now(UTC).isoformat(),
                        "command_protocol_version": 2,
                        "executor_mode": "nftables",
                        "supported_actions": [
                            "BLOCK_IP_NFTABLES",
                            "UNBLOCK_IP_NFTABLES",
                            "ALERT_ONLY",
                        ],
                    },
                )
                return list(response["commands"])

            concurrent_heartbeats = await asyncio.gather(heartbeat(), heartbeat())
            delivered = [command for batch in concurrent_heartbeats for command in batch]
            assert len(delivered) == 1 and delivered[0]["id"] == action["id"]
            command = AgentCommandContract.model_validate(delivered[0])
            async with ControllerClient(URL) as client:
                receipt = await worker.process_command(command, client)
                assert receipt is not None and receipt.status == "ok", receipt
                async with session.get(URL + f"/api/v1/defense/actions/{action['id']}") as response:
                    assert (await response.json())["status"] == "APPLIED"
                assert not await probe()  # An actual request from a different namespace is dropped.
                restarted = CommandProcessor(settings)
                restarted.set_identity(identity)
                assert await restarted.process_command(command, client) is not None
                recovery = await post(f"/recovery/actions/{action['id']}/revert", {})
                assert recovery["status"] == "PENDING"
                children = await heartbeat()
                assert len(children) == 1 and children[0]["action_type"] == "UNBLOCK_IP_NFTABLES"
                ack = await restarted.process_command(
                    AgentCommandContract.model_validate(children[0]), client
                )
                assert ack is not None and ack.status == "ok"
                assert await probe()
                async with session.get(URL + f"/api/v1/defense/actions/{action['id']}") as response:
                    assert (await response.json())["status"] == "REVERTED"
    finally:
        await runner.cleanup()
