"""API router exposing per-project Load Balancer configuration and runtime proxy endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from sentinelx_common.contracts.projects import (
    LBAlgorithmUpdateRequest,
    LBBackendStateUpdateRequest,
    ProjectLBConfigContract,
    ProjectLBStatusResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from sentinelx_controller.modules.nodes.dependencies import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.lb_coordinator import ProjectLBCoordinator
from sentinelx_controller.modules.projects.router import get_project_service
from sentinelx_controller.modules.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["load-balancer"])


def get_lb_coordinator(
    request: Request,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    node_service: Annotated[NodeService, Depends(get_node_service)],
) -> ProjectLBCoordinator:
    return ProjectLBCoordinator(
        project_service=project_service,
        node_service=node_service,
        lb_admin_token=request.app.state.settings.lb_admin_token,
        default_lb_url=request.app.state.settings.default_lb_url,
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project metadata and optional Load Balancer configuration",
)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectResponse:
    updated = await project_service.update_project(project_id, request)
    if updated.load_balancer.enabled:
        await coordinator.sync_project_lb(project_id)
    return updated


@router.get(
    "/{project_id}/load-balancer",
    response_model=ProjectLBStatusResponse,
    summary="Get Load Balancer pool runtime status for a project",
)
async def get_project_lb_status(
    project_id: str,
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectLBStatusResponse:
    return await coordinator.get_status(project_id)


@router.put(
    "/{project_id}/load-balancer",
    response_model=ProjectLBStatusResponse,
    summary="Enable/configure Load Balancer for a project and sync pool",
)
async def update_project_lb_config(
    project_id: str,
    config: ProjectLBConfigContract,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectLBStatusResponse:
    await project_service.update_lb_config(project_id, config)
    return await coordinator.sync_project_lb(project_id)


@router.patch(
    "/{project_id}/load-balancer/algorithm",
    response_model=ProjectLBStatusResponse,
    summary="Switch Load Balancer algorithm for a project",
)
async def switch_project_lb_algorithm(
    project_id: str,
    request: LBAlgorithmUpdateRequest,
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectLBStatusResponse:
    return await coordinator.switch_algorithm(project_id, request.algorithm)


@router.post(
    "/{project_id}/load-balancer/sync",
    response_model=ProjectLBStatusResponse,
    summary="Push project backend pool and LB config to sentinelx_lb",
)
async def sync_project_lb(
    project_id: str,
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectLBStatusResponse:
    return await coordinator.sync_project_lb(project_id)


@router.post(
    "/{project_id}/load-balancer/backends/{node_id}/state",
    response_model=ProjectLBStatusResponse,
    summary="Manually enable or drain/disable an upstream backend node in sentinelx_lb",
)
async def set_project_lb_backend_state(
    project_id: str,
    node_id: str,
    request: LBBackendStateUpdateRequest,
    coordinator: Annotated[ProjectLBCoordinator, Depends(get_lb_coordinator)],
) -> ProjectLBStatusResponse:
    return await coordinator.set_backend_state(project_id, node_id, request)
