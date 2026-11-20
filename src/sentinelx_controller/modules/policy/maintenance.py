"""Prune old decision snapshots in bounded batches, preserving command/recovery audit."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.policy.models import (
    DefensePolicyModel,
    PolicyDecisionModel,
    PolicyExecutionStateModel,
)


async def prune_decisions(
    session: AsyncSession,
    cutoff: datetime,
    limit: int,
    *,
    apply: bool,
) -> int:
    ids = list(
        (
            await session.execute(
                select(PolicyDecisionModel.id)
                .where(PolicyDecisionModel.created_at < cutoff)
                .order_by(PolicyDecisionModel.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True),
            )
        )
        .scalars()
        .all()
    )
    if ids and apply:
        await session.execute(delete(PolicyDecisionModel).where(PolicyDecisionModel.id.in_(ids)))
    return len(ids)


async def prune_cooldowns(session: AsyncSession, now: datetime, limit: int, *, apply: bool) -> int:
    # Respect even pre-upgrade policies with longer custom cooldowns; never truncate a live one.
    maximum = (
        await session.execute(select(func.max(DefensePolicyModel.cooldown_seconds)))
    ).scalar_one()
    cutoff = now - timedelta(seconds=max(86400, min(maximum or 0, 2**31)))
    keys = list(
        (
            await session.execute(
                select(PolicyExecutionStateModel.key)
                .where(
                    or_(
                        PolicyExecutionStateModel.last_authorized_at.is_(None),
                        PolicyExecutionStateModel.last_authorized_at < cutoff,
                    ),
                )
                .order_by(PolicyExecutionStateModel.last_authorized_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    if keys and apply:
        await session.execute(
            delete(PolicyExecutionStateModel).where(PolicyExecutionStateModel.key.in_(keys))
        )
    return len(keys)
