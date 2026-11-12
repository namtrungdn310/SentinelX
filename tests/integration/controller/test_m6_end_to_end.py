"""Full End-to-End integration test for Milestone M6: Defense Command Pipeline."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session


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
async def test_m6_end_to_end_defense_pipeline(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Project & Node Registration
        p_res = await client.post("/api/v1/projects", json={"name": "PBL4 Lab"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "web-worker-01",
                "ip_address": "192.168.1.101",
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
                "hostname": "web-worker-01",
                "agent_version": "0.1.0",
            },
        )
        agent_id = enr_res.json()["agent_id"]
        assert enr_res.json()["heartbeat_interval_seconds"] == 7

        # 2. Configure Defense Policy with is_auto_execute=True
        pol_res = await client.post(
            f"/api/v1/projects/{project_id}/defense-policies",
            json={
                "name": "Auto Clear Cache on Spike",
                "event_type": "cpu_threshold_detector",
                "action_type": "CLEAR_OS_CACHE",
                "target_params": {},
                "is_auto_execute": True,
                "cooldown_seconds": 60,
                "block_duration_seconds": 0,
                "enabled": True,
            },
        )
        assert pol_res.status_code == 201

        # 3. Ingest metric samples triggering CPU anomaly (10 samples of 95% CPU)
        now = datetime.now(UTC)
        samples = []
        for i in range(10):
            samples.append(
                {
                    "observed_at": (now + timedelta(seconds=i)).isoformat(),
                    "cpu_percent": 95.0,
                    "memory_percent": 30.0,
                    "disk_percent": 40.0,
                    "network_rx_bytes": 1000,
                    "network_tx_bytes": 1000,
                }
            )

        telemetry_res = await client.post(
            "/api/v1/telemetry/metrics",
            json={
                "node_id": node_id,
                "agent_id": agent_id,
                "sequence": 1,
                "sent_at": now.isoformat(),
                "samples": samples,
            },
        )
        assert telemetry_res.status_code == 200

        # 4. Verify that Incident was created and DefenseAction was automatically created
        incidents_res = await client.get(f"/api/v1/incidents?project_id={project_id}")
        assert incidents_res.status_code == 200
        assert incidents_res.json()["total"] >= 1

        actions_res = await client.get(f"/api/v1/defense/actions?node_id={node_id}")
        assert actions_res.status_code == 200
        actions_data = actions_res.json()
        assert actions_data["total"] == 1
        action = actions_data["items"][0]
        assert action["status"] == "PENDING"
        assert action["action_type"] == "CLEAR_OS_CACHE"
        action_id = action["id"]

        # 5. Agent sends Heartbeat (piggybacking commands)
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
        hb_data = hb_res.json()
        assert hb_data["next_interval_seconds"] == 7
        assert len(hb_data["commands"]) == 1
        received_cmd = hb_data["commands"][0]
        assert received_cmd["id"] == action_id
        assert received_cmd["action_type"] == "CLEAR_OS_CACHE"

        # 6. Agent CommandProcessor executes command and reports ACK
        agent_settings = AgentSettings(
            controller_url="http://test",
            node_id=node_id,
            defense_executor_type="simulated",
        )
        processor = CommandProcessor(settings=agent_settings)

        from unittest.mock import AsyncMock

        from sentinelx_common.contracts.defense import AgentCommandContract
        cmd_contract = AgentCommandContract.model_validate(received_cmd)

        mock_agent_client = AsyncMock(spec=ControllerClient)
        await processor.process_command(cmd_contract, mock_agent_client)

        mock_agent_client.ack_defense_action.assert_awaited_once()
        ack_req = mock_agent_client.ack_defense_action.call_args[0][1]
        assert ack_req.status == "APPLIED"

        # Submit the actual ACK to Controller API
        ack_post = await client.post(
            f"/api/v1/defense/actions/{action_id}/ack",
            json=ack_req.model_dump(mode="json"),
        )
        assert ack_post.status_code == 200
        assert ack_post.json()["status"] == "ok"

        # 7. Check Controller DB confirms action status APPLIED
        final_action_res = await client.get(f"/api/v1/defense/actions/{action_id}")
        assert final_action_res.status_code == 200
        final_action = final_action_res.json()
        assert final_action["status"] == "APPLIED"
        assert final_action["agent_ack_at"] is not None
