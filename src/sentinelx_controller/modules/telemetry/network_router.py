"""M2 and M4 REST endpoints, under the existing telemetry module."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.network import (
    NetworkBatchRequest,
    NetworkBatchResponse,
    NetworkQueryResponse,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.detection.router import get_detection_service
from sentinelx_controller.modules.detection.service import DetectionService
from sentinelx_controller.modules.incidents.router import get_incident_service
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.router import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.policy.router import get_policy_service
from sentinelx_controller.modules.policy.service import PolicyService
from sentinelx_controller.modules.telemetry.network_repository import NetworkRepository
from sentinelx_controller.modules.telemetry.network_service import NetworkTelemetryService

router = APIRouter(prefix="/telemetry", tags=["network telemetry"])


def get_network_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    nodes: Annotated[NodeService, Depends(get_node_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    detection_service: Annotated[DetectionService, Depends(get_detection_service)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
    policy_service: Annotated[PolicyService, Depends(get_policy_service)],
) -> NetworkTelemetryService:
    return NetworkTelemetryService(
        repository=NetworkRepository(session),
        nodes=nodes,
        hub=hub,
        publisher=CommittedPublisher(background_tasks, hub),
        detection_service=detection_service,
        incident_service=incident_service,
        policy_service=policy_service,
    )


@router.post("/network-features", response_model=NetworkBatchResponse)
async def ingest_network(
    request: NetworkBatchRequest,
    service: Annotated[NetworkTelemetryService, Depends(get_network_service)],
) -> NetworkBatchResponse:
    return await service.ingest(request)


@router.get("/nodes/{node_id}/network-features", response_model=NetworkQueryResponse)
async def query_network(
    node_id: UUID,
    service: Annotated[NetworkTelemetryService, Depends(get_network_service)],
    start_time: Annotated[AwareDatetime | None, Query()] = None,
    end_time: Annotated[AwareDatetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NetworkQueryResponse:
    return await service.query(node_id, start_time, end_time, limit)
