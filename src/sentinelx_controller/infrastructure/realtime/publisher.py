"""Queue realtime delivery after the function-scoped DB transaction has committed."""

import logging

from fastapi import BackgroundTasks

from sentinelx_common.contracts.realtime import RealtimeMessage
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub

logger = logging.getLogger(__name__)


class CommittedPublisher:
    """Failed dependency commits discard response tasks; REST history is durable truth.

    This is best-effort realtime delivery, not a persistent outbox.
    """

    def __init__(self, tasks: BackgroundTasks, hub: RealtimeHub) -> None:
        self._tasks, self._hub = tasks, hub

    def enqueue(self, message: RealtimeMessage) -> None:
        self._tasks.add_task(self._send, message)

    async def _send(self, message: RealtimeMessage) -> None:
        try:
            await self._hub.broadcast(message)
        except Exception:
            logger.exception("Realtime delivery failed after commit; query REST history to recover")
