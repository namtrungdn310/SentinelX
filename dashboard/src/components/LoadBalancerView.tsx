import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Globe,
  PauseCircle,
  Play,
  Plus,
  RefreshCw,
  Server,
  Settings2,
  ShieldAlert,
  Trash2,
  Zap,
} from "lucide-react";
import {
  defaultProjectLBConfig,
  fetchProjectLBStatus,
  setProjectLBBackendState,
  switchProjectLBAlgorithm,
  syncProjectLB,
} from "../api";
import { buildMockProjectLBStatus } from "../mockData";
import { healthLabels, nodeHealth } from "../presentation";
import type {
  LBAlgorithmType,
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
  isDemoMode: boolean;
  onOpenConfig: () => void;
  onOpenAddNode?: () => void;
  onUpdateProjectLB: (
    projectId: string,
    payload: { load_balancer: ProjectLBConfig },
  ) => Promise<Project | void>;
  onSyncProjectLocalLB?: (
    projectId: string,
    loadBalancer: ProjectLBConfig,
  ) => void;
  onUpdateNode: (
    nodeId: string,
    payload: {
      lb_role?: NodeLBRoleType;
      lb_backend_port?: number;
      lb_health_path?: string | null;
    },
  ) => Promise<Node | void>;
  onNotify?: (toast: SecurityToastPayload) => void;
}

const BACKEND_SLOT_HEIGHT = 104;
const BACKEND_SLOT_GAP = 12;
const TOPOLOGY_PAD_Y = 0;

export function LoadBalancerView({
  project,
  projectNodes,
  isDemoMode,
  onOpenConfig,
  onOpenAddNode,
  onUpdateProjectLB,
  onSyncProjectLocalLB,
  onUpdateNode,
  onNotify,
}: Props) {
  const headingId = useId();
  const [liveStatus, setLiveStatus] = useState<ProjectLBStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Interactive Demo Mode simulation state
  const [demoAutoFlow, setDemoAutoFlow] = useState(true);
  const [demoOverrides, setDemoOverrides] = useState<
    Record<string, Partial<LBBackendRuntime>>
  >({});
  const [activeTargetId, setActiveTargetId] = useState<string | null>(null);
  const rrCursorRef = useRef(0);

  // Quick-add existing standalone node into LB pool
  const standaloneNodes = useMemo(
    () => projectNodes.filter((n) => n.lb_role !== "lb_backend"),
    [projectNodes],
  );
  const [selectedAddNodeId, setSelectedAddNodeId] = useState<string>("");
  const [addPort, setAddPort] = useState<number>(8080);

  const effectiveAddNodeId = standaloneNodes.some(
    (n) => n.id === selectedAddNodeId,
  )
    ? selectedAddNodeId
    : (standaloneNodes[0]?.id ?? "");

  const lbEnabled = Boolean(project.load_balancer?.enabled);

  const loadLiveStatus = useCallback(
    async (silent = false) => {
      if (isDemoMode || !lbEnabled) return;
      if (!silent) setLoading(true);
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
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [isDemoMode, lbEnabled, project.id],
  );

  // Poll live status every 2.5s when enabled and connected
  useEffect(() => {
    if (isDemoMode || !lbEnabled) {
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
  }, [isDemoMode, lbEnabled, project.id]);

  const demoStatus = useMemo(
    () => buildMockProjectLBStatus(project, projectNodes, demoOverrides),
    [project, projectNodes, demoOverrides],
  );

  const status: ProjectLBStatus = isDemoMode
    ? demoStatus
    : lbEnabled && liveStatus?.project_id === project.id
      ? liveStatus
      : demoStatus;

  const nodeById = useMemo(
    () => new Map(projectNodes.map((n) => [n.id, n])),
    [projectNodes],
  );

  // Simulated request routing tick in Demo Mode to power live animation & counters
  const dispatchSimulatedRequests = useCallback(
    (count: number) => {
      if (!isDemoMode || !lbEnabled) return;
      setDemoOverrides((prev) => {
        const current = buildMockProjectLBStatus(project, projectNodes, prev);
        const routable = current.backends.filter(
          (b) => b.is_healthy && b.admin_enabled,
        );
        if (!routable.length) return prev;

        const next = { ...prev };
        let lastPickedUrl: string | null = null;
        const algo = current.algorithm;

        // Track mutable in_flight & totals across batch
        const inflightMap = new Map(routable.map((b) => [b.url, b.in_flight]));
        const totalMap = new Map(routable.map((b) => [b.url, b.total_requests]));

        for (let step = 0; step < count; step++) {
          let chosen: LBBackendRuntime;
          if (algo === "least_in_flight") {
            chosen = [...routable].sort(
              (a, b) => (inflightMap.get(a.url) ?? 0) - (inflightMap.get(b.url) ?? 0),
            )[0];
          } else {
            chosen = routable[rrCursorRef.current % routable.length];
            rrCursorRef.current += 1;
          }

          const nodeId = chosen.node_id ?? chosen.url;
          const nextTotal = (totalMap.get(chosen.url) ?? 0) + 1;
          // Simulate natural completion so in_flight stays realistic (1..6)
          const rawInflight = inflightMap.get(chosen.url) ?? 1;
          const nextInflight =
            count > 1
              ? Math.min(8, Math.max(1, rawInflight + 1))
              : (rawInflight % 5) + 1;

          inflightMap.set(chosen.url, nextInflight);
          totalMap.set(chosen.url, nextTotal);

          next[nodeId] = {
            ...(next[nodeId] ?? {}),
            total_requests: nextTotal,
            success_requests: nextTotal - (chosen.error_requests ?? 0),
            in_flight: nextInflight,
          };
          lastPickedUrl = chosen.url;
        }

        if (lastPickedUrl) {
          setActiveTargetId(lastPickedUrl);
        }
        return next;
      });
    },
    [isDemoMode, lbEnabled, project, projectNodes],
  );

  useEffect(() => {
    if (!isDemoMode || !lbEnabled || !demoAutoFlow) return;
    const timer = window.setInterval(() => {
      dispatchSimulatedRequests(1);
    }, 1100);
    return () => window.clearInterval(timer);
  }, [isDemoMode, lbEnabled, demoAutoFlow, dispatchSimulatedRequests]);

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

  const handleSwitchAlgorithm = async (algo: LBAlgorithmType) => {
    if (status.algorithm === algo || actionBusy) return;
    setActionBusy("algorithm");
    setError(null);
    const nextConfig: ProjectLBConfig = {
      ...(project.load_balancer ?? defaultProjectLBConfig()),
      enabled: true,
      algorithm: algo,
    };
    try {
      if (isDemoMode) {
        await onUpdateProjectLB(project.id, { load_balancer: nextConfig });
      } else {
        const res = await switchProjectLBAlgorithm(project.id, algo);
        setLiveStatus(res);
        if (onSyncProjectLocalLB) {
          onSyncProjectLocalLB(project.id, nextConfig);
        } else {
          await onUpdateProjectLB(project.id, { load_balancer: nextConfig });
        }
      }
      onNotify?.({
        id: `lb-algo-${Date.now()}`,
        type: "defense",
        title: "Đã chuyển thuật toán chia tải",
        message: `${project.name} đang dùng ${algo === "least_in_flight" ? "Least In-Flight" : "Round Robin"}.`,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không thể đổi thuật toán chia tải.",
      );
    } finally {
      setActionBusy(null);
    }
  };

  const handleSyncLB = async () => {
    if (actionBusy) return;
    setActionBusy("sync");
    setError(null);
    try {
      if (isDemoMode) {
        onNotify?.({
          id: `lb-sync-${Date.now()}`,
          type: "defense",
          title: "Đã đồng bộ cấu hình Pool",
          message: `Demo Mode đã cập nhật ${status.total_backends} backend cho ${project.name}.`,
        });
      } else {
        const res = await syncProjectLB(project.id);
        setLiveStatus(res);
        onNotify?.({
          id: `lb-sync-${Date.now()}`,
          type: "defense",
          title: res.reachable ? "Đã đồng bộ Load Balancer" : "Chưa kết nối được LB",
          message:
            res.sync_message ||
            `${res.routable_backends}/${res.total_backends} backend sẵn sàng.`,
        });
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Đồng bộ Load Balancer thất bại.",
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
      if (isDemoMode) {
        const routableOthers = status.backends.filter(
          (b) => b.url !== backend.url && b.is_healthy && b.admin_enabled,
        ).length;
        if (!nextEnabled && routableOthers === 0) {
          throw new Error(
            "Không thể tạm rút backend hoạt động cuối cùng (sẽ gây gián đoạn toàn cụm).",
          );
        }
        setDemoOverrides((prev) => ({
          ...prev,
          [backend.node_id!]: {
            ...(prev[backend.node_id!] ?? {}),
            admin_enabled: nextEnabled,
            in_flight: nextEnabled ? 1 : 0,
          },
        }));
      } else {
        const res = await setProjectLBBackendState(
          project.id,
          backend.node_id,
          nextEnabled,
        );
        setLiveStatus(res);
      }
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

  const handleSimulateDemoHealthFlip = (backend: LBBackendRuntime) => {
    if (!isDemoMode || !backend.node_id) return;
    const nextHealthy = !backend.is_healthy;
    setDemoOverrides((prev) => ({
      ...prev,
      [backend.node_id!]: {
        ...(prev[backend.node_id!] ?? {}),
        is_healthy: nextHealthy,
        health_state: nextHealthy ? "healthy" : "unhealthy",
        in_flight: nextHealthy ? 1 : 0,
        consecutive_failures: nextHealthy
          ? 0
          : status.health_check.failure_threshold,
        consecutive_successes: nextHealthy
          ? status.health_check.success_threshold
          : 0,
        last_health_error: nextHealthy
          ? null
          : `GET ${backend.health_path || "/health"} timeout (simulated)`,
      },
    }));
  };

  const handleAssignNodeToPool = async () => {
    if (!effectiveAddNodeId || actionBusy) return;
    setActionBusy("add-node");
    setError(null);
    try {
      await onUpdateNode(effectiveAddNodeId, {
        lb_role: "lb_backend",
        lb_backend_port: Math.min(65535, Math.max(1, Number(addPort) || 8080)),
      });
      if (!isDemoMode) {
        await loadLiveStatus(true);
      }
      onNotify?.({
        id: `lb-add-node-${Date.now()}`,
        type: "defense",
        title: "Đã thêm backend vào Load Balancer",
        message: `Cụm ${project.name} đã tự động đồng bộ máy chủ mới vào pool.`,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không thêm được máy chủ vào pool.",
      );
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
      if (!isDemoMode) {
        await loadLiveStatus(true);
      }
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
            <span className="lb-sync-chip">
              {!lbEnabled
                ? "Chế độ tạm dừng chia tải"
                : status.sync_status === "synced"
                  ? "Pool đã đồng bộ"
                  : status.sync_message || status.sync_status}
            </span>
          </div>
          {lbEnabled && status.sync_message && status.sync_status !== "synced" && (
            <p className="lb-sync-warning">{status.sync_message}</p>
          )}
        </div>

        <div className="lb-header-actions">
          <div
            className="lb-algo-segmented"
            role="group"
            aria-label="Chọn thuật toán Load Balancer"
          >
            <button
              type="button"
              className={status.algorithm === "round_robin" ? "active" : ""}
              onClick={() => void handleSwitchAlgorithm("round_robin")}
              disabled={!lbEnabled || Boolean(actionBusy)}
            >
              Round Robin
            </button>
            <button
              type="button"
              className={status.algorithm === "least_in_flight" ? "active" : ""}
              onClick={() => void handleSwitchAlgorithm("least_in_flight")}
              disabled={!lbEnabled || Boolean(actionBusy)}
            >
              Least In-Flight
            </button>
          </div>

          <button
            type="button"
            className="btn btn-outline"
            onClick={() => void handleSyncLB()}
            disabled={!lbEnabled || Boolean(actionBusy) || loading}
          >
            <RefreshCw
              size={14}
              className={actionBusy === "sync" || loading ? "lb-spin" : ""}
            />
            Đồng bộ
          </button>

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

          {isDemoMode && (
            <div className="lb-demo-controls">
              <button
                type="button"
                className={`btn btn-outline ${demoAutoFlow ? "lb-auto-on" : ""}`}
                onClick={() => setDemoAutoFlow((v) => !v)}
                disabled={!lbEnabled}
              >
                {demoAutoFlow ? (
                  <>
                    <PauseCircle size={14} /> Dừng mô phỏng
                  </>
                ) : (
                  <>
                    <Play size={14} /> Tự động mô phỏng
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => dispatchSimulatedRequests(10)}
                disabled={!lbEnabled || status.routable_backends === 0}
              >
                <Zap size={14} /> Gửi burst 10 req
              </button>
            </div>
          )}
        </div>

        {backends.length === 0 ? (
          <div className="lb-no-backends">
            <Server size={24} />
            <div>
              <strong>Pool hiện chưa có Backend Server nào</strong>
              <p>
                {standaloneNodes.length > 0
                  ? "Chọn máy chủ có sẵn ở mục bên dưới để thêm ngay vào Load Balancer pool."
                  : "Dự án chưa có máy chủ nào. Đăng ký máy chủ mới với vai trò Backend nhận tải LB."}
              </p>
            </div>
            {standaloneNodes.length === 0 && onOpenAddNode && (
              <button
                type="button"
                className="btn btn-primary"
                style={{ marginLeft: "auto" }}
                onClick={onOpenAddNode}
              >
                <Plus size={14} /> Thêm máy chủ
              </button>
            )}
          </div>
        ) : (
          <div className="lb-flow-canvas">
            <div className="lb-flow-grid">
              {/* Column 1: Client Ingress */}
              <div className="lb-stage-col lb-ingress-col">
                <div className="lb-node-card lb-ingress-card">
                  <span className="lb-card-eyebrow">CLIENT TRAFFIC</span>
                  <strong>Ingress Clients</strong>
                  <small>HTTP Reverse Proxy</small>
                  <div className="lb-mini-stat">
                    <span>Tổng request</span>
                    <b className="font-mono">
                      {status.total_requests.toLocaleString("vi-VN")}
                    </b>
                  </div>
                </div>
              </div>

              {/* Column 2: SVG Connector 1 (Ingress -> LB Hub) */}
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
                    const isActiveTarget =
                      lbEnabled && activeTargetId === backend.url;
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
                  const stateTone = !lbEnabled
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
                        lbEnabled && activeTargetId === backend.url ? "is-target" : ""
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
                          {isDemoMode && backend.node_id && (
                            <button
                              type="button"
                              className="btn-xs btn-outline"
                              title="Mô phỏng mất kết nối /health hoặc phục hồi backend này"
                              onClick={() => handleSimulateDemoHealthFlip(backend)}
                            >
                              <Activity size={12} />
                              {backend.is_healthy ? "Test Lỗi" : "Phục hồi"}
                            </button>
                          )}
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
        </div>

        {/* Always show Pool assignment bar so user sees how to add servers */}
        <div className="lb-add-existing-bar">
          {standaloneNodes.length > 0 ? (
            <>
              <div className="lb-add-existing-label">
                <Plus size={15} />
                <span>Thêm máy chủ đã đăng ký vào LB Pool:</span>
              </div>
              <div className="lb-add-existing-controls">
                <select
                  className="form-input"
                  aria-label="Chọn máy chủ đưa vào Load Balancer"
                  value={effectiveAddNodeId}
                  onChange={(e) => setSelectedAddNodeId(e.target.value)}
                  disabled={Boolean(actionBusy)}
                >
                  {standaloneNodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname} ({n.ip_address})
                    </option>
                  ))}
                </select>
                <label className="lb-inline-port">
                  <span>Cổng dịch vụ:</span>
                  <input
                    type="number"
                    className="form-input font-mono"
                    min={1}
                    max={65535}
                    value={addPort}
                    onChange={(e) =>
                      setAddPort(
                        Math.max(1, Math.min(65535, Number(e.target.value) || 8080)),
                      )
                    }
                    disabled={Boolean(actionBusy)}
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void handleAssignNodeToPool()}
                  disabled={!effectiveAddNodeId || Boolean(actionBusy)}
                >
                  <Plus size={14} /> Thêm vào Pool
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="lb-add-existing-label lb-add-existing-empty">
                <Server size={15} />
                <span>
                  {projectNodes.length === 0
                    ? "Dự án chưa có máy chủ nào. Đăng ký máy chủ trước rồi thêm vào LB Pool tại đây."
                    : "Tất cả máy chủ trong dự án đều đang nằm trong LB Pool."}
                </span>
              </div>
              {onOpenAddNode && (
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={onOpenAddNode}
                >
                  <Plus size={14} /> Đăng ký thêm máy chủ
                </button>
              )}
            </>
          )}
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
    </section>
  );
}
