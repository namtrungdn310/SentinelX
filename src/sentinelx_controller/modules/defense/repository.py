"""Repository for DefenseAction database operations."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.defense import DefenseActionStatus
from sentinelx_controller.modules.defense.models import DefenseActionModel


class DefenseRepository:
    """Async repository for managing defense action persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_action(self, action: DefenseActionModel) -> DefenseActionModel:
        """Persist a new defense action."""
        self._session.add(action)
        await self._session.flush()
        return action

    async def get_by_id(self, action_id: uuid.UUID) -> DefenseActionModel | None:
        """Find a defense action by UUID."""
        stmt = select(DefenseActionModel).where(DefenseActionModel.id == action_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actions(
        self,
        node_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[DefenseActionModel]]:
        """List defense actions with optional filters and total count."""
        base_query = select(DefenseActionModel)
        count_query = select(func.count(DefenseActionModel.id))

        if node_id is not None:
            base_query = base_query.where(DefenseActionModel.node_id == node_id)
            count_query = count_query.where(DefenseActionModel.node_id == node_id)

        if incident_id is not None:
            base_query = base_query.where(DefenseActionModel.incident_id == incident_id)
            count_query = count_query.where(DefenseActionModel.incident_id == incident_id)

        if status is not None:
            base_query = base_query.where(DefenseActionModel.status == status)
            count_query = count_query.where(DefenseActionModel.status == status)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        items_stmt = (
            base_query.order_by(DefenseActionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items_result = await self._session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return total, items

    async def get_and_mark_pending_commands(
        self,
        node_id: uuid.UUID,
        limit: int = 20,
    ) -> list[DefenseActionModel]:
        """Fetch PENDING commands for a node and transition status to SENT."""
        stmt = (
            select(DefenseActionModel)
            .where(
                DefenseActionModel.node_id == node_id,
                DefenseActionModel.status == DefenseActionStatus.PENDING.value,
            )
            .order_by(DefenseActionModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        actions = list(result.scalars().all())

        for action in actions:
            action.status = DefenseActionStatus.SENT.value

        if actions:
            await self._session.flush()

        return actions

    async def record_ack(
        self,
        action: DefenseActionModel,
        status: str,
        agent_ack_at: datetime,
        error_message: str | None = None,
    ) -> DefenseActionModel:
        """Update action with agent execution acknowledgment."""
        action.status = status
        action.agent_ack_at = agent_ack_at
        action.error_message = error_message
        await self._session.flush()
        return action

    async def has_active_action(
        self,
        node_id: uuid.UUID,
        action_type: str,
        target_ip: str | None,
    ) -> bool:
        """Check if an active action (PENDING, SENT, APPLIED) already exists for this target."""
        active_statuses = [
            DefenseActionStatus.PENDING.value,
            DefenseActionStatus.SENT.value,
            DefenseActionStatus.APPLIED.value,
        ]
        stmt = select(func.count(DefenseActionModel.id)).where(
            DefenseActionModel.node_id == node_id,
            DefenseActionModel.action_type == action_type,
            DefenseActionModel.status.in_(active_statuses),
        )
        if target_ip is not None:
            stmt = stmt.where(DefenseActionModel.target_ip == target_ip)
        else:
            stmt = stmt.where(DefenseActionModel.target_ip.is_(None))

        res = await self._session.execute(stmt)
        return (res.scalar_one() or 0) > 0

    async def get_applied_blocking_actions(
        self,
        node_id: uuid.UUID | None = None,
    ) -> list[DefenseActionModel]:
        """Fetch all currently APPLIED stateful actions that may expire."""
        stmt = select(DefenseActionModel).where(
            DefenseActionModel.status == DefenseActionStatus.APPLIED.value,
            DefenseActionModel.action_type.in_(["BLOCK_IP_NFTABLES", "RATE_LIMIT"]),
        )
        if node_id is not None:
            stmt = stmt.where(DefenseActionModel.node_id == node_id)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_active_blocking_actions_for_incident(
        self,
        incident_id: uuid.UUID,
    ) -> bool:
        """Check if any active blocking actions remain for an incident."""
        active_statuses = [
            DefenseActionStatus.PENDING.value,
            DefenseActionStatus.SENT.value,
            DefenseActionStatus.APPLIED.value,
        ]
        stmt = select(func.count(DefenseActionModel.id)).where(
            DefenseActionModel.incident_id == incident_id,
            DefenseActionModel.status.in_(active_statuses),
            DefenseActionModel.action_type != "UNBLOCK_IP_NFTABLES",
        )
        res = await self._session.execute(stmt)
        return (res.scalar_one() or 0) > 0
