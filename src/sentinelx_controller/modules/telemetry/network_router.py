"""M2 REST endpoints, under the existing telemetry module."""

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
from sentinelx_controller.modules.nodes.router import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.telemetry.network_repository import NetworkRepository
from sentinelx_controller.modules.telemetry.network_service import NetworkTelemetryService

router = APIRouter(prefix="/telemetry", tags=["network telemetry"])


def get_network_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    nodes: Annotated[NodeService, Depends(get_node_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> NetworkTelemetryService:
    return NetworkTelemetryService(
        NetworkRepository(session), nodes, hub, CommittedPublisher(background_tasks, hub),
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
