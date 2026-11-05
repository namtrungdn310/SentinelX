"""Application service layer for Detection module."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionEventListResponse,
    DetectionEventResponse,
    DetectionSeverity,
)
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.modules.detection.engine import DetectionEngine
from sentinelx_controller.modules.detection.repository import DetectionRepository

logger = logging.getLogger(__name__)

_global_detection_engine: DetectionEngine | None = None


def get_detection_engine() -> DetectionEngine:
    """Provide singleton instance of DetectionEngine."""
    global _global_detection_engine
    if _global_detection_engine is None:
        _global_detection_engine = DetectionEngine()
    return _global_detection_engine


class DetectionService:
    """Public application service orchestrating Detection evaluation and queries."""

    def __init__(
        self,
        repository: DetectionRepository,
        engine: DetectionEngine,
        realtime_hub: RealtimeHub | None = None,
    ) -> None:
        self._repo = repository
        self._engine = engine
        self._realtime_hub = realtime_hub

    async def evaluate_metrics(
        self,
        node_id: uuid.UUID,
        samples: list[MetricSample],
    ) -> list[DetectionEventContract]:
        """Evaluate incoming metric samples and emit events if anomalies detected."""
        events = self._engine.process_samples(node_id, samples)
        if not events:
            return []

        # 1. Save events to database
        await self._repo.save_events(events)

        # 2. Broadcast via WebSocket
        if self._realtime_hub is not None:
            now = datetime.now(UTC)
            for ev in events:
                msg = RealtimeMessage(
                    event=RealtimeEventType.DETECTION_ALERT.value,
                    data=ev.model_dump(mode="json"),
                    timestamp=now,
                )
                await self._realtime_hub.broadcast(msg)
                logger.warning(
                    "DETECTION ALERT emitted: node=%s detector=%s severity=%s",
                    node_id,
                    ev.detector_name,
                    ev.severity,
                )

        return events

    async def list_events(
        self,
        node_id_str: str | None = None,
        severity: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DetectionEventListResponse:
        """Query list of detection events with pagination and filters."""
        node_uuid: uuid.UUID | None = None
        if node_id_str is not None:
            try:
                node_uuid = uuid.UUID(node_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid node UUID format",
                ) from err

        models = await self._repo.query_events(
            node_id=node_uuid,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

        items = [
            DetectionEventResponse(
                id=str(m.id),
                incident_id=str(m.incident_id) if m.incident_id else None,
                node_id=str(m.node_id),
                detector_name=m.detector_name,
                severity=DetectionSeverity(m.severity),
                attacker_ip=m.attacker_ip,
                confidence_score=m.confidence_score,
                details=m.details,
                detected_at=m.detected_at,
            )
            for m in models
        ]

        return DetectionEventListResponse(total=len(items), items=items)

    async def get_event(self, event_id_str: str) -> DetectionEventResponse:
        """Get single event details by UUID string."""
        try:
            event_uuid = uuid.UUID(event_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid event UUID format",
            ) from err

        model = await self._repo.get_by_id(event_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detection event not found",
            )

        return DetectionEventResponse(
            id=str(model.id),
            incident_id=str(model.incident_id) if model.incident_id else None,
            node_id=str(model.node_id),
            detector_name=model.detector_name,
            severity=DetectionSeverity(model.severity),
            attacker_ip=model.attacker_ip,
            confidence_score=model.confidence_score,
            details=model.details,
            detected_at=model.detected_at,
        )
