"""Idempotent enrollment for the explicitly opted-in local container lab only."""

import asyncio
import logging
import os
import sys
from typing import Any

import aiohttp

from sentinelx_agent.config import AgentSettings
from sentinelx_agent.identity import AgentIdentityManager

logger = logging.getLogger("sentinelx_agent.lab_bootstrap")


async def _request_json(
    client: aiohttp.ClientSession,
    settings: AgentSettings,
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
    *,
    allow_statuses: set[int] | None = None,
) -> tuple[int, Any]:
    last_error: Exception | None = None
    url = settings.controller_url + "/api/v1" + path
    for attempt in range(1, 16):
        try:
            async with client.request(method, url, json=data) as response:
                if allow_statuses and response.status in allow_statuses:
                    return response.status, await response.json(content_type=None)
                if response.status >= 500:
                    raise RuntimeError(f"HTTP {response.status}")
                if response.status >= 300:
                    detail = (await response.text())[:200]
                    raise RuntimeError(f"Lab bootstrap {path} failed: HTTP {response.status}: {detail}")
                return response.status, await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, RuntimeError) as err:
            last_error = err
            if "failed: HTTP 4" in str(err):
                raise
            if attempt < 15:
                await asyncio.sleep(min(2.0, 0.5 * attempt))
    raise RuntimeError(f"Lab bootstrap {path} unreachable: {last_error}")


async def bootstrap(settings: AgentSettings) -> None:
    if os.environ.get("SENTINELX_LAB_BOOTSTRAP") != "1":
        identity = AgentIdentityManager.load(settings.identity_path)
        if identity:
            os.environ["SENTINELX_NODE_ID"] = identity.node_id
            return
        raise RuntimeError("Lab bootstrap must be explicitly enabled")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
        existing_identity = AgentIdentityManager.load(settings.identity_path)
        if existing_identity:
            status, node_data = await _request_json(
                client,
                settings,
                "GET",
                f"/nodes/{existing_identity.node_id}",
                allow_statuses={404},
            )
            if status == 200 and isinstance(node_data, dict):
                os.environ["SENTINELX_NODE_ID"] = existing_identity.node_id
                return
            logger.warning(
                "Saved lab identity %s no longer exists on Controller; re-enrolling cleanly",
                existing_identity.node_id,
            )
            settings.identity_path.unlink(missing_ok=True)
            journal_path = settings.command_journal_path or settings.identity_path.with_name(
                "commands.sqlite3"
            )
            journal_path.unlink(missing_ok=True)

        name = os.environ.get("SENTINELX_LAB_PROJECT", "SentinelX Docker Lab")
        _, projects = await _request_json(client, settings, "GET", "/projects")
        project = next((item for item in projects if item["name"] == name), None)
        if project is None:
            status, created_or_err = await _request_json(
                client,
                settings,
                "POST",
                "/projects",
                {"name": name, "description": "Docker Compose multi-node lab environment"},
                allow_statuses={409},
            )
            if status == 409:
                _, projects = await _request_json(client, settings, "GET", "/projects")
                project = next((item for item in projects if item["name"] == name), None)
            else:
                project = created_or_err
        if project is None:
            raise RuntimeError(f"Could not find or create lab project '{name}'")

        project_id = project["project_id"]
        await _request_json(
            client,
            settings,
            "POST",
            f"/projects/{project_id}/defense-policies/seed-defaults",
        )

        ip = os.environ["SENTINELX_LAB_NODE_IP"]
        lb_role = os.environ.get("SENTINELX_LAB_LB_ROLE", "standalone")
        lb_port = int(os.environ.get("SENTINELX_LAB_LB_PORT", "8080"))
        lb_health_path = os.environ.get("SENTINELX_LAB_LB_HEALTH_PATH") or None

        _, nodes = await _request_json(client, settings, "GET", "/nodes?project_id=" + project_id)
        node = next((item for item in nodes if item["ip_address"] == ip), None)
        if node is None:
            status, node_or_err = await _request_json(
                client,
                settings,
                "POST",
                "/nodes",
                {
                    "project_id": project_id,
                    "hostname": settings.hostname,
                    "ip_address": ip,
                    "lb_role": lb_role,
                    "lb_backend_port": lb_port,
                    "lb_health_path": lb_health_path,
                },
                allow_statuses={409},
            )
            if status == 409:
                _, nodes = await _request_json(
                    client, settings, "GET", "/nodes?project_id=" + project_id
                )
                node = next((item for item in nodes if item["ip_address"] == ip), None)
            else:
                node = node_or_err
        if node is None:
            raise RuntimeError(f"Could not find or register lab node '{ip}'")

        if os.environ.get("SENTINELX_LAB_ENABLE_PROJECT_LB") == "1":
            lb_cfg = project.get("load_balancer") or {}
            if not lb_cfg.get("enabled"):
                await _request_json(
                    client,
                    settings,
                    "PUT",
                    f"/projects/{project_id}/load-balancer",
                    {
                        "enabled": True,
                        "algorithm": lb_cfg.get("algorithm", "round_robin"),
                        "health_path": lb_cfg.get("health_path", "/health"),
                        "health_interval_seconds": lb_cfg.get("health_interval_seconds", 3.0),
                        "failure_threshold": lb_cfg.get("failure_threshold", 3),
                        "success_threshold": lb_cfg.get("success_threshold", 2),
                    },
                )
            else:
                await _request_json(client, settings, "POST", f"/projects/{project_id}/load-balancer/sync")

        _, token = await _request_json(
            client, settings, "POST", f"/nodes/{node['node_id']}/enrollment-tokens", {}
        )
        os.environ["SENTINELX_NODE_ID"] = node["node_id"]
        os.environ["SENTINELX_ENROLLMENT_TOKEN"] = token["enrollment_token"]


if __name__ == "__main__":
    asyncio.run(bootstrap(AgentSettings.load()))
    os.execv(sys.executable, [sys.executable, "-m", "sentinelx_agent.main"])
