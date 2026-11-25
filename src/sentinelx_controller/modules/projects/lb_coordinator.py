"""Coordinator bridging per-project PostgreSQL LB config and sentinelx_lb HTTP API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from fastapi import HTTPException

from sentinelx_common.contracts.projects import (
    LBAlgorithmType,
    LBBackendRuntimeResponse,
    LBBackendStateUpdateRequest,
    ProjectLBConfigContract,
    ProjectLBStatusResponse,
)

if TYPE_CHECKING:
    from sentinelx_common.contracts.nodes import NodeResponse
    from sentinelx_controller.modules.nodes.service import NodeService
    from sentinelx_controller.modules.projects.service import ProjectService

logger = logging.getLogger("sentinelx_controller.projects.lb")


def _backend_url(node: NodeResponse) -> str:
    ip = node.ip_address.strip()
    host = f"[{ip}]" if ":" in ip and not ip.startswith("[") else ip
    return f"http://{host}:{node.lb_backend_port}"


class ProjectLBCoordinator:
    """Synchronizes Project LB pool/algorithm state with the target sentinelx_lb instance."""

    def __init__(
        self,
        project_service: ProjectService,
        node_service: NodeService,
        lb_admin_token: str | None = None,
        default_lb_url: str | None = None,
        timeout_seconds: float = 2.5,
    ) -> None:
        self._projects = project_service
        self._nodes = node_service
        self._admin_token = lb_admin_token
        self._default_lb_url = (
            default_lb_url.strip().rstrip("/")
            if default_lb_url and default_lb_url.strip()
            else None
        )
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    def _resolve_lb_url(self, lb_cfg: ProjectLBConfigContract) -> str | None:
        raw = (lb_cfg.lb_url or self._default_lb_url or "").strip().rstrip("/")
        return raw or None

    def _headers(self) -> dict[str, str]:
        if self._admin_token:
            return {"Authorization": f"Bearer {self._admin_token}"}
        return {}

    async def _build_desired_payload(
        self,
        project_id: str,
        lb_cfg: ProjectLBConfigContract,
    ) -> tuple[list[dict[str, Any]], dict[str, str], list[LBBackendRuntimeResponse]]:
        nodes = await self._nodes.list_nodes(project_id_str=project_id)
        backend_nodes = [n for n in nodes if n.lb_role == "lb_backend"]
        backends_payload: list[dict[str, Any]] = []
        url_to_node_id: dict[str, str] = {}
        fallback_items: list[LBBackendRuntimeResponse] = []
        for node in backend_nodes:
            url = _backend_url(node)
            url_to_node_id[url] = node.node_id
            health_path = node.lb_health_path or lb_cfg.health_path
            backends_payload.append(
                {
                    "url": url,
                    "name": node.hostname,
                    "weight": 1,
                    "health_path": health_path,
                }
            )
            fallback_items.append(
                LBBackendRuntimeResponse(
                    name=node.hostname,
                    url=url,
                    node_id=node.node_id,
                    weight=1,
                    health_path=health_path,
                    is_healthy=False,
                    admin_enabled=True,
                    health_state="unknown",
                )
            )
        return backends_payload, url_to_node_id, fallback_items

    @staticmethod
    def _config_body(
        lb_cfg: ProjectLBConfigContract,
        backends_payload: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "algorithm": lb_cfg.algorithm,
            "backends": backends_payload,
            "health_check": {
                "enabled": True,
                "path": lb_cfg.health_path,
                "interval_seconds": lb_cfg.health_interval_seconds,
                "failure_threshold": lb_cfg.failure_threshold,
                "success_threshold": lb_cfg.success_threshold,
            },
        }

    def _map_status_response(
        self,
        project_id: str,
        lb_cfg: ProjectLBConfigContract,
        raw: dict[str, Any],
        url_to_node_id: dict[str, str],
        *,
        sync_status: str = "synced",
        sync_message: str | None = None,
    ) -> ProjectLBStatusResponse:
        raw_pool = raw.get("pool")
        pool: dict[str, Any] = raw_pool if isinstance(raw_pool, dict) else {}
        raw_backends_obj = pool.get("backends")
        raw_backends: list[Any] = raw_backends_obj if isinstance(raw_backends_obj, list) else []
        backends: list[LBBackendRuntimeResponse] = []
        for item in raw_backends:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").rstrip("/")
            backends.append(
                LBBackendRuntimeResponse(
                    name=str(item.get("name") or url),
                    url=url,
                    node_id=url_to_node_id.get(url),
                    weight=int(item.get("weight") or 1),
                    health_path=(
                        str(item["health_path"]) if item.get("health_path") is not None else None
                    ),
                    is_healthy=bool(item.get("is_healthy", True)),
                    admin_enabled=bool(item.get("admin_enabled", True)),
                    health_state=str(item.get("health_state") or "healthy"),
                    in_flight=int(item.get("in_flight") or 0),
                    total_requests=int(item.get("total_requests") or 0),
                    success_requests=int(item.get("success_requests") or 0),
                    error_requests=int(item.get("error_requests") or 0),
                    consecutive_successes=int(item.get("consecutive_successes") or 0),
                    consecutive_failures=int(item.get("consecutive_failures") or 0),
                    last_health_check_at=(
                        str(item["last_health_check_at"])
                        if item.get("last_health_check_at") is not None
                        else None
                    ),
                    last_health_status_code=(
                        int(item["last_health_status_code"])
                        if isinstance(item.get("last_health_status_code"), int)
                        else None
                    ),
                    last_health_error=(
                        str(item["last_health_error"])
                        if item.get("last_health_error") is not None
                        else None
                    ),
                    flapping_detected=bool(item.get("flapping_detected", False)),
                )
            )
        raw_algo = str(raw.get("algorithm") or lb_cfg.algorithm)
        algo: LBAlgorithmType = (
            "least_in_flight" if raw_algo == "least_in_flight" else "round_robin"
        )
        raw_hc = raw.get("health_check")
        hc: dict[str, Any] = raw_hc if isinstance(raw_hc, dict) else {}
        return ProjectLBStatusResponse(
            project_id=project_id,
            enabled=lb_cfg.enabled,
            lb_url=self._resolve_lb_url(lb_cfg),
            algorithm=algo,
            reachable=True,
            sync_status=(
                "synced" if sync_status == "synced" else "error"
            ),
            sync_message=sync_message,
            health_check=dict(hc),
            total_backends=int(pool.get("total_backends") or len(backends)),
            healthy_backends=int(pool.get("healthy_backends") or 0),
            routable_backends=int(
                pool.get("routable_backends") or pool.get("healthy_backends") or 0
            ),
            admin_disabled_backends=int(pool.get("admin_disabled_backends") or 0),
            total_in_flight=int(pool.get("total_in_flight") or 0),
            total_requests=int(pool.get("total_requests") or 0),
            total_success=int(pool.get("total_success") or 0),
            total_errors=int(pool.get("total_errors") or 0),
            backends=backends,
        )

    async def get_status(self, project_id: str) -> ProjectLBStatusResponse:
        """Query runtime status from sentinelx_lb, auto-healing drift if DB has pool."""
        project = await self._projects.get_project(project_id)
        lb_cfg = project.load_balancer
        if not lb_cfg.enabled:
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=False,
                lb_url=lb_cfg.lb_url,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="disabled",
            )

        backends_payload, url_to_node_id, fallback_items = await self._build_desired_payload(
            project_id, lb_cfg
        )
        target_lb_url = self._resolve_lb_url(lb_cfg)
        if not target_lb_url:
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=True,
                lb_url=None,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="error",
                sync_message=(
                    "Hệ thống chưa cấu hình SENTINELX_DEFAULT_LB_URL và dự án chưa đặt "
                    "Endpoint LB riêng."
                ),
                total_backends=len(fallback_items),
                backends=fallback_items,
            )

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(f"{target_lb_url}/lb/status") as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        return ProjectLBStatusResponse(
                            project_id=project_id,
                            enabled=True,
                            lb_url=target_lb_url,
                            algorithm=lb_cfg.algorithm,
                            reachable=False,
                            sync_status="error",
                            sync_message=f"LB trả về HTTP {resp.status}: {text[:160]}",
                            total_backends=len(fallback_items),
                            backends=fallback_items,
                        )
                    raw: dict[str, Any] = await resp.json()

                # Auto-reconcile if LB restarted with empty/drifted pool or algorithm.
                raw_pool = raw.get("pool")
                pool: dict[str, Any] = raw_pool if isinstance(raw_pool, dict) else {}
                raw_list = pool.get("backends")
                live_items = raw_list if isinstance(raw_list, list) else []
                live_urls = [
                    str(b.get("url") or "").rstrip("/")
                    for b in live_items
                    if isinstance(b, dict)
                ]
                expected_urls = [str(b["url"]).rstrip("/") for b in backends_payload]
                if (
                    raw.get("algorithm") != lb_cfg.algorithm
                    or sorted(live_urls) != sorted(expected_urls)
                ):
                    async with session.put(
                        f"{target_lb_url}/lb/admin/config",
                        json=self._config_body(lb_cfg, backends_payload),
                        headers=self._headers(),
                    ) as sync_resp:
                        if sync_resp.status < 400:
                            raw = await sync_resp.json()
                        else:
                            detail = await sync_resp.text()
                            return self._map_status_response(
                                project_id,
                                lb_cfg,
                                raw,
                                url_to_node_id,
                                sync_status="error",
                                sync_message=(
                                    f"Đồng bộ cấu hình LB thất bại ({sync_resp.status}): "
                                    f"{detail[:160]}"
                                ),
                            )
            return self._map_status_response(project_id, lb_cfg, raw, url_to_node_id)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=True,
                lb_url=target_lb_url,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="unreachable",
                sync_message=f"Không thể kết nối tới Load Balancer ({type(err).__name__})",
                total_backends=len(fallback_items),
                backends=fallback_items,
            )

    async def sync_project_lb(self, project_id: str) -> ProjectLBStatusResponse:
        """Push project algorithm, health config, and LB backend nodes to sentinelx_lb."""
        project = await self._projects.get_project(project_id)
        lb_cfg = project.load_balancer
        if not lb_cfg.enabled:
            target_lb_url = self._resolve_lb_url(lb_cfg)
            if target_lb_url:
                await self._clear_disabled_lb(project_id, lb_cfg, target_lb_url)
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=False,
                lb_url=lb_cfg.lb_url,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="disabled",
            )

        backends_payload, url_to_node_id, fallback_items = await self._build_desired_payload(
            project_id, lb_cfg
        )
        target_lb_url = self._resolve_lb_url(lb_cfg)
        if not target_lb_url:
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=True,
                lb_url=None,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="error",
                sync_message=(
                    "Hệ thống chưa cấu hình SENTINELX_DEFAULT_LB_URL và dự án chưa đặt "
                    "Endpoint LB riêng."
                ),
                total_backends=len(fallback_items),
                backends=fallback_items,
            )

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.put(
                    f"{target_lb_url}/lb/admin/config",
                    json=self._config_body(lb_cfg, backends_payload),
                    headers=self._headers(),
                ) as resp:
                    if resp.status >= 400:
                        detail = await resp.text()
                        return ProjectLBStatusResponse(
                            project_id=project_id,
                            enabled=True,
                            lb_url=target_lb_url,
                            algorithm=lb_cfg.algorithm,
                            reachable=True,
                            sync_status="error",
                            sync_message=f"LB từ chối đồng bộ (HTTP {resp.status}): {detail[:160]}",
                            total_backends=len(fallback_items),
                            backends=fallback_items,
                        )
                    raw: dict[str, Any] = await resp.json()
                    return self._map_status_response(project_id, lb_cfg, raw, url_to_node_id)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            logger.warning("LB sync skipped (unreachable) project=%s: %s", project_id, err)
            return ProjectLBStatusResponse(
                project_id=project_id,
                enabled=True,
                lb_url=target_lb_url,
                algorithm=lb_cfg.algorithm,
                reachable=False,
                sync_status="unreachable",
                sync_message=(
                    f"Đã lưu cấu hình nhưng chưa kết nối được tới LB ({type(err).__name__})"
                ),
                total_backends=len(fallback_items),
                backends=fallback_items,
            )

    async def _clear_disabled_lb(
        self,
        project_id: str,
        lb_cfg: ProjectLBConfigContract,
        target_lb_url: str,
    ) -> None:
        """Clear backends and pause probing on sentinelx_lb when this project disables LB."""
        try:
            backends_payload, _, _ = await self._build_desired_payload(project_id, lb_cfg)
            project_urls = {str(b["url"]).rstrip("/") for b in backends_payload}
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(f"{target_lb_url}/lb/status") as status_resp:
                    if status_resp.status >= 400:
                        return
                    raw = await status_resp.json(content_type=None)
                raw_pool = raw.get("pool") if isinstance(raw, dict) else None
                live_items = raw_pool.get("backends") if isinstance(raw_pool, dict) else None
                live_urls = {
                    str(item.get("url") or "").rstrip("/")
                    for item in (live_items or [])
                    if isinstance(item, dict)
                }
                if lb_cfg.lb_url or (live_urls and live_urls & project_urls):
                    await session.put(
                        f"{target_lb_url}/lb/admin/config",
                        json={
                            "algorithm": lb_cfg.algorithm,
                            "backends": [],
                            "health_check": {
                                "enabled": False,
                                "path": lb_cfg.health_path,
                                "interval_seconds": lb_cfg.health_interval_seconds,
                                "failure_threshold": lb_cfg.failure_threshold,
                                "success_threshold": lb_cfg.success_threshold,
                            },
                        },
                        headers=self._headers(),
                    )
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as err:
            logger.debug("LB disable cleanup skipped project=%s: %s", project_id, err)

    async def switch_algorithm(
        self,
        project_id: str,
        algorithm: LBAlgorithmType,
    ) -> ProjectLBStatusResponse:
        """Persist updated algorithm in PostgreSQL and apply it immediately on sentinelx_lb."""
        await self._projects.update_lb_algorithm(project_id, algorithm)
        return await self.sync_project_lb(project_id)

    async def set_backend_state(
        self,
        project_id: str,
        node_id: str,
        request: LBBackendStateUpdateRequest,
    ) -> ProjectLBStatusResponse:
        """Manually enable or drain/eject a specific LB backend node."""
        project = await self._projects.get_project(project_id)
        lb_cfg = project.load_balancer
        target_lb_url = self._resolve_lb_url(lb_cfg)
        if not lb_cfg.enabled or not target_lb_url:
            raise HTTPException(409, "Load Balancer is not enabled or configured for this project")

        node = await self._nodes.get_node(node_id)
        if node.project_id != project_id:
            raise HTTPException(404, "Node does not belong to this project")
        if node.lb_role != "lb_backend":
            raise HTTPException(409, "Node is not configured as an LB backend")

        target_url = _backend_url(node)
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    f"{target_lb_url}/lb/admin/backends/state",
                    json={
                        "identifier": target_url,
                        "enabled": request.enabled,
                        "force": request.force,
                    },
                    headers=self._headers(),
                ) as resp:
                    if resp.status == 409:
                        data = await resp.json()
                        raise HTTPException(
                            409,
                            data.get("error") or "Cannot disable last healthy backend",
                        )
                    if resp.status == 404:
                        # Pool was not yet pushed; sync pool then retry state update once
                        await self.sync_project_lb(project_id)
                        async with session.post(
                            f"{target_lb_url}/lb/admin/backends/state",
                            json={
                                "identifier": target_url,
                                "enabled": request.enabled,
                                "force": request.force,
                            },
                            headers=self._headers(),
                        ) as retry_resp:
                            if retry_resp.status >= 400:
                                detail = await retry_resp.text()
                                raise HTTPException(retry_resp.status, detail[:200])
                    elif resp.status >= 400:
                        detail = await resp.text()
                        raise HTTPException(resp.status, detail[:200])
        except HTTPException:
            raise
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise HTTPException(
                502,
                f"Không thể kết nối tới Load Balancer để cập nhật backend ({type(err).__name__})",
            ) from err

        return await self.get_status(project_id)
