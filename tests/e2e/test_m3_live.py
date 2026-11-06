"""Opt-in M3 regressions against the same isolated PostgreSQL lab used by M2."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import aiohttp
import pytest

BASE = os.getenv(
    "SENTINELX_M3_CONTROLLER_URL", os.getenv("SENTINELX_M2_CONTROLLER_URL", "")
).rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="Requires isolated M1/M2/M3 PostgreSQL lab")


@pytest.mark.asyncio
async def test_m3_concurrent_retry_persistence_and_postcommit_websocket() -> None:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:

        async def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
            async with session.post(BASE + path, json=payload) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
                return data

        async def events(node: str, limit: int = 50) -> dict[str, Any]:
            async with session.get(
                BASE + f"/api/v1/detection-events?node_id={node}&limit={limit}"
            ) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
                return data

        async def register() -> tuple[str, str]:
            name = "m3-qa-" + uuid4().hex[:8]
            project = await post("/api/v1/projects", {"name": name})
            node = (
                await post(
                    "/api/v1/nodes",
                    {
                        "project_id": project["project_id"],
                        "hostname": name,
                        "ip_address": "192.0.2.1",
                    },
                )
            )["node_id"]
            token = await post(f"/api/v1/nodes/{node}/enrollment-tokens", {})
            identity = await post(
                "/api/v1/nodes/enroll",
                {
                    "node_id": node,
                    "enrollment_token": token["enrollment_token"],
                    "agent_version": "qa",
                    "hostname": name,
                },
            )
            return node, identity["agent_id"]

        def batch(
            node: str, agent: str, values: list[float], start: datetime, disk: float = 20
        ) -> dict[str, Any]:
            return {
                "node_id": node,
                "agent_id": agent,
                "sequence": 1,
                "sent_at": datetime.now(UTC).isoformat(),
                "samples": [
                    {
                        "observed_at": (start + timedelta(seconds=5 * i)).isoformat(),
                        "cpu_percent": value,
                        "memory_percent": 40,
                        "disk_percent": disk,
                    }
                    for i, value in enumerate(values)
                ],
            }

        node, agent = await register()
        start = datetime.now(UTC) - timedelta(seconds=20)
        sample = batch(node, agent, [98], start)
        # Separate simultaneous PostgreSQL transactions must observe only one unique sample.
        await asyncio.gather(*[post("/api/v1/telemetry/metrics", sample) for _ in range(3)])
        assert (await events(node))["total"] == 0
        async with session.ws_connect(BASE + "/api/v1/ws") as ws:
            request = batch(node, agent, [98, 98], start + timedelta(seconds=5))
            await post("/api/v1/telemetry/metrics", request)
            # No compensating polling: HTTP success guarantees durable metric/event/state.
            durable = await events(node)
            assert durable["total"] == 1
            async with asyncio.timeout(10):
                while True:
                    message = await ws.receive_json()
                    if message["event"] == "detection_alert" and message["data"]["node_id"] == node:
                        break
            assert message["data"]["id"] == durable["items"][0]["id"]
            assert message["data"]["severity"] == "CRITICAL"
            await asyncio.gather(*[post("/api/v1/telemetry/metrics", request) for _ in range(3)])
            assert (await events(node))["total"] == 1

        node2, agent2 = await register()
        overload = batch(node2, agent2, [98, 98, 98, 20, 20], start, disk=99)
        await post("/api/v1/telemetry/metrics", overload)
        result = await events(node2)
        assert result["total"] == 2  # CPU prefix and disk, both inside the same five-sample batch.
        assert (await events(node2, 1))["total"] == 2
        await post("/api/v1/telemetry/metrics", overload)
        assert (await events(node2))["total"] == 2
