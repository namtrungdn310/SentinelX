"""Full End-to-End integration test for Milestone M8: Recovery and Cooldown Pipeline."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.executors.simulated import SimulatedDefenseExecutor
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.incidents.models import IncidentModel


@pytest.fixture
async def test_app() -> AsyncGenerator[tuple[FastAPI, async_sessionmaker[AsyncSession]], None]:
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller",
        database=DatabaseSettings(url=test_db_url),
    )
    app = create_app(settings=settings)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield app, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_m8_end_to_end_recovery_pipeline(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Project & Node Registration & Enrollment
        p_res = await client.post("/api/v1/projects", json={"name": "M8 Lab"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "linux-guard-01",
                "ip_address": "192.168.1.150",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        tok_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        token = tok_res.json()["enrollment_token"]

        enr_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": token,
                "hostname": "linux-guard-01",
                "agent_version": "0.1.0",
            },
        )
        agent_id = enr_res.json()["agent_id"]

        # 2. Create Incident via DB
        import uuid
        incident_id = str(uuid.uuid4())
        async with session_factory() as session:
            inc_model = IncidentModel(
                id=uuid.UUID(incident_id),
                project_id=uuid.UUID(project_id),
                title="Port Scan and SYN Flood Anomaly",
                status="DETECTED",
                severity="HIGH",
                started_at=datetime.now(UTC),
            )
            session.add(inc_model)
            await session.commit()

        # 3. Create active BLOCK_IP_NFTABLES defense action with short block_duration_seconds=1
        target_attacker_ip = "198.51.100.99"
        act_res = await client.post(
            "/api/v1/defense/actions",
            json={
                "node_id": node_id,
                "incident_id": incident_id,
                "action_type": "BLOCK_IP_NFTABLES",
                "target_ip": target_attacker_ip,
                "command_payload": {"block_duration_seconds": 1},
            },
        )
        assert act_res.status_code == 201
        block_action_id = act_res.json()["id"]

        # 4. Agent heartbeats and receives the BLOCK_IP_NFTABLES command
        now = datetime.now(UTC)
        hb_res = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": now.isoformat(),
            },
        )
        assert hb_res.status_code == 200
        hb_commands = hb_res.json()["commands"]
        assert len(hb_commands) == 1
        assert hb_commands[0]["id"] == block_action_id
        assert hb_commands[0]["action_type"] == "BLOCK_IP_NFTABLES"

        # 5. Agent executes block command using SimulatedDefenseExecutor
        sim_executor = SimulatedDefenseExecutor()
        agent_settings = AgentSettings(
            controller_url="http://test",
            node_id=node_id,
            defense_executor_type="simulated",
        )
        processor = CommandProcessor(settings=agent_settings, executor=sim_executor)
        block_cmd_contract = AgentCommandContract.model_validate(hb_commands[0])

        mock_agent_client = AsyncMock(spec=ControllerClient)
        await processor.process_command(block_cmd_contract, mock_agent_client)

        assert target_attacker_ip in sim_executor.blocked_ips
        mock_agent_client.ack_defense_action.assert_awaited_once()
        block_ack_req = mock_agent_client.ack_defense_action.call_args[0][1]

        # Submit block ACK to Controller
        ack_res = await client.post(
            f"/api/v1/defense/actions/{block_action_id}/ack",
            json=block_ack_req.model_dump(mode="json"),
        )
        assert ack_res.status_code == 200

        # Verify action is APPLIED and incident is MITIGATING
        check_act = await client.get(f"/api/v1/defense/actions/{block_action_id}")
        assert check_act.json()["status"] == "APPLIED"

        check_inc = await client.get(f"/api/v1/incidents/{incident_id}")
        assert check_inc.json()["status"] == "MITIGATING"

        # 6. Wait for block_duration_seconds=1 to expire
        await asyncio.sleep(1.1)

        # 7. Next Agent heartbeat triggers automatic expiry scan and piggybacks UNBLOCK_IP_NFTABLES!
        hb2_res = await client.post(
            "/api/v1/nodes/heartbeat",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 2,
                "sent_at": datetime.now(UTC).isoformat(),
            },
        )
        assert hb2_res.status_code == 200
        hb2_commands = hb2_res.json()["commands"]
        assert len(hb2_commands) == 1
        unblock_cmd = hb2_commands[0]
        assert unblock_cmd["action_type"] == "UNBLOCK_IP_NFTABLES"
        assert unblock_cmd["target_ip"] == target_attacker_ip
        unblock_action_id = unblock_cmd["id"]

        # 8. Agent executes unblock command
        unblock_cmd_contract = AgentCommandContract.model_validate(unblock_cmd)
        mock_agent_client.reset_mock()
        await processor.process_command(unblock_cmd_contract, mock_agent_client)

        # Verify IP is no longer in blocked_ips on Agent
        assert target_attacker_ip not in sim_executor.blocked_ips
        mock_agent_client.ack_defense_action.assert_awaited_once()
        unblock_ack_req = mock_agent_client.ack_defense_action.call_args[0][1]
        assert unblock_ack_req.status == "APPLIED"

        # Submit unblock ACK to Controller
        ack2_res = await client.post(
            f"/api/v1/defense/actions/{unblock_action_id}/ack",
            json=unblock_ack_req.model_dump(mode="json"),
        )
        assert ack2_res.status_code == 200

        # 9. Verify Closed-Loop Recovery State
        # a) Original defense action is REVERTED
        orig_res = await client.get(f"/api/v1/defense/actions/{block_action_id}")
        assert orig_res.status_code == 200
        assert orig_res.json()["status"] == "REVERTED"

        # b) Recovery action is recorded with status SUCCESS and reason TIMEOUT_EXPIRED
        rec_list_res = await client.get("/api/v1/recovery/actions")
        assert rec_list_res.status_code == 200
        rec_data = rec_list_res.json()
        assert rec_data["total"] >= 1
        matching_rec = next(
            (r for r in rec_data["items"] if r["defense_action_id"] == block_action_id),
            None,
        )
        assert matching_rec is not None
        assert matching_rec["status"] == "SUCCESS"
        assert matching_rec["reason"] == "TIMEOUT_EXPIRED"

        # c) Incident transitioned from MITIGATING to RESOLVED
        inc_final_res = await client.get(f"/api/v1/incidents/{incident_id}")
        assert inc_final_res.status_code == 200
        final_inc = inc_final_res.json()
        assert final_inc["status"] == "RESOLVED"
        assert final_inc["resolved_at"] is not None
