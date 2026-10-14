"""Unit tests for RealtimeHub."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from sentinelx_common.contracts.realtime import RealtimeMessage
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub


@pytest.mark.asyncio
async def test_realtime_hub_connect_and_disconnect() -> None:
    """Test registering and unregistering websocket connections."""
    hub = RealtimeHub()
    assert hub.connection_count == 0

    mock_ws = AsyncMock(spec=WebSocket)
    await hub.connect(mock_ws)
    assert hub.connection_count == 1
    mock_ws.accept.assert_awaited_once()

    await hub.disconnect(mock_ws)
    assert hub.connection_count == 0


@pytest.mark.asyncio
async def test_realtime_hub_broadcast_success() -> None:
    """Test broadcasting message to multiple active clients."""
    hub = RealtimeHub()
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)

    await hub.connect(ws1)
    await hub.connect(ws2)
    assert hub.connection_count == 2

    msg = RealtimeMessage(
        event="test_event",
        data={"key": "value"},
        timestamp=datetime.now(UTC),
    )

    delivered = await hub.broadcast(msg)
    assert delivered == 2
    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_realtime_hub_broadcast_prunes_dead_connection() -> None:
    """Test broken or disconnected sockets are safely dropped during broadcast."""
    hub = RealtimeHub()
    good_ws = AsyncMock(spec=WebSocket)
    dead_ws = AsyncMock(spec=WebSocket)
    dead_ws.send_text.side_effect = WebSocketDisconnect(code=1000)

    await hub.connect(good_ws)
    await hub.connect(dead_ws)
    assert hub.connection_count == 2

    msg = RealtimeMessage(
        event="test_event",
        data={},
        timestamp=datetime.now(UTC),
    )

    delivered = await hub.broadcast(msg)
    assert delivered == 1
    assert hub.connection_count == 1
    good_ws.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_realtime_hub_broadcast_timeout_prunes_slow_connection() -> None:
    """Test slow/hanging client is pruned by bounded fan-out timeout."""
    hub = RealtimeHub(send_timeout_seconds=0.02)
    slow_ws = AsyncMock(spec=WebSocket)

    async def hang(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(0.5)

    slow_ws.send_text.side_effect = hang

    await hub.connect(slow_ws)
    assert hub.connection_count == 1

    msg = RealtimeMessage(
        event="test_event",
        data={},
        timestamp=datetime.now(UTC),
    )

    delivered = await hub.broadcast(msg)
    assert delivered == 0
    assert hub.connection_count == 0
