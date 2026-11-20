"""Regression proofs for transactional policy state and bounded maintenance."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.policy import DefensePolicyCreateRequest, PolicyActionType
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.maintenance import prune_cooldowns, prune_decisions
from sentinelx_controller.modules.policy.models import (
    PolicyDecisionModel,
    PolicyExecutionStateModel,
)
from sentinelx_controller.modules.policy.repository import PolicyRepository
from sentinelx_controller.modules.policy.service import PolicyService
from sentinelx_controller.modules.telemetry.maintenance import prune_telemetry
from sentinelx_controller.modules.telemetry.models import TelemetryMetricSampleModel
from sentinelx_controller.modules.telemetry.network_models import NetworkWindowModel
from tests.core_helpers import core_harness


@pytest.mark.asyncio
async def test_policy_rollback_dryrun_restart_and_node_isolation() -> None:
    async with core_harness() as harness:
        event = DetectionEventContract.model_validate(
            {
                "id": str(uuid4()),
                "node_id": harness.node,
                "detector_name": "syn_flood_detector",
                "severity": "HIGH",
                "attacker_ip": "198.51.100.33",
                "confidence_score": 0.9,
                "detected_at": datetime.now(UTC),
                "details": {
                    "attack_type": "syn_flood",
                    "source_ip": "198.51.100.33",
                    "destination_ip": "192.0.2.11",
                    "protocol": "TCP",
                    "packet_count": 2000,
                    "extra_context": {"direction": "inbound"},
                },
            }
        )
        async with harness.sessions() as session:
            service = PolicyService(PolicyRepository(session), PolicyEngine())
            await service.create_policy(
                harness.project,
                DefensePolicyCreateRequest(
                    name="block",
                    event_type=event.detector_name,
                    action_type=PolicyActionType.BLOCK_IP_NFTABLES,
                ),
            )
            await session.commit()
            assert (
                await service.evaluate_event(UUID(harness.project), event, dry_run=True)
            ).authorized
            assert (
                await session.execute(select(func.count()).select_from(PolicyExecutionStateModel))
            ).scalar_one() == 0
            assert (
                await session.execute(select(func.count()).select_from(PolicyDecisionModel))
            ).scalar_one() == 0
            assert (await service.evaluate_event(UUID(harness.project), event)).authorized
            await (
                session.rollback()
            )  # A downstream insert failed: authorization must roll back too.
        async with harness.sessions() as session:
            service = PolicyService(PolicyRepository(session), PolicyEngine())
            assert (await service.evaluate_event(UUID(harness.project), event)).authorized
            await session.commit()
        async with harness.sessions() as session:
            service = PolicyService(PolicyRepository(session), PolicyEngine())
            assert not (await service.evaluate_event(UUID(harness.project), event)).authorized
            await session.commit()
        node = await harness.post(
            "/nodes",
            {"project_id": harness.project, "hostname": "isolated", "ip_address": "192.0.2.12"},
        )
        async with harness.sessions() as session:
            service = PolicyService(PolicyRepository(session), PolicyEngine())
            assert (
                await service.evaluate_event(
                    UUID(harness.project), event.model_copy(update={"node_id": node["node_id"]})
                )
            ).authorized
            await session.commit()
        response = await harness.client.get(
            "/api/v1/policy-decisions", params={"node_id": harness.node, "limit": 1}
        )
        assert response.status_code == 200 and len(response.json()) == 1


@pytest.mark.asyncio
async def test_retention_dryrun_and_each_batch_are_bounded() -> None:
    async with core_harness() as harness:
        cutoff = datetime.now(UTC) - timedelta(days=90)
        async with harness.sessions() as session:
            session.add_all(
                [
                    PolicyDecisionModel(
                        node_id=UUID(harness.node),
                        event_id=str(uuid4()),
                        created_at=cutoff - timedelta(days=1),
                        snapshot={},
                    )
                    for _ in range(3)
                ]
            )
            session.add(
                PolicyDecisionModel(
                    node_id=UUID(harness.node),
                    event_id=str(uuid4()),
                    created_at=datetime.now(UTC),
                    snapshot={},
                )
            )
            await session.commit()
            assert await prune_decisions(session, cutoff, 2, apply=False) == 2
            assert (
                await session.execute(select(func.count()).select_from(PolicyDecisionModel))
            ).scalar_one() == 4
            assert await prune_decisions(session, cutoff, 2, apply=True) == 2
            await session.commit()
            assert await prune_decisions(session, cutoff, 2, apply=True) == 1
            await session.commit()
            assert (
                await session.execute(select(func.count()).select_from(PolicyDecisionModel))
            ).scalar_one() == 1


@pytest.mark.asyncio
async def test_telemetry_retention_uses_receive_time_and_preserves_live_cooldown() -> None:
    async with core_harness() as harness:
        now = datetime.now(UTC)
        old = now - timedelta(days=10)
        async with harness.sessions.begin() as session:
            for _ in range(3):
                session.add(
                    TelemetryMetricSampleModel(
                        node_id=UUID(harness.node),
                        observed_at=now,
                        received_at=old,
                        cpu_usage_pct=1,
                        memory_usage_pct=1,
                    )
                )
                session.add(
                    NetworkWindowModel(
                        node_id=UUID(harness.node),
                        window_id=uuid4(),
                        window_start=old - timedelta(seconds=10),
                        window_end=old,
                        received_at=old,
                        interface="eth0",
                        features=[],
                        omitted_packets=0,
                        skipped_windows=0,
                    )
                )
            session.add(
                TelemetryMetricSampleModel(
                    node_id=UUID(harness.node),
                    observed_at=old,
                    received_at=now,
                    cpu_usage_pct=1,
                    memory_usage_pct=1,
                )
            )
            for index, stamp in enumerate((old, now)):
                session.add(
                    PolicyExecutionStateModel(
                        key=str(index), node_id=UUID(harness.node), last_authorized_at=stamp
                    )
                )
        async with harness.sessions.begin() as session:
            assert await prune_telemetry(
                session, now - timedelta(days=7), now - timedelta(days=3), 2, apply=False
            ) == {"metrics": 2, "network_windows": 2}
            assert await prune_cooldowns(session, now, 2, apply=False) == 1
        async with harness.sessions.begin() as session:
            assert await prune_telemetry(
                session, now - timedelta(days=7), now - timedelta(days=3), 2, apply=True
            ) == {"metrics": 2, "network_windows": 2}
            assert await prune_cooldowns(session, now, 2, apply=True) == 1
        async with harness.sessions() as session:
            assert (
                await session.execute(select(func.count()).select_from(TelemetryMetricSampleModel))
            ).scalar_one() == 2
            assert (
                await session.execute(select(func.count()).select_from(NetworkWindowModel))
            ).scalar_one() == 1
            assert (
                await session.execute(select(func.count()).select_from(PolicyExecutionStateModel))
            ).scalar_one() == 1
