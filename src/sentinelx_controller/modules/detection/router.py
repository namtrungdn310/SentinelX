"""API router for detection events."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.detection import (
    DetectionEventListResponse,
    DetectionEventResponse,
    DetectionSeverity,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.detection.engine import DetectionEngine
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.detection.service import (
    DetectionService,
    get_detection_engine,
)

router = APIRouter(prefix="/detection-events", tags=["detection"])


def get_detection_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    engine: Annotated[DetectionEngine, Depends(get_detection_engine)],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DetectionService:
    """Dependency injection for DetectionService."""
    repo = DetectionRepository(session)
    return DetectionService(
        repository=repo,
        engine=engine,
        realtime_hub=realtime_hub,
        publisher=CommittedPublisher(background_tasks, realtime_hub),
    )


@router.get(
    "",
    response_model=DetectionEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query detection events with filters",
)
async def list_detection_events(
    service: Annotated[DetectionService, Depends(get_detection_service)],
    node_id: Annotated[str | None, Query(description="Filter by node ID")] = None,
    severity: Annotated[
        DetectionSeverity | None, Query(description="Filter by severity (LOW, HIGH, etc)")
    ] = None,
    start_time: Annotated[AwareDatetime | None, Query(description="Start time (UTC)")] = None,
    end_time: Annotated[AwareDatetime | None, Query(description="End time (UTC)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DetectionEventListResponse:
    return await service.list_events(
        node_id_str=node_id,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{event_id}",
    response_model=DetectionEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single detection event by ID",
)
async def get_detection_event(
    event_id: str,
    service: Annotated[DetectionService, Depends(get_detection_service)],
) -> DetectionEventResponse:
    return await service.get_event(event_id)
