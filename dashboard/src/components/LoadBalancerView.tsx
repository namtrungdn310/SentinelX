import { useCallback, useEffect, useId, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Globe,
  Plus,
  Server,
  Settings2,
  ShieldAlert,
  Trash2,
  Users,
} from "lucide-react";
import {
  defaultProjectLBConfig,
  fetchProjectLBStatus,
  setProjectLBBackendState,
} from "../api";
import { healthLabels, nodeHealth } from "../presentation";
import { LBPoolPickerModal } from "./LBPoolPickerModal";
import type {
  LBBackendRuntime,
  Node,
  NodeLBRoleType,
  Project,
  ProjectLBConfig,
  ProjectLBStatus,
} from "../types";
import type { SecurityToastPayload } from "./SecurityToast";

interface Props {
  project: Project;
  projectNodes: Node[];
  onOpenConfig: () => void;
  onGoToHosts?: () => void;
  onUpdateProjectLB: (
    projectId: string,
    payload: { load_balancer: ProjectLBConfig },
  ) => Promise<Project | void>;
  onUpdateNode: (
    nodeId: string,
    payload: {
      lb_role?: NodeLBRoleType;
      lb_backend_port?: number;
      lb_health_path?: string | null;
    },
  ) => Promise<Node | void>;
  onNotify?: (toast: SecurityToastPayload) => void;
  initialStatus?: ProjectLBStatus | null;
}

const BACKEND_SLOT_HEIGHT = 104;
const BACKEND_SLOT_GAP = 12;
const TOPOLOGY_PAD_Y = 0;

function buildEmptyProjectLBStatus(
  project: Project,
  projectNodes: Node[],
): ProjectLBStatus {
  const lb = project.load_balancer ?? defaultProjectLBConfig();
  const backendNodes = projectNodes.filter((n) => n.lb_role === "lb_backend");
  const backends: LBBackendRuntime[] = backendNodes.map((n) => ({
    name: n.hostname,
    url: `http://${n.ip_address}:${n.lb_backend_port ?? 8080}`,
    node_id: n.id,
    weight: 1,
    health_path: n.lb_health_path || lb.health_path || "/health",
    is_healthy: false,
    admin_enabled: true,
    health_state: lb.enabled ? "unknown" : "disabled",
    in_flight: 0,
    total_requests: 0,
    success_requests: 0,
    error_requests: 0,
    consecutive_successes: 0,
    consecutive_failures: 0,
    last_health_check_at: null,
    last_health_error: null,
  }));
  return {
    project_id: project.id,
    enabled: Boolean(lb.enabled),
    lb_url: lb.lb_url ?? null,
    algorithm: lb.algorithm ?? "round_robin",
    reachable: false,
    sync_status: lb.enabled ? "syncing" : "disabled",
    sync_message: null,
    health_check: {
      enabled: true,
      path: lb.health_path || "/health",
      interval_seconds: lb.health_interval_seconds ?? 3,
      failure_threshold: lb.failure_threshold ?? 3,
      success_threshold: lb.success_threshold ?? 2,
    },
    total_backends: backends.length,
    healthy_backends: 0,
    routable_backends: 0,
    admin_disabled_backends: 0,
    total_in_flight: 0,
    total_requests: 0,
    total_success: 0,
    total_errors: 0,
    backends,
  };
}

export function LoadBalancerView({
  project,
  projectNodes,
  onOpenConfig,
  onGoToHosts,
  onUpdateProjectLB,
  onUpdateNode,
  onNotify,
  initialStatus = null,
}: Props) {
  const headingId = useId();
  const [liveStatus, setLiveStatus] = useState<ProjectLBStatus | null>(initialStatus);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Eligible already-registered & online project servers not yet in LB pool
  const eligibleActiveNodes = useMemo(
    () =>
      projectNodes.filter(
        (n) => n.lb_role !== "lb_backend" && n.status === "online",
      ),
    [projectNodes],
  );
  const unavailableNodes = useMemo(
    () =>
      projectNodes.filter(
        (n) => n.lb_role !== "lb_backend" && n.status !== "online",
      ),
    [projectNodes],
  );
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  const lbEnabled = Boolean(project.load_balancer?.enabled);

  const loadLiveStatus = useCallback(
    async (silent = false) => {
      if (!lbEnabled) return;
      try {
        const res = await fetchProjectLBStatus(project.id);
        setLiveStatus(res);
        setError(null);
      } catch (err) {
        if (!silent) {
          setError(
            err instanceof Error
              ? err.message
              : "Không thể kết nối Controller để lấy trạng thái LB.",
          );
        }
      }
    },
    [lbEnabled, project.id],
  );

  // Auto-reload live status & auto-reconcile LB pool every 2.5s when enabled
  useEffect(() => {
    if (!lbEnabled) {
      return;
    }
    let cancelled = false;
    const poll = async (silent: boolean) => {
      try {
        const res = await fetchProjectLBStatus(project.id);
        if (!cancelled) {
          setLiveStatus(res);
          setError(null);
        }
      } catch (err) {
        if (!cancelled && !silent) {
          setError(
            err instanceof Error
              ? err.message
              : "Không thể kết nối Controller để lấy trạng thái LB.",
          );
        }
      }
    };
    void poll(false);
    const timer = window.setInterval(() => {
      void poll(true);
    }, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    lbEnabled,
    project.id,
    project.load_balancer?.lb_url,
    project.load_balancer?.algorithm,
    project.load_balancer?.health_path,
    project.load_balancer?.health_interval_seconds,
    project.load_balancer?.failure_threshold,
    project.load_balancer?.success_threshold,
  ]);

  const fallbackStatus = useMemo(
    () => buildEmptyProjectLBStatus(project, projectNodes),
    [project, projectNodes],
  );

  const status: ProjectLBStatus =
    lbEnabled && liveStatus?.project_id === project.id ? liveStatus : fallbackStatus;

  const nodeById = useMemo(
    () => new Map(projectNodes.map((n) => [n.id, n])),
    [projectNodes],
  );

  // Handlers
  const handleToggleLBEnabled = async (nextEnabled: boolean) => {
    if (actionBusy) return;
    setActionBusy("toggle");
    setError(null);
    const nextConfig: ProjectLBConfig = {
      ...(project.load_balancer ?? defaultProjectLBConfig()),
      enabled: nextEnabled,
    };
    try {
      await onUpdateProjectLB(project.id, { load_balancer: nextConfig });
      if (!nextEnabled) {
        setLiveStatus(null);
      }
      onNotify?.({
        id: `lb-toggle-${Date.now()}`,
        type: "defense",
        title: nextEnabled
          ? "Đã bật Load Balancer"
          : "Đã tắt Load Balancer",
        message: nextEnabled
          ? `${project.name} đã kích hoạt chia tải (${
              nextConfig.algorithm === "least_in_flight"
                ? "Least In-Flight"
                : "Round Robin"
            }).`
          : `${project.name} đã chuyển về giám sát máy chủ độc lập.`,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Không thể thay đổi trạng thái Load Balancer.",
      );
    } finally {
      setActionBusy(null);
    }
  };

  const handleToggleBackendAdminState = async (
    backend: LBBackendRuntime,
    nextEnabled: boolean,
  ) => {
    if (!backend.node_id || actionBusy) return;
    setActionBusy(`drain:${backend.node_id}`);
    setError(null);
    try {
      const res = await setProjectLBBackendState(
        project.id,
        backend.node_id,
        nextEnabled,
      );
      setLiveStatus(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Không thể thay đổi trạng thái nhận tải của backend.",
      );
    } finally {
      setActionBusy(null);
    }
  };

  const handleAddPoolItems = async (
    items: Array<{ nodeId: string; port: number }>,
  ) => {
    if (!items.length || actionBusy) return;
    setActionBusy("add-node");
    setError(null);
    try {
      for (const item of items) {
        await onUpdateNode(item.nodeId, {
          lb_role: "lb_backend",
          lb_backend_port: item.port,
        });
      }
      await loadLiveStatus(true);
      onNotify?.({
        id: `lb-add-node-${Date.now()}`,
        type: "defense",
        title: "Đã đưa máy chủ vào LB Pool",
        message:
          items.length === 1
            ? `Đã thêm 1 máy chủ vào pool của ${project.name}.`
            : `Đã thêm ${items.length} máy chủ vào pool của ${project.name}.`,
      });
    } finally {
      setActionBusy(null);
    }
  };

  const handleRemoveFromPool = async (backend: LBBackendRuntime) => {
    if (!backend.node_id || actionBusy) return;
    setActionBusy(`remove:${backend.node_id}`);
    setError(null);
    try {
      await onUpdateNode(backend.node_id, { lb_role: "standalone" });
      await loadLiveStatus(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không thể gỡ backend khỏi pool.",
      );
    } finally {
      setActionBusy(null);
    }
  };

  // Geometry for SVG traffic flow diagram matching fixed-height backend cards
  const backends = status.backends;
  const rowCount = Math.max(1, backends.length);
  const svgHeight =
    TOPOLOGY_PAD_Y * 2 +
    rowCount * BACKEND_SLOT_HEIGHT +
    (rowCount - 1) * BACKEND_SLOT_GAP;
  const midY = svgHeight / 2;

  const successRate =
    status.total_requests > 0
      ? ((status.total_success / status.total_requests) * 100).toFixed(1)
      : "100.0";
  const ingressTargetHost = (status.lb_url || "LB Hệ thống")
    .replace(/^https?:\/\//, "")
    .replace(/\/$/, "");

  return (
    <section className="lb-view" aria-labelledby={headingId}>
      <h2 id={headingId} className="sr-only">
        Theo dõi và điều khiển Load Balancer
      </h2>

      {/* Top Unified Header Control Bar (always anchored in place) */}
      <div className="panel lb-header-bar">
        <div className="lb-header-identity">
          <div className="lb-status-cluster">
            <span
              className={`lb-conn-badge ${
                !lbEnabled ? "paused" : status.reachable ? "online" : "offline"
              }`}
            >
              <i />
              {!lbEnabled
                ? "LB Đang tắt"
                : status.reachable
                  ? "LB Đang hoạt động"
                  : "Mất kết nối LB"}
            </span>
            <span className="lb-url-chip font-mono" title="Endpoint Load Balancer">
              <Globe size={13} />
              {status.lb_url || "LB Hệ thống mặc định"}
            </span>
          </div>
          {lbEnabled && status.sync_message && status.sync_status !== "synced" && (
            <p className="lb-sync-warning">{status.sync_message}</p>
          )}
        </div>

        <div className="lb-header-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onOpenConfig}
            disabled={Boolean(actionBusy)}
          >
            <Settings2 size={14} /> Cấu hình
          </button>

          <div className="lb-switch-control">
            <span className="lb-switch-text">
              {actionBusy === "toggle"
                ? "Đang lưu…"
                : lbEnabled
                  ? "Bật"
                  : "Tắt"}
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={lbEnabled}
              aria-label="Bật hoặc tắt Load Balancer cho dự án"
              className={`lb-slider-track ${lbEnabled ? "is-on" : ""}`}
              onClick={() => void handleToggleLBEnabled(!lbEnabled)}
              disabled={Boolean(actionBusy)}
              title="Gạt sang phải để bật, sang trái để tắt Load Balancer"
            >
              <span className="lb-slider-thumb" />
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="feedback-banner feedback-error" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Animated Traffic Flow Topology Panel */}
      <div className="panel lb-topology-panel">
        <div className="panel-heading lb-topology-heading">
          <div>
            <h2>Luồng phân phối tải trực tiếp</h2>
            <p className="panel-sub">
              Theo dõi hướng đi của request theo thời gian thực qua{" "}
              <strong>
                {status.algorithm === "least_in_flight"
                  ? "Least In-Flight"
                  : "Round Robin"}
              </strong>{" "}
              · Tự động ngắt nhánh khi backend lỗi probe{" "}
              <code>{status.health_check.path}</code>.
            </p>
          </div>
        </div>

        {backends.length === 0 ? (
          <div className="lb-no-backends">
            <Server size={24} />
            <div>
              <strong>Pool hiện chưa có Backend Server nào</strong>
              <p>
                {eligibleActiveNodes.length > 0
                  ? `Có ${eligibleActiveNodes.length} máy chủ đã đăng ký & đang hoạt động sẵn sàng đưa vào LB Pool.`
                  : "Chưa có máy chủ đang hoạt động nào ngoài Pool. Hãy kiểm tra kết nối Agent tại trang Máy chủ."}
              </p>
            </div>
            {eligibleActiveNodes.length > 0 ? (
              <button
                type="button"
                className="btn btn-primary"
                style={{ marginLeft: "auto" }}
                onClick={() => setIsPickerOpen(true)}
              >
                <Plus size={14} /> Chọn máy chủ vào Pool
              </button>
            ) : (
              onGoToHosts && (
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ marginLeft: "auto" }}
                  onClick={onGoToHosts}
                >
                  Mở trang Máy chủ <ArrowRight size={14} />
                </button>
              )
            )}
          </div>
        ) : (
          <div className="lb-flow-canvas">
            <div className="lb-flow-grid">
              {/* Column 1: External Client Origin */}
              <div className="lb-stage-col lb-ingress-col">
                <div className="lb-node-card lb-ingress-card">
                  <span className="lb-card-eyebrow lb-card-eyebrow-icon">
                    <Users size={11} /> NGUỒN TRUY CẬP
                  </span>
                  <strong>Client</strong>
                  <small className="lb-ingress-origin">
                    <span>Internet / LAN</span>
                    <span className="lb-ingress-dest font-mono">
                      → {ingressTargetHost}
                    </span>
                  </small>
                  <div className="lb-mini-stat">
                    <span>Tổng request</span>
                    <b className="font-mono">
                      {status.total_requests.toLocaleString("vi-VN")}
                    </b>
                  </div>
                </div>
              </div>

              {/* Column 2: SVG Connector 1 (Origin -> LB Hub) */}
              <div className="lb-connector-col" style={{ height: `${svgHeight}px` }}>
                <svg
                  className="lb-connector-svg"
                  viewBox={`0 0 120 ${svgHeight}`}
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <path
                    d={`M 0 ${midY} L 120 ${midY}`}
                    vectorEffect="non-scaling-stroke"
                    className={`lb-flow-path ${
                      lbEnabled && status.routable_backends > 0
                        ? "lb-flow-path--ingress"
                        : "lb-flow-path--paused"
                    }`}
                  />
                  {lbEnabled && status.routable_backends > 0 && (
                    <circle r="4" className="lb-packet-dot lb-packet-dot--ingress">
                      <animateMotion
                        dur="1.2s"
                        repeatCount="indefinite"
                        path={`M 0 ${midY} L 120 ${midY}`}
                      />
                    </circle>
                  )}
                </svg>
              </div>

              {/* Column 3: Load Balancer Core Hub */}
              <div className="lb-stage-col lb-hub-col">
                <div
                  className={`lb-node-card lb-hub-card ${
                    !lbEnabled
                      ? "paused"
                      : status.routable_backends > 0
                        ? "active"
                        : "degraded"
                  }`}
                >
                  <div className="lb-hub-pulse-ring" aria-hidden="true" />
                  <span className="lb-card-eyebrow">SENTINELX LB HUB</span>
                  <strong>
                    {!lbEnabled
                      ? "Tạm dừng"
                      : status.algorithm === "least_in_flight"
                        ? "Least In-Flight"
                        : "Round Robin"}
                  </strong>
                  <small className="lb-hub-role">HTTP Reverse Proxy</small>
                  <div className="lb-hub-kpis">
                    <div>
                      <span>Đang xử lý</span>
                      <b className="font-mono">{lbEnabled ? status.total_in_flight : 0}</b>
                    </div>
                    <div>
                      <span>Sẵn sàng</span>
                      <b className="font-mono">
                        {lbEnabled ? status.routable_backends : 0}/{status.total_backends}
                      </b>
                    </div>
                    <div>
                      <span>Thành công</span>
                      <b className="font-mono">{lbEnabled ? `${successRate}%` : "—"}</b>
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 4: SVG Connector 2 (LB Hub -> Each Backend) */}
              <div className="lb-connector-col" style={{ height: `${svgHeight}px` }}>
                <svg
                  className="lb-connector-svg"
                  viewBox={`0 0 160 ${svgHeight}`}
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  {backends.map((backend, index) => {
                    const by =
                      TOPOLOGY_PAD_Y +
                      index * (BACKEND_SLOT_HEIGHT + BACKEND_SLOT_GAP) +
                      BACKEND_SLOT_HEIGHT / 2;
                    const d = `M 0 ${midY} C 75 ${midY}, 85 ${by}, 160 ${by}`;
                    const isRoutable =
                      lbEnabled && backend.is_healthy && backend.admin_enabled;
                    const isEjected = lbEnabled && !backend.is_healthy;
                    const isActiveTarget = isRoutable && backend.in_flight > 0;
                    const packetDur =
                      backend.in_flight >= 4
                        ? "1.15s"
                        : backend.in_flight >= 2
                          ? "1.55s"
                          : "2.0s";
                    return (
                      <g key={backend.url}>
                        <path
                          d={d}
                          vectorEffect="non-scaling-stroke"
                          className={`lb-flow-path ${
                            isRoutable
                              ? isActiveTarget
                                ? "lb-flow-path--highlight"
                                : "lb-flow-path--active"
                              : isEjected
                                ? "lb-flow-path--ejected"
                                : "lb-flow-path--paused"
                          }`}
                        />
                        {isRoutable && (
                          <>
                            <circle
                              r={isActiveTarget ? 4.5 : 3.8}
                              className={`lb-packet-dot ${
                                isActiveTarget ? "lb-packet-dot--hot" : ""
                              }`}
                            >
                              <animateMotion
                                dur={packetDur}
                                begin={`${(index * 0.35).toFixed(2)}s`}
                                repeatCount="indefinite"
                                path={d}
                              />
                            </circle>
                            <circle
                              r="3"
                              className="lb-packet-dot lb-packet-dot--trail"
                            >
                              <animateMotion
                                dur={packetDur}
                                begin={`${(index * 0.35 + 0.8).toFixed(2)}s`}
                                repeatCount="indefinite"
                                path={d}
                              />
                            </circle>
                          </>
                        )}
                      </g>
                    );
                  })}
                </svg>
                {backends.map((backend, index) => {
                  const isRoutable =
                    lbEnabled && backend.is_healthy && backend.admin_enabled;
                  if (isRoutable) return null;
                  const by =
                    TOPOLOGY_PAD_Y +
                    index * (BACKEND_SLOT_HEIGHT + BACKEND_SLOT_GAP) +
                    BACKEND_SLOT_HEIGHT / 2;
                  const topPct = (((midY + by) / 2) / svgHeight) * 100;
                  const isEjected = lbEnabled && !backend.is_healthy;
                  return (
                    <span
                      key={`cut-${backend.url}`}
                      className={`lb-lane-cut-badge ${
                        isEjected ? "ejected" : "paused"
                      }`}
                      style={{ top: `${topPct}%` }}
                      aria-hidden="true"
                    >
                      {isEjected ? "× Ngắt" : "II"}
                    </span>
                  );
                })}
              </div>

              {/* Column 5: Backend Pool Cards */}
              <div className="lb-stage-col lb-backends-col">
                {backends.map((backend) => {
                  const isRoutable =
                    lbEnabled && backend.is_healthy && backend.admin_enabled;
                  const isPendingSync =
                    lbEnabled &&
                    !status.reachable &&
                    backend.health_state === "unknown";
                  const stateTone = !lbEnabled
                    ? "paused"
                    : isPendingSync
                      ? "paused"
                      : !backend.is_healthy
                        ? "crit"
                        : !backend.admin_enabled
                          ? "paused"
                          : backend.health_state === "recovering" ||
                              backend.health_state === "degraded"
                            ? "warn"
                            : "ok";
                  const stateLabel = !lbEnabled
                    ? "ĐANG TẮT"
                    : isPendingSync
                      ? "CHỜ ĐỒNG BỘ"
                      : !backend.is_healthy
                        ? "EJECTED"
                        : !backend.admin_enabled
                          ? "TẠM RÚT"
                          : backend.health_state === "recovering"
                            ? "ĐANG PHỤC HỒI"
                            : "HEALTHY";
                  const loadPercent = lbEnabled
                    ? Math.min(100, backend.in_flight * 14)
                    : 0;
                  const isBusy =
                    actionBusy === `drain:${backend.node_id ?? backend.url}`;

                  return (
                    <div
                      key={backend.url}
                      className={`lb-backend-card tone-${stateTone} ${
                        lbEnabled &&
                        backend.is_healthy &&
                        backend.admin_enabled &&
                        backend.in_flight > 0
                          ? "is-target"
                          : ""
                      }`}
                      style={{ height: `${BACKEND_SLOT_HEIGHT}px` }}
                    >
                      <div className="lb-backend-card-top">
                        <div className="lb-backend-identity">
                          <strong>{backend.name}</strong>
                          <span className="font-mono">
                            {backend.url.replace(/^https?:\/\//, "")}
                          </span>
                        </div>
                        <span className={`lb-state-pill tone-${stateTone}`}>
                          {stateLabel}
                        </span>
                      </div>

                      <div className="lb-inflight-label">
                        <span>In-flight: {backend.in_flight}</span>
                        <span className="font-mono">
                          {backend.total_requests.toLocaleString("vi-VN")} req
                          {backend.error_requests > 0
                            ? ` · ${backend.error_requests} err`
                            : ""}
                        </span>
                      </div>

                      <div className="lb-backend-card-bottom">
                        <div className="lb-inflight-track">
                          <div
                            className={`lb-inflight-fill ${
                              isRoutable ? "active" : "inactive"
                            }`}
                            style={{ width: `${loadPercent}%` }}
                          />
                        </div>

                        <div className="lb-card-actions">
                          {backend.node_id && (
                            <button
                              type="button"
                              className={`btn-xs ${
                                backend.admin_enabled
                                  ? "btn-outline"
                                  : "btn-primary"
                              }`}
                              disabled={
                                isBusy ||
                                (backend.admin_enabled && status.routable_backends <= 1)
                              }
                              title={
                                backend.admin_enabled && status.routable_backends <= 1
                                  ? "Không thể tạm rút backend hoạt động cuối cùng (hãy Tắt LB nếu muốn ngừng chia tải)"
                                  : undefined
                              }
                              onClick={() =>
                                void handleToggleBackendAdminState(
                                  backend,
                                  !backend.admin_enabled,
                                )
                              }
                            >
                              {backend.admin_enabled ? "Tạm rút" : "Bật lại"}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
        {backends.length === 1 && (
          <div className="lb-single-backend-hint">
            <AlertTriangle size={14} />
            <span>
              Pool hiện mới có <strong>1 backend</strong> — hãy thêm ít nhất 2 máy
              chủ vào pool để Load Balancer chia tải luân phiên và dự phòng lỗi.
            </span>
          </div>
        )}
      </div>

      {/* Pool Health Diagnostics & Node Membership */}
      <div className="panel lb-pool-panel">
        <div className="panel-heading">
          <div>
            <h2>Chẩn đoán Health Check & Quản lý Pool</h2>
            <p className="panel-sub">
              Kiểm tra định kỳ <code>{status.health_check.path}</code> mỗi{" "}
              {status.health_check.interval_seconds}s · Tự động loại sau{" "}
              {status.health_check.failure_threshold} lỗi liên tiếp, phục hồi sau{" "}
              {status.health_check.success_threshold} lần OK.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setIsPickerOpen(true)}
            disabled={Boolean(actionBusy)}
          >
            <Plus size={14} /> Chọn máy chủ vào Pool
            {eligibleActiveNodes.length > 0 && (
              <span className="lb-btn-count">{eligibleActiveNodes.length}</span>
            )}
          </button>
        </div>

        {backends.length > 0 && (
          <div className="lb-diagnostics-table-wrap">
            <table className="lb-diagnostics-table">
              <thead>
                <tr>
                  <th>Backend Node</th>
                  <th>Endpoint</th>
                  <th>Health Probe</th>
                  <th>Trạng thái Agent</th>
                  <th>Chi tiết / Lỗi gần nhất</th>
                  <th className="align-right">Pool</th>
                </tr>
              </thead>
              <tbody>
                {backends.map((backend) => {
                  const linkedNode = backend.node_id
                    ? nodeById.get(backend.node_id)
                    : undefined;
                  return (
                    <tr key={backend.url}>
                      <td>
                        <strong>{linkedNode?.hostname || backend.name}</strong>
                      </td>
                      <td className="font-mono">
                        {backend.url}
                        <small className="lb-sub-path">
                          {backend.health_path || status.health_check.path}
                        </small>
                      </td>
                      <td>
                        {backend.is_healthy ? (
                          <span className="lb-probe-ok">
                            <CheckCircle2 size={14} /> OK (
                            {backend.consecutive_successes} liên tiếp)
                          </span>
                        ) : (
                          <span className="lb-probe-err">
                            <ShieldAlert size={14} /> Lỗi{" "}
                            {backend.consecutive_failures}/
                            {status.health_check.failure_threshold}
                          </span>
                        )}
                      </td>
                      <td>
                        {linkedNode ? (
                          <span className={`status-badge ${nodeHealth(linkedNode)}`}>
                            <i />
                            {healthLabels[nodeHealth(linkedNode)]}
                          </span>
                        ) : (
                          <span className="status-badge unknown">
                            <i />
                            Không rõ
                          </span>
                        )}
                      </td>
                      <td className="lb-error-cell">
                        {backend.last_health_error || "Đang phản hồi bình thường"}
                      </td>
                      <td className="align-right">
                        {backend.node_id && (
                          <button
                            type="button"
                            className="btn-xs btn-outline lb-remove-btn"
                            onClick={() => void handleRemoveFromPool(backend)}
                            disabled={Boolean(actionBusy)}
                            title="Chuyển node này về Standalone (gỡ khỏi Load Balancer pool)"
                          >
                            <Trash2 size={12} /> Gỡ
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <LBPoolPickerModal
        key={isPickerOpen ? project.id : "picker-closed"}
        isOpen={isPickerOpen}
        projectName={project.name}
        eligibleNodes={eligibleActiveNodes}
        unavailableCount={unavailableNodes.length}
        busy={actionBusy === "add-node"}
        onClose={() => setIsPickerOpen(false)}
        onConfirmAdd={handleAddPoolItems}
      />
    </section>
  );
}
