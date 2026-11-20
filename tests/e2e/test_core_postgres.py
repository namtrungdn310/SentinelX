"""Opt-in row-lock tests in the dedicated PostgreSQL acceptance database."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.policy import DefensePolicyCreateRequest, PolicyActionType
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.repository import PolicyRepository
from sentinelx_controller.modules.policy.service import PolicyService
from tests.core_helpers import core_harness

URL = os.getenv("SENTINELX_CORE_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Requires isolated core PostgreSQL lab")


@pytest.mark.asyncio
async def test_two_controller_transactions_authorize_once_and_rollback_releases_cooldown() -> None:
    async with core_harness(URL) as harness:
        event = DetectionEventContract.model_validate(
            {
                "id": str(uuid4()),
                "node_id": harness.node,
                "detector_name": "syn_flood_detector",
                "severity": "HIGH",
                "confidence_score": 0.9,
                "attacker_ip": "198.51.100.18",
                "detected_at": datetime.now(UTC),
                "details": {
                    "attack_type": "syn_flood",
                    "source_ip": "198.51.100.18",
                    "destination_ip": "192.0.2.11",
                    "protocol": "tcp",
                    "packet_count": 2000,
                    "extra_context": {"direction": "inbound"},
                },
            }
        )
        async with harness.sessions.begin() as session:
            await PolicyService(PolicyRepository(session), PolicyEngine()).create_policy(
                harness.project,
                DefensePolicyCreateRequest(
                    name="concurrent",
                    event_type=event.detector_name,
                    action_type=PolicyActionType.BLOCK_IP_NFTABLES,
                ),
            )

        async def evaluate(candidate: DetectionEventContract, *, commit: bool = True) -> bool:
            async with harness.sessions() as session:
                service = PolicyService(PolicyRepository(session), PolicyEngine())
                result = await service.evaluate_event(UUID(harness.project), candidate)
                if commit:
                    await session.commit()
                else:
                    await session.rollback()
                return result.authorized

        assert sorted(await asyncio.gather(evaluate(event), evaluate(event))) == [False, True]
        retry = event.model_copy(update={"attacker_ip": "198.51.100.19"})
        assert await evaluate(retry, commit=False)
        assert await evaluate(retry)
