"""Recovery ownership and real-state contract tests."""

import pytest

from tests.core_helpers import core_harness


@pytest.mark.asyncio
async def test_manual_recovery_revert_flow() -> None:
    async with core_harness() as h:
        action = await h.block()
        pending = await h.client.post(f"/api/v1/recovery/actions/{action['id']}/revert")
        assert pending.status_code == 409
        command = (await h.heartbeat())[0]
        assert (await h.ack(command)).status_code == 200
        recovery = await h.client.post(f"/api/v1/recovery/actions/{action['id']}/revert")
        assert recovery.status_code == 201, recovery.text
        again = await h.client.post(f"/api/v1/recovery/actions/{action['id']}/revert")
        assert again.json()["id"] == recovery.json()["id"]
        unblock = (await h.heartbeat())[0]
        assert unblock["command_payload"]["original_defense_action_id"] == action["id"]
        assert (await h.ack(unblock)).status_code == 200
        saved = (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()
        assert saved["status"] == "REVERTED"
        result = await h.client.get(f"/api/v1/recovery/actions/{recovery.json()['id']}")
        assert result.json()["status"] == "SUCCESS"
        # Replaying the old block's receipt cannot resurrect a reverted action.
        assert (await h.ack(command)).status_code == 200
        assert (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()[
            "status"
        ] == "REVERTED"
        assert (await h.client.get("/api/v1/recovery/actions")).json()["total"] == 1


@pytest.mark.asyncio
async def test_scan_expired_actions_endpoint() -> None:
    async with core_harness() as h:
        assert (await h.client.post("/api/v1/recovery/scan-expired")).json() == []
        assert (
            await h.client.post("/api/v1/recovery/scan-expired?node_id=invalid")
        ).status_code == 422
