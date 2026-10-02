"""Unit tests for database session and engine lifecycle."""

import pytest
from sqlalchemy import text

from sentinelx_controller.config import DatabaseSettings
from sentinelx_controller.infrastructure.database.session import (
    check_db_readiness,
    close_db_engine,
    get_db_session,
    get_engine,
    get_session_factory,
    init_db_engine,
)


@pytest.mark.asyncio
async def test_uninitialized_engine_raises_error() -> None:
    """Test get_engine raises error before init."""
    await close_db_engine()
    with pytest.raises(RuntimeError, match="Database engine is not initialized"):
        get_engine()


@pytest.mark.asyncio
async def test_uninitialized_session_factory_raises_error() -> None:
    """Test get_session_factory raises error before init."""
    await close_db_engine()
    with pytest.raises(RuntimeError, match="Database session factory is not initialized"):
        get_session_factory()


@pytest.mark.asyncio
async def test_init_and_close_db_engine() -> None:
    """Test initializing and closing database engine with in-memory SQLite."""
    settings = DatabaseSettings(url="sqlite+aiosqlite:///:memory:")
    engine = init_db_engine(settings)
    assert engine is not None
    assert get_engine() is engine
    assert get_session_factory() is not None

    # Test readiness query
    is_ready, error = await check_db_readiness()
    assert is_ready is True
    assert error is None

    # Clean close
    await close_db_engine()
    with pytest.raises(RuntimeError):
        get_engine()


@pytest.mark.asyncio
async def test_get_db_session_success() -> None:
    """Test get_db_session yields an active session that commits cleanly."""
    settings = DatabaseSettings(url="sqlite+aiosqlite:///:memory:")
    init_db_engine(settings)

    try:
        session_gen = get_db_session()
        session = await anext(session_gen)
        result = await session.execute(text("SELECT 42"))
        val = result.scalar()
        assert val == 42

        # Finish generator without error
        with pytest.raises(StopAsyncIteration):
            await anext(session_gen)
    finally:
        await close_db_engine()


@pytest.mark.asyncio
async def test_get_db_session_rollback_on_error() -> None:
    """Test get_db_session rolls back when an exception occurs."""
    settings = DatabaseSettings(url="sqlite+aiosqlite:///:memory:")
    init_db_engine(settings)

    try:
        session_gen = get_db_session()
        session = await anext(session_gen)
        assert session.is_active

        # Throw exception into generator
        with pytest.raises(ValueError, match="Simulated error"):
            await session_gen.athrow(ValueError("Simulated error"))
    finally:
        await close_db_engine()


@pytest.mark.asyncio
async def test_check_db_readiness_failure_when_engine_none() -> None:
    """Test check_db_readiness returns False when engine is None."""
    await close_db_engine()
    is_ready, error = await check_db_readiness()
    assert is_ready is False
    assert error == "Database engine is not initialized"
