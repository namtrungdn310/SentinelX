"""End-to-end integration tests for Milestone M4.

Pipeline: Network Telemetry -> Network Detection -> Incident -> Policy -> Defense Action.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.policy.service import get_policy_engine


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
async def test_m4_end_to_end_network_telemetry_detection_incident_policy_flow(
    test_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Full lifecycle verification for Milestone M4:

    1. Register Project, Node, and enroll Agent.
    2. Configure Defense Policy for syn_flood_detector (BLOCK_IP_NFTABLES).
    3. Configure IP Whitelist for trusted subnet (192.168.1.0/24).
    4. Ingest external SYN flood attack (203.0.113.195) via /telemetry/network-features.
    5. Assert DetectionEvent is saved with attacker_ip and details.
    6. Assert an Incident is created/grouped for the attack.
    7. Assert DefenseAction (BLOCK_IP_NFTABLES) is automatically created (M6 integration).
    8. Assert Agent Heartbeat receives the BLOCK_IP_NFTABLES command!
    9. Ingest attack from whitelisted IP (192.168.1.50) -> action denied by whitelist!
    """
    app, _ = test_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup project
        p_res = await client.post("/api/v1/projects", json={"name": "M4-Network-Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["project_id"]

        # Setup node
        n_res = await client.post(
            "/api/v1/nodes",
            json={
                "project_id": project_id,
                "hostname": "prod-linux-node-m4",
                "ip_address": "192.168.1.100",
            },
        )
        assert n_res.status_code == 201
        node_id = n_res.json()["node_id"]

        # Enroll agent
        token_res = await client.post(
            f"/api/v1/nodes/{node_id}/enrollment-tokens",
            json={"expires_in_hours": 1},
        )
        assert token_res.status_code == 201
        enrollment_token = token_res.json()["enrollment_token"]

        enroll_res = await client.post(
            "/api/v1/nodes/enroll",
            json={
                "node_id": node_id,
                "enrollment_token": enrollment_token,
                "agent_version": "0.1.0",
                "hostname": "prod-linux-node-m4",
            },
        )
        assert enroll_res.status_code == 200
        agent_id = enroll_res.json()["agent_id"]

        # Reset policy engine state
        get_policy_engine().clear_state()

        # 2. Configure defense policy for SYN Flood
        pol_res = await client.post(
            f"/api/v1/projects/{project_id}/defense-policies",
            json={
                "name": "Auto Block SYN Flooders",
                "event_type": "syn_flood_detector",
                "action_type": "BLOCK_IP_NFTABLES",
                "target_params": {},
                "cooldown_seconds": 300,
                "block_duration_seconds": 1800,
                "enabled": True,
            },
        )
        assert pol_res.status_code == 201

        # 3. Configure IP Whitelist for trusted admin subnet
        wl_res = await client.post(
            f"/api/v1/projects/{project_id}/ip-whitelist",
            json={
                "ip_or_cidr": "192.168.1.0/24",
                "description": "Internal trusted management subnet",
            },
        )
        assert wl_res.status_code == 201

        # 4. Ingest malicious external SYN flood attack (source_ip: 203.0.113.195)
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=5)
        window_end = now
        window_id = str(uuid.uuid4())

        network_payload = {
            "node_id": node_id,
            "agent_id": agent_id,
            "sequence": 1,
            "sent_at": now.isoformat(),
            "windows": [
                {
                    "window_id": window_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "interface": "eth0",
                    "features": [
                        {
                            "source_ip": "203.0.113.195",
                            "destination_ip": "192.168.1.100",
                            "protocol": "tcp",
                            "packet_count": 210,
                            "byte_count": 10500,
                            "syn_count": 200,
                            "ack_count": 0,
                            "destination_ports": [80],
                        }
                    ],
                }
            ],
        }

        ingest_res = await client.post("/api/v1/telemetry/network-features", json=network_payload)
        assert ingest_res.status_code == 200
        assert ingest_res.json()["processed_count"] == 1

        # 5. Query detection events: 1 CRITICAL event with attacker_ip == "203.0.113.195"
        ev_res = await client.get("/api/v1/detection-events", params={"node_id": node_id})
        assert ev_res.status_code == 200
        events_data = ev_res.json()
        assert events_data["total"] >= 1
        event = events_data["items"][0]
        assert event["detector_name"] == "syn_flood_detector"
        assert event["attacker_ip"] == "203.0.113.195"
        assert event["severity"] == "CRITICAL"
        assert event["incident_id"] is not None
        assert event["details"]["attack_type"] == "SYN_FLOOD"

        incident_id = event["incident_id"]

        # 6. Query incidents API: should have active incident
        inc_res = await client.get("/api/v1/incidents", params={"project_id": project_id})
        assert inc_res.status_code == 200
        inc_data = inc_res.json()
        assert inc_data["total"] == 1
        incident = inc_data["items"][0]
        assert incident["id"] == incident_id
        assert incident["status"] == "DETECTED"
        assert incident["severity"] == "CRITICAL"
        assert incident["event_count"] >= 1

        # 7. Check DefenseAction automatically created for BLOCK_IP_NFTABLES (M6 Integration)
        actions_res = await client.get(f"/api/v1/defense/actions?node_id={node_id}")
        assert actions_res.status_code == 200
        actions = actions_res.json()["items"]
        assert len(actions) == 1
        action = actions[0]
        assert action["action_type"] == "BLOCK_IP_NFTABLES"
        assert action["target_ip"] == "203.0.113.195"
        assert action["status"] == "PENDING"
        action_id = action["id"]

        # 8. Agent sends Heartbeat -> Piggybacked command received!
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
        assert len(hb_data["commands"]) == 1
        cmd = hb_data["commands"][0]
        assert cmd["id"] == action_id
        assert cmd["action_type"] == "BLOCK_IP_NFTABLES"
        assert cmd["command_payload"]["target"] == "203.0.113.195"

        # 9. Ingest attack from whitelisted IP (192.168.1.50)
        wl_attack_id = str(uuid.uuid4())
        wl_payload = {
            "node_id": node_id,
            "agent_id": agent_id,
            "sequence": 2,
            "sent_at": (now + timedelta(seconds=10)).isoformat(),
            "windows": [
                {
                    "window_id": wl_attack_id,
                    "window_start": (now + timedelta(seconds=5)).isoformat(),
                    "window_end": (now + timedelta(seconds=10)).isoformat(),
                    "interface": "eth0",
                    "features": [
                        {
                            "source_ip": "192.168.1.50",
                            "destination_ip": "192.168.1.100",
                            "protocol": "tcp",
                            "packet_count": 250,
                            "byte_count": 12000,
                            "syn_count": 220,
                            "ack_count": 0,
                            "destination_ports": [80],
                        }
                    ],
                }
            ],
        }
        wl_ingest_res = await client.post("/api/v1/telemetry/network-features", json=wl_payload)
        assert wl_ingest_res.status_code == 200

        # Evaluate policy for whitelisted IP: MUST BE DENIED_WHITELIST!
        wl_eval_res = await client.post(
            f"/api/v1/projects/{project_id}/policy/evaluate",
            json={
                "event": {
                    "id": str(uuid.uuid4()),
                    "node_id": node_id,
                    "detector_name": "syn_flood_detector",
                    "severity": "CRITICAL",
                    "attacker_ip": "192.168.1.50",
                    "confidence_score": 0.95,
                    "details": {
                        "attack_type": "SYN_FLOOD",
                        "source_ip": "192.168.1.50",
                        "destination_ip": "192.168.1.100",
                        "protocol": "tcp",
                        "packet_count": 250,
                        "byte_count": 12000,
                        "syn_count": 220,
                        "ack_count": 0,
                    },
                    "detected_at": now.isoformat(),
                }
            },
        )
        assert wl_eval_res.status_code == 200
        assert wl_eval_res.json()["authorized"] is False
        assert wl_eval_res.json()["status"] == "DENIED_WHITELIST"
