"""M1 -> M3 -> M5 -> M6: alert-only never claims a system change."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_agent.identity import AgentIdentity
from sentinelx_common.contracts.defense import AgentCommandContract
from tests.core_helpers import core_harness


@pytest.mark.asyncio
async def test_m6_end_to_end_defense_pipeline(tmp_path: Path) -> None:
    async with core_harness() as h:
        await h.post(
            f"/projects/{h.project}/defense-policies",
            {
                "name": "CPU alert",
                "event_type": "cpu_threshold_detector",
                "action_type": "ALERT_ONLY",
            },
        )
        now = datetime.now(UTC)
        await h.post(
            "/telemetry/metrics",
            {
                "node_id": h.node,
                "agent_id": h.agent,
                "sequence": 1,
                "sent_at": now.isoformat(),
                "samples": [
                    {
                        "observed_at": (now - timedelta(seconds=10 - i * 5)).isoformat(),
                        "cpu_percent": 98,
                        "memory_percent": 40,
                        "disk_percent": 20,
                    }
                    for i in range(3)
                ],
            },
        )
        actions = (await h.client.get("/api/v1/defense/actions")).json()["items"]
        assert len(actions) == 1
        command = (await h.heartbeat())[0]
        processor = CommandProcessor(
            AgentSettings(
                controller_url="http://192.0.2.20",
                node_id=h.node,
                command_journal_path=tmp_path / "commands.sqlite3",
            )
        )
        processor.set_identity(AgentIdentity(node_id=h.node, agent_id=h.agent, enrolled_at=now))
        client = AsyncMock(spec=ControllerClient)
        await processor.process_command(AgentCommandContract.model_validate(command), client)
        receipt = client.ack_defense_action.call_args.args[1]
        assert receipt.status == "SKIPPED"
        response = await h.client.post(
            f"/api/v1/defense/actions/{command['id']}/ack", json=receipt.model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        incident = (await h.client.get("/api/v1/incidents")).json()["items"][0]
        assert incident["status"] == "DETECTED"
        assert (await h.client.get(f"/api/v1/defense/actions/{command['id']}")).json()[
            "status"
        ] == "SKIPPED"


@pytest.mark.asyncio
async def test_m6_end_to_end_service_restart_pipeline(tmp_path: Path) -> None:
    async with core_harness() as h:
        await h.post(
            f"/projects/{h.project}/defense-policies",
            {
                "name": "Auto restart worker on CPU",
                "event_type": "cpu_threshold_detector",
                "action_type": "RESTART_SERVICE",
                "target_params": {"service_name": "order-worker"},
                "is_auto_execute": True,
            },
        )
        now = datetime.now(UTC)
        await h.post(
            "/telemetry/metrics",
            {
                "node_id": h.node,
                "agent_id": h.agent,
                "sequence": 1,
                "sent_at": now.isoformat(),
                "samples": [
                    {
                        "observed_at": (now - timedelta(seconds=10 - i * 5)).isoformat(),
                        "cpu_percent": 98,
                        "memory_percent": 40,
                        "disk_percent": 20,
                        "top_process_name": "order-worker",
                        "top_process_pid": 4128,
                    }
                    for i in range(3)
                ],
            },
        )
        actions = (await h.client.get("/api/v1/defense/actions")).json()["items"]
        assert len(actions) == 1
        assert actions[0]["action_type"] == "RESTART_SERVICE"
        assert actions[0]["command_payload"]["service_name"] == "order-worker"

        command = (await h.heartbeat())[0]
        processor = CommandProcessor(
            AgentSettings(
                controller_url="http://192.0.2.20",
                node_id=h.node,
                command_journal_path=tmp_path / "commands.sqlite3",
            )
        )
        processor.set_identity(AgentIdentity(node_id=h.node, agent_id=h.agent, enrolled_at=now))
        client = AsyncMock(spec=ControllerClient)
        await processor.process_command(AgentCommandContract.model_validate(command), client)
        receipt = client.ack_defense_action.call_args.args[1]
        assert receipt.status in ("APPLIED", "SIMULATED")

        response = await h.client.post(
            f"/api/v1/defense/actions/{command['id']}/ack", json=receipt.model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        assert (await h.client.get(f"/api/v1/defense/actions/{command['id']}")).json()[
            "status"
        ] in ("APPLIED", "SIMULATED")
