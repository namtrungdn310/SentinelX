"""Idempotent enrollment for the explicitly opted-in local container lab only."""

import asyncio
import os
import sys
from typing import Any

import aiohttp

from sentinelx_agent.config import AgentSettings
from sentinelx_agent.identity import AgentIdentityManager


async def bootstrap(settings: AgentSettings) -> None:
    identity = AgentIdentityManager.load(settings.identity_path)
    if identity:
        os.environ["SENTINELX_NODE_ID"] = identity.node_id
        return
    if os.environ.get("SENTINELX_LAB_BOOTSTRAP") != "1":
        raise RuntimeError("Lab bootstrap must be explicitly enabled")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:

        async def call(method: str, path: str, data: dict[str, Any] | None = None) -> Any:
            async with client.request(
                method, settings.controller_url + "/api/v1" + path, json=data
            ) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Lab bootstrap {path} failed: HTTP {response.status}")
                return await response.json()

        name = os.environ.get("SENTINELX_LAB_PROJECT", "SentinelX Docker Lab")
        projects = await call("GET", "/projects")
        project = next((item for item in projects if item["name"] == name), None)
        if project is None:
            project = await call("POST", "/projects", {"name": name})
        project_id = project["project_id"]
        ip = os.environ["SENTINELX_LAB_NODE_IP"]
        nodes = await call("GET", "/nodes?project_id=" + project_id)
        node = next((item for item in nodes if item["ip_address"] == ip), None)
        if node is None:
            node = await call(
                "POST",
                "/nodes",
                {"project_id": project_id, "hostname": settings.hostname, "ip_address": ip},
            )
        token = await call("POST", f"/nodes/{node['node_id']}/enrollment-tokens", {})
        os.environ["SENTINELX_NODE_ID"] = node["node_id"]
        os.environ["SENTINELX_ENROLLMENT_TOKEN"] = token["enrollment_token"]


if __name__ == "__main__":
    asyncio.run(bootstrap(AgentSettings.load()))
    os.execv(sys.executable, [sys.executable, "-m", "sentinelx_agent.main"])
