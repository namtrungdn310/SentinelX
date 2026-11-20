"""Repository for DefenseAction database operations."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.defense import DefenseActionStatus
from sentinelx_controller.infrastructure.database.locking import lock_node_transaction
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

    async def lock_node(self, node_id: uuid.UUID) -> None:
        """Serialize commands for a node across Controller processes on PostgreSQL."""
        await lock_node_transaction(self._session, node_id)

    async def lock_action(self, action_id: uuid.UUID) -> DefenseActionModel | None:
        existing = await self.get_by_id(action_id)
        if existing is None:
            return None
        await self.lock_node(existing.node_id)
        return (
            await self._session.execute(
                select(DefenseActionModel)
                .where(DefenseActionModel.id == action_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

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
            base_query.order_by(DefenseActionModel.created_at.desc()).limit(limit).offset(offset)
        )
        items_result = await self._session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return total, items

    async def get_and_mark_pending_commands(
        self,
        node_id: uuid.UUID,
        limit: int = 20,
        lease_seconds: int = 30,
        max_attempts: int = 5,
        supported_actions: list[str] | None = None,
    ) -> list[DefenseActionModel]:
        """Claim pending/expired leases, bounded by command expiry and retry budget."""
        await self.lock_node(node_id)
        now = datetime.now(UTC)
        stmt = (
            select(DefenseActionModel)
            .where(
                DefenseActionModel.node_id == node_id,
                DefenseActionModel.status.in_(["PENDING", "SENT"]),
                or_(
                    DefenseActionModel.leased_until.is_(None),
                    DefenseActionModel.leased_until <= now,
                ),
            )
            .order_by(DefenseActionModel.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        actions = list(result.scalars().all())

        claimed: list[DefenseActionModel] = []
        for action in actions:
            if supported_actions is not None and action.action_type not in supported_actions:
                action.status = "FAILED"
                action.error_message = "Agent does not advertise support for this action"
                continue
            expiry = (
                action.expires_at.replace(tzinfo=UTC)
                if action.expires_at.tzinfo is None
                else action.expires_at
            )
            if expiry <= now or action.attempts >= max_attempts:
                action.status = DefenseActionStatus.EXPIRED.value
                action.error_message = (
                    "Command expired or delivery attempts exhausted; reconcile host state"
                )
                continue
            action.status = DefenseActionStatus.SENT.value
            action.delivery_token = action.delivery_token or secrets.token_urlsafe(32)
            action.leased_until = now + timedelta(seconds=lease_seconds)
            action.attempts += 1
            claimed.append(action)

        if actions:
            await self._session.flush()

        return claimed

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
