"""Public NodeService factory without command/recovery routing dependencies."""

from typing import Annotated

from fastapi import BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.nodes.repository import AgentEnrollmentRepository, NodeRepository
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.router import get_project_service
from sentinelx_controller.modules.projects.service import ProjectService


def get_node_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> NodeService:
    return NodeService(
        NodeRepository(session),
        project_service,
        AgentEnrollmentRepository(session),
        realtime_hub=realtime_hub,
        publisher=CommittedPublisher(background_tasks, realtime_hub),
    )
