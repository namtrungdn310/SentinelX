"""Database repository for defense policies and IP whitelist."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.policy.models import (
    DefensePolicyModel,
    IPWhitelistModel,
    PolicyDecisionModel,
    PolicyExecutionStateModel,
)


class PolicyRepository:
    """Data access layer for defense_policies and ip_whitelist tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def cooldown(
        self,
        node_id: uuid.UUID,
        policy_id: str,
        target: str,
        *,
        lock: bool,
    ) -> PolicyExecutionStateModel | None:
        key = hashlib.sha256(f"{node_id}:{policy_id}:{target}".encode()).hexdigest()
        if lock:
            insert = (
                sqlite_insert if self._session.get_bind().dialect.name == "sqlite" else pg_insert
            )
            await self._session.execute(
                insert(PolicyExecutionStateModel)
                .values(key=key, node_id=node_id)
                .on_conflict_do_nothing(index_elements=["key"]),
            )
        query = select(PolicyExecutionStateModel).where(PolicyExecutionStateModel.key == key)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return (await self._session.execute(query)).scalar_one_or_none()

    async def audit(self, decision: PolicyDecisionModel) -> None:
        self._session.add(decision)
        await self._session.flush()

    # ─── DEFENSE POLICIES ───

    async def decisions(
        self, node_id: uuid.UUID | None, limit: int, offset: int
    ) -> list[PolicyDecisionModel]:
        statement = select(PolicyDecisionModel)
        if node_id is not None:
            statement = statement.where(PolicyDecisionModel.node_id == node_id)
        result = await self._session.execute(
            statement.order_by(PolicyDecisionModel.created_at.desc(), PolicyDecisionModel.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_policy(self, policy: DefensePolicyModel) -> DefensePolicyModel:
        """Tạo chính sách phòng thủ mới."""
        self._session.add(policy)
        await self._session.flush()
        return policy

    async def get_policy_by_id(self, policy_id: uuid.UUID) -> DefensePolicyModel | None:
        """Lấy chính sách theo UUID."""
        stmt = select(DefensePolicyModel).where(DefensePolicyModel.id == policy_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_policies(
        self,
        project_id: uuid.UUID | None = None,
        enabled_only: bool = False,
    ) -> list[DefensePolicyModel]:
        """Truy vấn danh sách chính sách phòng thủ."""
        stmt = select(DefensePolicyModel)
        if project_id is not None:
            stmt = stmt.where(DefensePolicyModel.project_id == project_id)
        if enabled_only:
            stmt = stmt.where(DefensePolicyModel.enabled.is_(True))

        stmt = stmt.order_by(DefensePolicyModel.priority, DefensePolicyModel.id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_policy(self, policy: DefensePolicyModel) -> DefensePolicyModel:
        """Lưu cập nhật chính sách."""
        await self._session.flush()
        return policy

    async def delete_policy(self, policy: DefensePolicyModel) -> None:
        """Xóa chính sách."""
        await self._session.delete(policy)
        await self._session.flush()

    # ─── IP WHITELIST ───

    async def create_whitelist(self, entry: IPWhitelistModel) -> IPWhitelistModel:
        """Thêm dải IP an toàn."""
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_whitelist_by_id(self, entry_id: uuid.UUID) -> IPWhitelistModel | None:
        """Lấy whitelist entry theo UUID."""
        stmt = select(IPWhitelistModel).where(IPWhitelistModel.id == entry_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_whitelist(self, project_id: uuid.UUID) -> list[IPWhitelistModel]:
        """Lấy toàn bộ whitelist entries của project."""
        stmt = (
            select(IPWhitelistModel)
            .where(IPWhitelistModel.project_id == project_id)
            .order_by(IPWhitelistModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_whitelist(self, entry: IPWhitelistModel) -> None:
        """Xóa dải IP khỏi whitelist."""
        await self._session.delete(entry)
        await self._session.flush()
