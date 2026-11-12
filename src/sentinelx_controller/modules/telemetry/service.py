"""Service layer for Telemetry operations."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from sentinelx_common.contracts.realtime import (
    RealtimeEventType,
    RealtimeMessage,
    RealtimeMetricPayload,
)
from sentinelx_common.contracts.telemetry import (
    MetricBatchRequest,
    MetricBatchResponse,
    MetricQueryResponse,
    MetricSample,
)
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.policy.service import PolicyService
from sentinelx_controller.modules.telemetry.repository import TelemetryRepository

logger = logging.getLogger(__name__)


class TelemetryService:
    """Business logic for telemetry ingestion and queries."""

    def __init__(
        self,
        telemetry_repo: TelemetryRepository,
        node_service: NodeService,
        realtime_hub: RealtimeHub | None = None,
        detection_service: DetectionService | None = None,
        incident_service: IncidentService | None = None,
        policy_service: PolicyService | None = None,
        publisher: CommittedPublisher | None = None,
    ) -> None:
        self._telemetry_repo = telemetry_repo
        self._node_service = node_service
        self._realtime_hub = realtime_hub
        self._detection_service = detection_service
        self._incident_service = incident_service
        self._policy_service = policy_service
        self._publisher = publisher

    async def ingest_metrics(self, request: MetricBatchRequest) -> MetricBatchResponse:
        """Validate agent credentials and persist incoming metric batch."""
        try:
            node_uuid = uuid.UUID(request.node_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid node UUID format",
            ) from err

        is_valid = await self._node_service.verify_agent(
            node_id_str=request.node_id,
            agent_id_str=request.agent_id,
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent credentials invalid or not enrolled for this node",
            )

        now = datetime.now(UTC)
        count = await self._telemetry_repo.save_batch(
            node_id=node_uuid,
            received_at=now,
            samples=request.samples,
        )

        if self._realtime_hub is not None:
            metric_payload = RealtimeMetricPayload(
                node_id=request.node_id,
                samples=request.samples,
                received_at=now,
            )
            message = RealtimeMessage(
                event=RealtimeEventType.METRIC_UPDATE.value,
                data=metric_payload.model_dump(mode="json"),
                timestamp=now,
            )
            if self._publisher is not None:
                self._publisher.enqueue(message)
            else:
                await self._realtime_hub.broadcast(message)

        if self._detection_service is not None:
            # A detection/state write failure rolls back metrics too; Agent can retry safely.
            events = await self._detection_service.evaluate_metrics(
                node_id=node_uuid,
                samples=request.samples,
            )
            if events and self._incident_service is not None:
                node_resp = await self._node_service.get_node(request.node_id)
                project_uuid = uuid.UUID(node_resp.project_id)
                correlated = await self._incident_service.correlate_events(
                    project_id=project_uuid,
                    node_id=node_uuid,
                    events=events,
                )
                if self._policy_service is not None:
                    for _inc, ev_list in correlated:
                        for ev in ev_list:
                            await self._policy_service.evaluate_event(
                                project_id=project_uuid,
                                event=ev,
                            )

        return MetricBatchResponse(
            status="ok",
            processed_count=count,
            received_at=now,
        )

    async def query_metrics(
        self,
        node_id_str: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> MetricQueryResponse:
        """Query historical time-series metrics for a node."""
        try:
            node_uuid = uuid.UUID(node_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid node UUID format",
            ) from err

        # Verify node exists via public NodeService
        await self._node_service.get_node(node_id_str)

        records = await self._telemetry_repo.query_by_node(
            node_id=node_uuid,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        samples = [
            MetricSample(
                observed_at=ensure_utc(r.observed_at),
                cpu_percent=r.cpu_usage_pct,
                memory_percent=r.memory_usage_pct,
                disk_percent=r.disk_usage_pct,
                network_rx_bytes=r.network_rx_bytes,
                network_tx_bytes=r.network_tx_bytes,
            )
            for r in records
        ]

        return MetricQueryResponse(
            node_id=node_id_str,
            count=len(samples),
            samples=samples,
        )
