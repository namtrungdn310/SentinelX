"""Application service layer for Policy module."""

import ipaddress
import logging
import uuid

from fastapi import HTTPException, status

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.policy import (
    DefensePolicyCreateRequest,
    DefensePolicyListResponse,
    DefensePolicyResponse,
    DefensePolicyUpdateRequest,
    IPWhitelistCreateRequest,
    IPWhitelistListResponse,
    IPWhitelistResponse,
    PolicyActionType,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
)
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.models import DefensePolicyModel, IPWhitelistModel
from sentinelx_controller.modules.policy.repository import PolicyRepository

logger = logging.getLogger(__name__)

_global_policy_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Singleton instance of PolicyEngine."""
    global _global_policy_engine
    if _global_policy_engine is None:
        _global_policy_engine = PolicyEngine()
    return _global_policy_engine


class PolicyService:
    """Service managing defense policies, IP whitelists, and evaluating safety."""

    def __init__(
        self,
        repository: PolicyRepository,
        engine: PolicyEngine,
    ) -> None:
        self._repo = repository
        self._engine = engine

    # ─── DEFENSE POLICIES CRUD ───

    async def create_policy(
        self,
        project_id_str: str,
        request: DefensePolicyCreateRequest,
    ) -> DefensePolicyResponse:
        """Tạo chính sách phòng thủ mới cho project."""
        try:
            project_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        model = DefensePolicyModel(
            project_id=project_uuid,
            name=request.name,
            event_type=request.event_type,
            action_type=request.action_type.value,
            target_params=request.target_params,
            is_auto_execute=request.is_auto_execute,
            cooldown_seconds=request.cooldown_seconds,
            block_duration_seconds=request.block_duration_seconds,
            enabled=request.enabled,
        )
        saved = await self._repo.create_policy(model)
        return self._to_policy_response(saved)

    async def get_policy(self, policy_id_str: str) -> DefensePolicyResponse:
        """Lấy chi tiết một policy theo UUID."""
        try:
            policy_uuid = uuid.UUID(policy_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid policy UUID format",
            ) from err

        model = await self._repo.get_policy_by_id(policy_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense policy not found",
            )
        return self._to_policy_response(model)

    async def list_policies(
        self,
        project_id_str: str | None = None,
    ) -> DefensePolicyListResponse:
        """Liệt kê danh sách policies."""
        project_uuid: uuid.UUID | None = None
        if project_id_str is not None:
            try:
                project_uuid = uuid.UUID(project_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid project UUID format",
                ) from err

        models = await self._repo.list_policies(project_id=project_uuid)
        items = [self._to_policy_response(m) for m in models]
        return DefensePolicyListResponse(total=len(items), items=items)

    async def update_policy(
        self,
        policy_id_str: str,
        request: DefensePolicyUpdateRequest,
    ) -> DefensePolicyResponse:
        """Cập nhật chính sách phòng thủ."""
        try:
            policy_uuid = uuid.UUID(policy_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid policy UUID format",
            ) from err

        model = await self._repo.get_policy_by_id(policy_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense policy not found",
            )

        if request.name is not None:
            model.name = request.name
        if request.action_type is not None:
            model.action_type = request.action_type.value
        if request.target_params is not None:
            model.target_params = request.target_params
        if request.is_auto_execute is not None:
            model.is_auto_execute = request.is_auto_execute
        if request.cooldown_seconds is not None:
            model.cooldown_seconds = request.cooldown_seconds
        if request.block_duration_seconds is not None:
            model.block_duration_seconds = request.block_duration_seconds
        if request.enabled is not None:
            model.enabled = request.enabled

        saved = await self._repo.save_policy(model)
        return self._to_policy_response(saved)

    async def delete_policy(self, policy_id_str: str) -> None:
        """Xóa chính sách phòng thủ."""
        try:
            policy_uuid = uuid.UUID(policy_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid policy UUID format",
            ) from err

        model = await self._repo.get_policy_by_id(policy_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense policy not found",
            )
        await self._repo.delete_policy(model)

    # ─── IP WHITELIST CRUD ───

    async def create_whitelist(
        self,
        project_id_str: str,
        request: IPWhitelistCreateRequest,
    ) -> IPWhitelistResponse:
        """Thêm dải IP an toàn vào whitelist."""
        try:
            project_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        # Validate CIDR/IP syntax
        try:
            ipaddress.ip_network(request.ip_or_cidr, strict=False)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid IP or CIDR network format: {request.ip_or_cidr}",
            ) from err

        model = IPWhitelistModel(
            project_id=project_uuid,
            ip_or_cidr=request.ip_or_cidr,
            description=request.description,
        )
        saved = await self._repo.create_whitelist(model)
        return self._to_whitelist_response(saved)

    async def list_whitelist(self, project_id_str: str) -> IPWhitelistListResponse:
        """Liệt kê toàn bộ whitelist của project."""
        try:
            project_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        models = await self._repo.list_whitelist(project_uuid)
        items = [self._to_whitelist_response(m) for m in models]
        return IPWhitelistListResponse(total=len(items), items=items)

    async def delete_whitelist(self, whitelist_id_str: str) -> None:
        """Xóa mục whitelist."""
        try:
            wl_uuid = uuid.UUID(whitelist_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid whitelist UUID format",
            ) from err

        model = await self._repo.get_whitelist_by_id(wl_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Whitelist entry not found",
            )
        await self._repo.delete_whitelist(model)

    # ─── EVALUATION ───

    async def evaluate_event(
        self,
        project_id: uuid.UUID,
        event: DetectionEventContract,
        controller_ip: str | None = None,
    ) -> PolicyEvaluationResult:
        """Đánh giá sự kiện và kiểm tra quy tắc phòng thủ."""
        policies = await self._repo.list_policies(project_id=project_id)
        whitelists = await self._repo.list_whitelist(project_id=project_id)
        return self._engine.evaluate(
            event=event,
            policies=policies,
            whitelists=whitelists,
            controller_ip=controller_ip,
        )

    async def dry_run_evaluation(
        self,
        project_id_str: str,
        request: PolicyEvaluationRequest,
    ) -> PolicyEvaluationResult:
        """Thử nghiệm đánh giá sự kiện (dry-run)."""
        try:
            project_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        return await self.evaluate_event(
            project_id=project_uuid,
            event=request.event,
        )

    def _to_policy_response(self, model: DefensePolicyModel) -> DefensePolicyResponse:
        return DefensePolicyResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            name=model.name,
            event_type=model.event_type,
            action_type=PolicyActionType(model.action_type),
            target_params=model.target_params,
            is_auto_execute=model.is_auto_execute,
            cooldown_seconds=model.cooldown_seconds,
            block_duration_seconds=model.block_duration_seconds,
            enabled=model.enabled,
        )

    def _to_whitelist_response(self, model: IPWhitelistModel) -> IPWhitelistResponse:
        return IPWhitelistResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            ip_or_cidr=model.ip_or_cidr,
            description=model.description,
            created_at=model.created_at,
        )
