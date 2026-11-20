"""A common transaction lock order for node-scoped state transitions."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_node_transaction(session: AsyncSession, node_id: UUID) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": int.from_bytes(node_id.bytes[:8], "big", signed=True)},
        )
