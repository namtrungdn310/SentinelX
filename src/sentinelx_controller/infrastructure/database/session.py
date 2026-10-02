"""Manage database engine and async session lifecycle."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sentinelx_controller.config import DatabaseSettings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Initialize async database engine and session factory.

    Args:
        settings: Database settings containing connection URL and pool limits.

    Returns:
        The configured AsyncEngine instance.
    """
    global _engine, _session_factory

    engine_kwargs: dict[str, Any] = {"echo": settings.echo}

    # SQLite does not accept pool_size and max_overflow arguments
    if "sqlite" not in settings.url:
        engine_kwargs["pool_size"] = settings.pool_size
        engine_kwargs["max_overflow"] = settings.max_overflow
        engine_kwargs["pool_timeout"] = settings.pool_timeout

    logger.info("Initializing database engine", extra={"url_prefix": settings.url.split("@")[-1]})
    _engine = create_async_engine(settings.url, **engine_kwargs)
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return _engine


async def close_db_engine() -> None:
    """Close and dispose the active database engine."""
    global _engine, _session_factory

    if _engine is not None:
        logger.info("Closing database engine and connections")
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    """Get the current database engine.

    Returns:
        Active AsyncEngine.

    Raises:
        RuntimeError: If the engine is not initialized.
    """
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_db_engine() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the current session factory.

    Returns:
        Active async_sessionmaker instance.

    Raises:
        RuntimeError: If the session factory is not initialized.
    """
    if _session_factory is None:
        raise RuntimeError("Database session factory is not initialized.")
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Yields:
        AsyncSession: Active database session with transaction management.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_readiness(engine: AsyncEngine | None = None) -> tuple[bool, str | None]:
    """Run a light SELECT 1 query to verify database connectivity.

    Args:
        engine: Optional engine to use. If None, uses global engine.

    Returns:
        Tuple of (is_connected: bool, error_message: str | None).
    """
    target_engine = engine or _engine
    if target_engine is None:
        return False, "Database engine is not initialized"

    try:
        async with target_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return False, str(exc)
