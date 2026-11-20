"""Operator-run bounded maintenance. Dry-run by default; no startup deletions."""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.config import ControllerSettings
from sentinelx_controller.modules.policy.maintenance import prune_cooldowns, prune_decisions
from sentinelx_controller.modules.telemetry.maintenance import prune_telemetry


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
