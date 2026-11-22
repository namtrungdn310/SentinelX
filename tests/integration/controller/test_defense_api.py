"""Authenticated leases and state-machine regression tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from sentinelx_controller.modules.defense.models import DefenseActionModel
from tests.core_helpers import core_harness


@pytest.mark.asyncio
async def test_defense_action_lifecycle_and_heartbeat_dispatch() -> None:
    async with core_harness() as h:
        action = await h.block()
        assert await h.heartbeat(version=1) == []
        command = (await h.heartbeat())[0]
        assert command["id"] == action["id"]
        assert await h.heartbeat() == []
        ack = await h.ack(command)
        assert ack.status_code == 200, ack.text
        saved = (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()
        assert saved["status"] == "APPLIED"
        assert saved["execution_metadata"] == {"executor": "nftables"}
        assert saved["effective_until"] and saved["applied_at"]
        assert await h.heartbeat() == []


@pytest.mark.asyncio
async def test_lost_response_is_redelivered_without_changing_identity() -> None:
    async with core_harness() as h:
        action = await h.block()
        first = (await h.heartbeat())[0]
        async with h.sessions() as db:
            row = await db.get(DefenseActionModel, UUID(action["id"]))
            assert row is not None
            row.leased_until = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
        second = (await h.heartbeat())[0]
        assert first == second
        assert (await h.ack(second)).status_code == 200


@pytest.mark.asyncio
async def test_ack_requires_owner_delivery_token_and_terminal_result() -> None:
    async with core_harness() as h:
        action = await h.block()
        command = (await h.heartbeat())[0]
        assert (await h.ack(command, agent_id=str(uuid4()))).status_code == 403
        assert (await h.ack(command, node_id=str(uuid4()))).status_code == 403
        assert (await h.ack(command, delivery_token="wrong")).status_code == 409
        assert (await h.ack(command, action_id=str(uuid4()))).status_code == 422
        assert (await h.ack(command, state="PENDING")).status_code == 422
        assert (await h.ack(command, execution_metadata={"simulated": True})).status_code == 422
        result = await h.ack(command, state="SIMULATED", execution_metadata={"simulated": True})
        assert result.status_code == 200
        same = await h.ack(command, state="SIMULATED", execution_metadata={"simulated": True})
        assert same.status_code == 200
        assert (await h.ack(command)).status_code == 409
        saved = (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()
        assert saved["status"] == "SIMULATED"
        assert saved["applied_at"] is None


@pytest.mark.asyncio
async def test_delivery_expiry_and_duplicate_manual_ownership() -> None:
    async with core_harness() as h:
        action = await h.block()
        duplicate = await h.client.post(
            "/api/v1/defense/actions",
            json={
                "node_id": h.node,
                "action_type": "BLOCK_IP_NFTABLES",
                "target_ip": action["target_ip"],
            },
        )
        assert duplicate.status_code == 409
        async with h.sessions() as db:
            row = await db.get(DefenseActionModel, UUID(action["id"]))
            assert row is not None
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
        assert await h.heartbeat() == []
        saved = (await h.client.get(f"/api/v1/defense/actions/{action['id']}")).json()
        assert saved["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_operator_cancels_only_before_delivery() -> None:
    async with core_harness() as h:
        action = await h.block()
        for _ in range(2):
            response = await h.client.post(f"/api/v1/defense/actions/{action['id']}/cancel")
            assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
        assert await h.heartbeat() == []
        next_action = await h.block()
        assert len(await h.heartbeat()) == 1
        assert (
            await h.client.post(f"/api/v1/defense/actions/{next_action['id']}/cancel")
        ).status_code == 409


@pytest.mark.asyncio
async def test_incident_tracks_delivery_and_execution_failures() -> None:
    from sentinelx_controller.modules.incidents.models import IncidentModel

    async with core_harness() as h:
        incident_id = uuid4()
        async with h.sessions() as db:
            db.add(
                IncidentModel(
                    id=incident_id,
                    project_id=UUID(h.project),
                    node_id=UUID(h.node),
                    title="Tấn công SYN Flood",
                    status="DETECTED",
                    severity="CRITICAL",
                    started_at=datetime.now(UTC),
                    summary="SYN: 200 · ACK: 1 · IP: 198.51.100.88",
                    correlation_key="network:198.51.100.88",
                )
            )
            await db.commit()

        expired_action = await h.block(
            incident_id=str(incident_id),
            target_ip="198.51.100.88",
        )
        async with h.sessions() as db:
            row = await db.get(DefenseActionModel, UUID(expired_action["id"]))
            assert row is not None
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()

        assert await h.heartbeat() == []
        inc_delivery = (await h.client.get(f"/api/v1/incidents/{incident_id}")).json()
        assert inc_delivery["status"] == "DETECTED"
        assert inc_delivery["defense_status"] == "DELIVERY_FAILED"
        assert "lỗi tải lệnh:" in inc_delivery["summary"]

        retry_action = await h.block(
            incident_id=str(incident_id),
            target_ip="198.51.100.88",
        )
        command = (await h.heartbeat())[0]
        assert command["id"] == retry_action["id"]
        ack_res = await h.ack(command, state="FAILED", error_message="nftables rule rejected")
        assert ack_res.status_code == 200

        inc_exec = (await h.client.get(f"/api/v1/incidents/{incident_id}")).json()
        assert inc_exec["status"] == "DETECTED"
        assert inc_exec["defense_status"] == "EXECUTION_FAILED"
        assert "lỗi kích hoạt: nftables rule rejected" in inc_exec["summary"]
