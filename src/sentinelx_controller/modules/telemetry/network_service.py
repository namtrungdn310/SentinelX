"""Network telemetry boundary: validate Agent through the public Node service."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException

from sentinelx_common.contracts.network import (
    NetworkBatchRequest,
    NetworkBatchResponse,
    NetworkQueryResponse,
)
from sentinelx_common.contracts.realtime import RealtimeMessage
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.telemetry.network_repository import NetworkRepository


class NetworkTelemetryService:
    def __init__(
        self,
        repository: NetworkRepository,
        nodes: NodeService,
        hub: RealtimeHub,
        publisher: CommittedPublisher | None = None,
    ) -> None:
        self._repository, self._nodes, self._hub = repository, nodes, hub
        self._publisher = publisher

    async def ingest(self, request: NetworkBatchRequest) -> NetworkBatchResponse:
        if not await self._nodes.verify_agent(str(request.node_id), str(request.agent_id)):
            raise HTTPException(403, "Agent credentials invalid or not enrolled for this node")
        now = datetime.now(UTC)
        saved = await self._repository.save(request.node_id, request.windows, now)
        if saved:
            message = RealtimeMessage(
                event="network_feature_update",
                timestamp=now,
                data={
                    "node_id": str(request.node_id),
                    "received_at": now.isoformat(),
                    "windows": [w.model_dump(mode="json") for w in saved],
                },
            )
            if self._publisher is not None:
                self._publisher.enqueue(message)
            else:
                await self._hub.broadcast(message)
        return NetworkBatchResponse(processed_count=len(saved), received_at=now)

    async def query(
        self, node_id: UUID, start_time: datetime | None, end_time: datetime | None, limit: int
    ) -> NetworkQueryResponse:
        if start_time is not None and end_time is not None and start_time > end_time:
            raise HTTPException(422, "start_time must not be after end_time")
        await self._nodes.get_node(str(node_id))
        windows = await self._repository.query(node_id, start_time, end_time, limit)
        return NetworkQueryResponse(node_id=node_id, count=len(windows), windows=windows)
