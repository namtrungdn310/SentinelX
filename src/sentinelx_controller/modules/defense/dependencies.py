"""Public DefenseService composition without a dependency on recovery internals."""

from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.incidents.router import get_incident_service
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.dependencies import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.policy.router import get_policy_service
from sentinelx_controller.modules.policy.service import PolicyService


def get_defense_core(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    nodes: Annotated[NodeService, Depends(get_node_service)],
    incidents: Annotated[IncidentService, Depends(get_incident_service)],
    policy: Annotated[PolicyService, Depends(get_policy_service)],
) -> DefenseService:
    return DefenseService(
        DefenseRepository(session),
        hub,
        CommittedPublisher(background_tasks, hub),
        incident_service=incidents,
        node_service=nodes,
        policy_service=policy,
        safety=request.app.state.settings.safety,
    )
