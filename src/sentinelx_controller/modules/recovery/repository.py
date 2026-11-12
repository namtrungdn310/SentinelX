"""Repository layer for persisting and querying recovery actions."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.recovery.models import RecoveryActionModel


class RecoveryRepository:
    """Data access layer for recovery_actions table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_recovery(self, recovery: RecoveryActionModel) -> RecoveryActionModel:
        """Persist a new recovery action record."""
        self._session.add(recovery)
        await self._session.flush()
        return recovery

    async def get_by_id(self, recovery_id: uuid.UUID) -> RecoveryActionModel | None:
        """Fetch single recovery action by ID."""
        stmt = select(RecoveryActionModel).where(RecoveryActionModel.id == recovery_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_defense_action_id(
        self,
        defense_action_id: uuid.UUID,
    ) -> RecoveryActionModel | None:
        """Fetch recovery action associated with a given defense action ID."""
        stmt = (
            select(RecoveryActionModel)
            .where(RecoveryActionModel.defense_action_id == defense_action_id)
            .order_by(RecoveryActionModel.executed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recoveries(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, Sequence[RecoveryActionModel]]:
        """List recovery actions with optional status filter and pagination."""
        count_stmt = select(func.count(RecoveryActionModel.id))
        items_stmt = select(RecoveryActionModel).order_by(RecoveryActionModel.executed_at.desc())

        if status:
            count_stmt = count_stmt.where(RecoveryActionModel.status == status)
            items_stmt = items_stmt.where(RecoveryActionModel.status == status)

        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one() or 0

        items_stmt = items_stmt.limit(limit).offset(offset)
        items_res = await self._session.execute(items_stmt)
        items = list(items_res.scalars().all())

        return total, items

    async def save(self, recovery: RecoveryActionModel) -> RecoveryActionModel:
        """Flush changes to a recovery action."""
        await self._session.flush()
        return recovery
