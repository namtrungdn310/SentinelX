"""WebSocket realtime endpoint and connection handling."""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub

logger = logging.getLogger("sentinelx_controller.api.v1.realtime")

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_realtime_endpoint(
    websocket: WebSocket,
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> None:
    """Bi-directional WebSocket connection for realtime telemetry & heartbeats."""
    await hub.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg_dict = json.loads(raw_text)
                event_name = msg_dict.get("event")
            except Exception:
                event_name = raw_text.strip().lower()

            if event_name == RealtimeEventType.PING.value or event_name == "ping":
                pong = RealtimeMessage(
                    event=RealtimeEventType.PONG.value,
                    data={},
                    timestamp=datetime.now(UTC),
                )
                await websocket.send_text(pong.model_dump_json())
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception as err:
        logger.warning("WebSocket client encountered exception: %s", err)
        await hub.disconnect(websocket)


@router.get("/ws/status", summary="Get realtime hub connection metrics")
async def get_realtime_status(
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> dict[str, Any]:
    """Return current connection count from RealtimeHub."""
    return {
        "status": "online",
        "active_connections": hub.connection_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }
