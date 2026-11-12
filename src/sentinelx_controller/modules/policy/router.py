"""REST API routes for Policy and IP Whitelist."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.policy import (
    DefensePolicyCreateRequest,
    DefensePolicyListResponse,
    DefensePolicyResponse,
    DefensePolicyUpdateRequest,
    IPWhitelistCreateRequest,
    IPWhitelistListResponse,
    IPWhitelistResponse,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.repository import PolicyRepository
from sentinelx_controller.modules.policy.service import (
    PolicyService,
    get_policy_engine,
)

router = APIRouter(tags=["policy"])


def get_policy_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
) -> PolicyService:
    """Dependency injection for PolicyService."""
    repo = PolicyRepository(session)
    return PolicyService(repository=repo, engine=engine)


# ─── DEFENSE POLICIES ───


@router.post(
    "/projects/{project_id}/defense-policies",
    response_model=DefensePolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new defense policy for a project",
)
async def create_policy(
    project_id: str,
    request: DefensePolicyCreateRequest,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> DefensePolicyResponse:
    """Create a defense policy."""
    return await service.create_policy(project_id, request)


@router.get(
    "/defense-policies",
    response_model=DefensePolicyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List defense policies with optional project filter",
)
async def list_policies(
    service: Annotated[PolicyService, Depends(get_policy_service)],
    project_id: Annotated[str | None, Query(description="Filter by project UUID")] = None,
) -> DefensePolicyListResponse:
    """List policies."""
    return await service.list_policies(project_id_str=project_id)


@router.get(
    "/defense-policies/{policy_id}",
    response_model=DefensePolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single defense policy details",
)
async def get_policy(
    policy_id: str,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> DefensePolicyResponse:
    """Get policy by ID."""
    return await service.get_policy(policy_id)


@router.patch(
    "/defense-policies/{policy_id}",
    response_model=DefensePolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a defense policy",
)
async def update_policy(
    policy_id: str,
    request: DefensePolicyUpdateRequest,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> DefensePolicyResponse:
    """Update policy fields."""
    return await service.update_policy(policy_id, request)


@router.delete(
    "/defense-policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a defense policy",
)
async def delete_policy(
    policy_id: str,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> None:
    """Delete policy."""
    await service.delete_policy(policy_id)


# ─── IP WHITELIST ───


@router.post(
    "/projects/{project_id}/ip-whitelist",
    response_model=IPWhitelistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an IP or CIDR to project whitelist",
)
async def create_whitelist(
    project_id: str,
    request: IPWhitelistCreateRequest,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> IPWhitelistResponse:
    """Add safe IP/CIDR."""
    return await service.create_whitelist(project_id, request)


@router.get(
    "/projects/{project_id}/ip-whitelist",
    response_model=IPWhitelistListResponse,
    status_code=status.HTTP_200_OK,
    summary="List IP whitelist for a project",
)
async def list_whitelist(
    project_id: str,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> IPWhitelistListResponse:
    """List whitelist entries."""
    return await service.list_whitelist(project_id)


@router.delete(
    "/ip-whitelist/{whitelist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an IP whitelist entry",
)
async def delete_whitelist(
    whitelist_id: str,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> None:
    """Delete whitelist entry."""
    await service.delete_whitelist(whitelist_id)


# ─── DRY RUN EVALUATION ───


@router.post(
    "/projects/{project_id}/policy/evaluate",
    response_model=PolicyEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Dry-run evaluate a detection event against project policies",
)
async def evaluate_policy_dry_run(
    project_id: str,
    request: PolicyEvaluationRequest,
    service: Annotated[PolicyService, Depends(get_policy_service)],
) -> PolicyEvaluationResult:
    """Dry run evaluate."""
    return await service.dry_run_evaluation(project_id, request)
