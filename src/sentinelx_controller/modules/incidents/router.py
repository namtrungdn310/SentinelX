"""REST API routes for Incidents module."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.incidents import (
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdateRequest,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.detection.repository import DetectionRepository
from sentinelx_controller.modules.detection.router import get_detection_service
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.incidents.service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_incident_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    detection_service: Annotated[DetectionService, Depends(get_detection_service)],
) -> IncidentService:
    """Dependency injection for IncidentService."""
    repo = IncidentRepository(session)
    detection_repo = DetectionRepository(session)
    publisher = CommittedPublisher(background_tasks, realtime_hub)
    return IncidentService(
        repository=repo,
        detection_repo=detection_repo,
        detection_service=detection_service,
        realtime_hub=realtime_hub,
        publisher=publisher,
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List incidents with pagination and filters",
)
async def list_incidents(
    service: Annotated[IncidentService, Depends(get_incident_service)],
    project_id: Annotated[str | None, Query(description="Filter by project UUID")] = None,
    status: Annotated[
        str | None,
        Query(description="Filter by status (DETECTED, MITIGATING, RESOLVED)"),
    ] = None,
    severity: Annotated[str | None, Query(description="Filter by severity")] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="Filter by started_at >= start_time"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter by started_at <= end_time"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> IncidentListResponse:
    """Retrieve list of incidents."""
    return await service.list_incidents(
        project_id_str=project_id,
        status=status,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get incident details with associated detection events",
)
async def get_incident(
    incident_id: str,
    service: Annotated[IncidentService, Depends(get_incident_service)],
) -> IncidentDetailResponse:
    """Retrieve single incident details with events."""
    return await service.get_incident(incident_id)


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update incident status or summary",
)
async def update_incident(
    incident_id: str,
    request: IncidentUpdateRequest,
    service: Annotated[IncidentService, Depends(get_incident_service)],
) -> IncidentResponse:
    """Update incident status (e.g. resolve or mark as false positive)."""
    return await service.update_incident(incident_id, request)
