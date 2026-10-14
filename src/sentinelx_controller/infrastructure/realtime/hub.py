"""Realtime WebSocket connection hub and event broadcaster."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from sentinelx_common.contracts.realtime import RealtimeMessage

logger = logging.getLogger("sentinelx_controller.realtime.hub")


class RealtimeHub:
    """Manages active WebSocket connections and bounded broadcast fan-out."""

    def __init__(self, send_timeout_seconds: float = 2.0) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._send_timeout_seconds = send_timeout_seconds

    @property
    def connection_count(self) -> int:
        """Current number of active WebSocket connections."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register an active WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(
            "WebSocket client connected. Active connections: %d",
            len(self._connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a disconnected WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(
            "WebSocket client disconnected. Active connections: %d",
            len(self._connections),
        )

    async def broadcast(self, message: RealtimeMessage) -> int:
        """Broadcast a realtime message to all connected clients concurrently.

        Uses bounded timeout per connection. Dropped or broken sockets are pruned.
        Returns the number of clients that successfully received the message.
        """
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return 0

        payload_str = message.model_dump_json()

        async def _safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(
                    ws.send_text(payload_str),
                    timeout=self._send_timeout_seconds,
                )
                return None
            except (WebSocketDisconnect, TimeoutError, RuntimeError, OSError) as err:
                logger.warning("Failed to send realtime event to client: %s. Pruning...", err)
                return ws

        # Bounded concurrent fan-out
        results = await asyncio.gather(*[_safe_send(ws) for ws in targets], return_exceptions=True)

        failed_sockets: list[WebSocket] = []
        success_count = 0
        for idx, res in enumerate(results):
            if res is None:
                success_count += 1
            elif isinstance(res, WebSocket):
                failed_sockets.append(res)
            elif isinstance(res, Exception):
                logger.warning("Unexpected exception in broadcast: %s", res)
                failed_sockets.append(targets[idx])

        # Prune failed or timed out sockets
        if failed_sockets:
            async with self._lock:
                for ws in failed_sockets:
                    self._connections.discard(ws)
            logger.info("Pruned %d dead WebSocket connections.", len(failed_sockets))

        return success_count

    async def broadcast_event(self, event: str, data: dict[str, Any]) -> int:
        """Convenience helper to broadcast event by name and payload dictionary."""
        msg = RealtimeMessage(
            event=event,
            data=data,
            timestamp=datetime.now(UTC),
        )
        return await self.broadcast(msg)
