"""API router for telemetry endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.telemetry import (
    MetricBatchRequest,
    MetricBatchResponse,
    MetricQueryResponse,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.router import get_defense_service
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.detection.router import get_detection_service
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.router import get_incident_service
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.router import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.policy.router import get_policy_service
from sentinelx_controller.modules.policy.service import PolicyService
from sentinelx_controller.modules.telemetry.repository import TelemetryRepository
from sentinelx_controller.modules.telemetry.service import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def get_telemetry_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    node_service: Annotated[NodeService, Depends(get_node_service)],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    detection_service: Annotated[DetectionService, Depends(get_detection_service)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
    policy_service: Annotated[PolicyService, Depends(get_policy_service)],
    defense_service: Annotated[DefenseService, Depends(get_defense_service)],
) -> TelemetryService:
    """Dependency providing TelemetryService."""
    telemetry_repo = TelemetryRepository(session)
    return TelemetryService(
        telemetry_repo=telemetry_repo,
        node_service=node_service,
        realtime_hub=realtime_hub,
        detection_service=detection_service,
        incident_service=incident_service,
        policy_service=policy_service,
        publisher=CommittedPublisher(background_tasks, realtime_hub),
        defense_service=defense_service,
    )


@router.post(
    "/metrics",
    response_model=MetricBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of metric samples from an Agent",
)
async def ingest_metrics(
    request: MetricBatchRequest,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
) -> MetricBatchResponse:
    return await service.ingest_metrics(request)


@router.get(
    "/nodes/{node_id}/metrics",
    response_model=MetricQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query historical metric samples for a node",
)
async def query_metrics(
    node_id: str,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
    start_time: Annotated[
        datetime | None,
        Query(description="Filter samples starting at UTC"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter samples ending at UTC"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of samples to return"),
    ] = 100,
) -> MetricQueryResponse:
    return await service.query_metrics(
        node_id_str=node_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
