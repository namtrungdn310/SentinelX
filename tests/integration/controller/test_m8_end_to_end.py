"""M8 protocol integration; real kernel enforcement is covered by the opt-in Linux lab."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from sentinelx_controller.modules.defense.models import DefenseActionModel
from tests.core_helpers import core_harness


@pytest.mark.asyncio
async def test_m8_end_to_end_recovery_pipeline() -> None:
    async with core_harness() as h:
        action = await h.block(60, command_payload={"block_duration_seconds": 60})
        command = (await h.heartbeat())[0]
        assert command["command_payload"] == {"duration_seconds": 60}
        assert (await h.ack(command)).status_code == 200
        # Creation age is irrelevant: an acknowledged 60s block is still active.
        async with h.sessions() as db:
            row = await db.get(DefenseActionModel, UUID(action["id"]))
            assert row is not None
            row.created_at = datetime.now(UTC) - timedelta(hours=1)
            await db.commit()
        assert (await h.client.post("/api/v1/recovery/scan-expired")).json() == []
        # Advance only the execution-derived expiry, avoiding a timing-dependent sleep.
        async with h.sessions() as db:
            row = await db.get(DefenseActionModel, UUID(action["id"]))
            assert row is not None
            row.effective_until = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
        unblocks = await h.heartbeat()
        assert len(unblocks) == 1
        unblock = unblocks[0]
        assert unblock["action_type"] == "UNBLOCK_IP_NFTABLES"
        assert (await h.ack(unblock)).status_code == 200
        saved = (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()
        assert saved["status"] == "REVERTED"
        assert (await h.client.get("/api/v1/recovery/actions")).json()["items"][0][
            "status"
        ] == "SUCCESS"
        assert await h.heartbeat() == []
