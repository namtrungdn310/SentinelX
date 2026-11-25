"""Application service layer for Policy module."""

import ipaddress
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from sentinelx_common.contracts.command_parameters import SUPPORTED_ACTIONS
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
    PolicyDecisionResponse,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
)
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.models import (
    DefensePolicyModel,
    IPWhitelistModel,
    PolicyDecisionModel,
)
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
        protected_cidrs: list[str] | None = None,
    ) -> None:
        self._repo = repository
        self._engine = engine
        self._protected_cidrs = protected_cidrs or []

    # ─── DEFENSE POLICIES CRUD ───

    async def list_decisions(
        self, node_id: str | None, limit: int, offset: int
    ) -> list[PolicyDecisionResponse]:
        try:
            node = uuid.UUID(node_id) if node_id else None
        except ValueError as error:
            raise HTTPException(422, "Invalid node UUID") from error
        rows = await self._repo.decisions(node, limit, offset)
        return [
            PolicyDecisionResponse(
                id=str(row.id),
                node_id=str(row.node_id),
                event_id=row.event_id,
                created_at=row.created_at,
                snapshot=row.snapshot,
            )
            for row in rows
        ]

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

        self._validate_action(request.action_type.value, request.block_duration_seconds)
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
            priority=request.priority,
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
            self._validate_action(
                request.action_type.value,
                request.block_duration_seconds
                if request.block_duration_seconds is not None
                else model.block_duration_seconds,
            )
            model.action_type = request.action_type.value
        if request.target_params is not None:
            model.target_params = request.target_params
        if request.is_auto_execute is not None:
            model.is_auto_execute = request.is_auto_execute
        if request.cooldown_seconds is not None:
            model.cooldown_seconds = request.cooldown_seconds
        if request.block_duration_seconds is not None:
            self._validate_action(model.action_type, request.block_duration_seconds)
            model.block_duration_seconds = request.block_duration_seconds
        if request.enabled is not None:
            model.enabled = request.enabled
        if request.priority is not None:
            model.priority = request.priority

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

        # Validate and canonicalize CIDR/IP syntax
        try:
            network = ipaddress.ip_network(request.ip_or_cidr.strip(), strict=False)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid IP or CIDR network format: {request.ip_or_cidr}",
            ) from err

        canonical_cidr = str(network)
        existing_entries = await self._repo.list_whitelist(project_uuid)
        for entry in existing_entries:
            try:
                if str(ipaddress.ip_network(entry.ip_or_cidr, strict=False)) == canonical_cidr:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"IP/CIDR '{canonical_cidr}' already exists in project whitelist",
                    )
            except ValueError:
                if entry.ip_or_cidr.strip() == canonical_cidr:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"IP/CIDR '{canonical_cidr}' already exists in project whitelist",
                    ) from None

        model = IPWhitelistModel(
            project_id=project_uuid,
            ip_or_cidr=canonical_cidr,
            description=request.description.strip() or None if request.description else None,
        )
        saved = await self._repo.create_whitelist(model)
        return self._to_whitelist_response(saved)

    async def seed_default_policies(self, project_id_str: str) -> DefensePolicyListResponse:
        """Idempotently ensure core system defense policies exist for a project."""
        try:
            project_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        existing = await self._repo.list_policies(project_id=project_uuid)
        existing_types = {p.event_type for p in existing}

        default_specs: list[tuple[str, str, PolicyActionType, int, int, int, bool]] = [
            (
                "Chống SYN Flood",
                "syn_flood_detector",
                PolicyActionType.BLOCK_IP_NFTABLES,
                60,
                300,
                10,
                True,
            ),
            (
                "Chống dò quét cổng (Port Scan)",
                "port_scan_detector",
                PolicyActionType.BLOCK_IP_NFTABLES,
                120,
                600,
                20,
                True,
            ),
            (
                "Chống UDP Flood / Đột biến băng thông",
                "traffic_spike_detector",
                PolicyActionType.BLOCK_IP_NFTABLES,
                60,
                300,
                30,
                True,
            ),
            (
                "Quá tải CPU kéo dài",
                "cpu_threshold_detector",
                PolicyActionType.ALERT_ONLY,
                300,
                0,
                40,
                True,
            ),
            (
                "Cạn kiệt RAM hệ thống",
                "memory_exhaustion_detector",
                PolicyActionType.CLEAR_OS_CACHE,
                180,
                0,
                50,
                True,
            ),
            (
                "Tràn dung lượng ổ đĩa",
                "disk_saturation_detector",
                PolicyActionType.ALERT_ONLY,
                300,
                0,
                60,
                True,
            ),
        ]

        for name, ev_type, action_type, cooldown, block_sec, priority, is_auto in default_specs:
            if ev_type in existing_types:
                continue
            await self._repo.create_policy(
                DefensePolicyModel(
                    project_id=project_uuid,
                    name=name,
                    event_type=ev_type,
                    action_type=action_type.value,
                    target_params={},
                    is_auto_execute=is_auto,
                    cooldown_seconds=cooldown,
                    block_duration_seconds=block_sec,
                    enabled=True,
                    priority=priority,
                )
            )

        updated = await self._repo.list_policies(project_id=project_uuid)
        return DefensePolicyListResponse(
            total=len(updated),
            items=[self._to_policy_response(m) for m in updated],
        )

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
        *,
        dry_run: bool = False,
    ) -> PolicyEvaluationResult:
        """Đánh giá sự kiện và kiểm tra quy tắc phòng thủ."""
        policies = await self._repo.list_policies(project_id=project_id)
        whitelists = await self._repo.list_whitelist(project_id=project_id)
        result = self._engine.evaluate(
            event=event,
            policies=policies,
            whitelists=whitelists,
            controller_ip=controller_ip,
            protected_cidrs=self._protected_cidrs,
        )
        if result.policy_id is not None:
            state = await self._repo.cooldown(
                uuid.UUID(event.node_id),
                result.policy_id,
                result.target or event.node_id,
                lock=not dry_run,
            )
            result = self._engine.evaluate(
                event,
                policies,
                whitelists,
                controller_ip,
                last_authorized_at=state.last_authorized_at if state else None,
                protected_cidrs=self._protected_cidrs,
            )
            if state is not None and not dry_run and result.authorized and result.is_auto_execute:
                state.last_authorized_at = datetime.now(UTC)
        if not dry_run:
            await self._repo.audit(
                PolicyDecisionModel(
                    node_id=uuid.UUID(event.node_id),
                    event_id=event.id,
                    snapshot={
                        "event": event.model_dump(mode="json"),
                        "result": result.model_dump(mode="json"),
                        "policies": [
                            self._to_policy_response(p).model_dump(mode="json") for p in policies
                        ],
                        "protected_cidrs": self._protected_cidrs,
                        "whitelists": [w.ip_or_cidr for w in whitelists],
                    },
                )
            )
        return result

    @staticmethod
    def _validate_action(action: str, duration: int) -> None:
        if action not in SUPPORTED_ACTIONS or action == "UNBLOCK_IP_NFTABLES":
            raise HTTPException(422, "Action has no supported automatic CORE executor")
        if action == "BLOCK_IP_NFTABLES" and not 1 <= duration <= 86400:
            raise HTTPException(422, "Block duration must be between 1 and 86400 seconds")

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
            dry_run=True,
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
            priority=model.priority if model.priority is not None else 100,
        )

    def _to_whitelist_response(self, model: IPWhitelistModel) -> IPWhitelistResponse:
        return IPWhitelistResponse(
            id=str(model.id),
            project_id=str(model.project_id),
            ip_or_cidr=model.ip_or_cidr,
            description=model.description,
            created_at=model.created_at,
        )
