# ADR-0007 — Dynamic Per-Project Load Balancer Control Plane & Observability

## Status
Accepted

## Context
SentinelX CORE (F12–F13) provides an `aiohttp` Layer-7 Reverse Proxy Load Balancer (`sentinelx_lb`) with `round_robin` and `least_in_flight` routing and active HTTP `/health` ejection/re-add. However, backend pools and routing algorithms were static startup-only configuration (`SENTINELX_LB_BACKENDS`, `SENTINELX_LB_ALGORITHM`), with no per-project toggle, no UI observability, and no hot synchronization from Controller.

This ADR defines the control plane for per-project Load Balancer management while explicitly preserving ADR-0005 and CORE Phase boundaries:
- Automatic CPU/RAM metric-driven `EJECT_NODE` (Adaptive LB) remains deferred to Phase 2 (requires weighted routing, connection draining, and cluster-wide anti-cascading quorum).
- Load Balancer remains optional per Project (standalone host-monitoring projects keep working unchanged without any LB).

## Decision
1. **Per-Project Optional LB Configuration (PostgreSQL + API)**:
   - Each Project optionally stores LB settings (`enabled`, `lb_url`, `algorithm`, `health_check` parameters).
   - Both `round_robin` and `least_in_flight` algorithms can be chosen at project creation and modified at runtime.
   - Each Node in a project can optionally participate as an `lb_backend` (with configurable `lb_backend_port` and `lb_health_path`) or remain `standalone`.
2. **Dynamic Hot-Sync API on `sentinelx_lb`**:
   - Expose authenticated management endpoints (`/lb/admin/config`, `/lb/admin/algorithm`, `/lb/admin/backends/{identifier}/state`) protected by `SENTINELX_LB_ADMIN_TOKEN`.
   - `BackendPool.sync_pool(...)` preserves in-flight and cumulative request telemetry for unchanged backends while applying additions, removals, weight/path updates, and algorithm changes with zero restart.
   - `admin_enabled` manual drain/enable state is tracked independently of `/health` `is_healthy`, preventing active probes from accidentally re-enabling a backend under operator maintenance and rejecting attempts to drain the last healthy routable backend unless `force=true`.
3. **Controller Proxy & Multi-Host Compliance**:
   - Dashboard communicates exclusively with Controller (`/api/v1/projects/{id}/load-balancer/*`), never directly exposing `SENTINELX_LB_ADMIN_TOKEN` to browsers or hard-coding `localhost`.
   - When `lb_url` is unreachable during configuration save, Controller persists the desired state fail-soft and surfaces sync status for retry.
4. **Visual Observability**:
   - Dashboard provides a dedicated "Cân bằng tải" view showing live request distribution, backend health states, algorithm switching, and manual drain/enable controls, plus a compact status card in Overview when enabled on the active Project.
