"""Operator-run bounded maintenance. Dry-run by default; no startup deletions."""

import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.config import ControllerSettings
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.detection.engine import DetectionEngine
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.repository import AgentEnrollmentRepository, NodeRepository
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.maintenance import prune_cooldowns, prune_decisions
from sentinelx_controller.modules.policy.repository import PolicyRepository
from sentinelx_controller.modules.policy.service import PolicyService
from sentinelx_controller.modules.projects.repository import ProjectRepository
from sentinelx_controller.modules.projects.service import ProjectService
from sentinelx_controller.modules.recovery.repository import RecoveryRepository
from sentinelx_controller.modules.recovery.service import RecoveryService
from sentinelx_controller.modules.telemetry.maintenance import prune_telemetry

logger = logging.getLogger("sentinelx_controller.maintenance")


async def run_supervisor_tick(
    settings: ControllerSettings,
    session_factory: async_sessionmaker[AsyncSession],
    realtime_hub: RealtimeHub | None = None,
) -> dict[str, int]:
    """Run one periodic recovery scan and stale-node offline sweep."""
    hub = realtime_hub or get_realtime_hub()
    bg_tasks = BackgroundTasks()
    publisher = CommittedPublisher(bg_tasks, hub)
    detection_engine = DetectionEngine(**settings.detection.model_dump())
    policy_engine = PolicyEngine()

    async with session_factory.begin() as session:
        project_service = ProjectService(ProjectRepository(session))
        node_service = NodeService(
            NodeRepository(session),
            project_service,
            AgentEnrollmentRepository(session),
            realtime_hub=hub,
            publisher=publisher,
        )
        detection_service = DetectionService(
            repository=DetectionRepository(session),
            engine=detection_engine,
            realtime_hub=hub,
            publisher=publisher,
        )
        incident_service = IncidentService(
            repository=IncidentRepository(session),
            detection_service=detection_service,
            realtime_hub=hub,
            publisher=publisher,
        )
        policy_service = PolicyService(
            repository=PolicyRepository(session),
            engine=policy_engine,
            protected_cidrs=settings.safety.protected_cidrs,
        )
        defense_service = DefenseService(
            DefenseRepository(session),
            hub,
            publisher,
            incident_service=incident_service,
            node_service=node_service,
            policy_service=policy_service,
            safety=settings.safety,
        )
        recovery_service = RecoveryService(
            recovery_repo=RecoveryRepository(session),
            defense_service=defense_service,
            incident_service=incident_service,
            realtime_hub=hub,
            publisher=publisher,
            safety=settings.safety,
        )
        defense_service.attach_recovery_handler(recovery_service.handle_unblock_ack)

        reverted = await recovery_service.scan_and_revert_expired_actions()
        offline_nodes = await node_service.sweep_stale_offline_nodes()

    await bg_tasks()
    return {
        "reverted_actions": len(reverted),
        "offline_nodes": len(offline_nodes),
    }


async def run(settings: ControllerSettings, *, apply: bool, batches: int) -> list[dict[str, int]]:
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, class_=AsyncSession)
    retention = settings.retention
    now = datetime.now(UTC)
    results: list[dict[str, int]] = []
    try:
        for _ in range(batches if apply else 1):
            async with factory.begin() as session:
                counts = await prune_telemetry(
                    session,
                    now - timedelta(days=retention.metric_days),
                    now - timedelta(days=retention.network_days),
                    retention.batch_size,
                    apply=apply,
                )
                counts["policy_decisions"] = await prune_decisions(
                    session,
                    now - timedelta(days=retention.policy_audit_days),
                    retention.batch_size,
                    apply=apply,
                )
                counts["policy_cooldowns"] = await prune_cooldowns(
                    session, now, retention.batch_size, apply=apply
                )
                results.append(counts)
                if not any(counts.values()):
                    break
    finally:
        await engine.dispose()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit bounded deletions")
    parser.add_argument("--batches", type=int, default=1)
    arguments = parser.parse_args()
    if not 1 <= arguments.batches <= 100:
        parser.error("batches must be between 1 and 100")
    result = asyncio.run(
        run(ControllerSettings.load(), apply=arguments.apply, batches=arguments.batches)
    )
    print(json.dumps({"applied": arguments.apply, "batches": result}))


if __name__ == "__main__":
    main()
