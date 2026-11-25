import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchDetectionEvents,
  fetchDefenseActions,
  fetchIncidents,
  fetchNodeMetrics,
  fetchNodes,
  fetchProjects,
  seedDefaultPolicies,
  createProject as apiCreateProject,
  updateProject as apiUpdateProject,
  updateNode as apiUpdateNode,
} from "./api";
import { mergeEvents } from "./events";
import type {
  DefenseAction,
  Incident,
  MetricSample,
  Node,
  NodeLBRoleType,
  PresetProfileType,
  Project,
  ProjectLBConfig,
  RealtimeMessage,
} from "./types";
import { useWebSocket } from "./useWebSocket";
import { mergeSamples } from "./telemetry";
import type { SecurityToastPayload } from "./components/SecurityToast";

interface Snapshot {
  projects: Project[];
  nodes: Node[];
  events: RealtimeMessage[];
  notableEvents: RealtimeMessage[];
  histories: Record<string, MetricSample[]>;
}

const EMPTY_SNAPSHOT: Snapshot = {
  projects: [],
  nodes: [],
  events: [],
  notableEvents: [],
  histories: {},
};

export function useInfrastructure() {
  const [snapshot, setSnapshot] = useState<Snapshot>(EMPTY_SNAPSHOT);
  const [isRefreshing, setIsRefreshing] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [chartRequest, setChartRequest] = useState<{
    nodeId: string;
    loading: boolean;
    error: string | null;
  } | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentRevision, setIncidentRevision] = useState(0);
  const [defenseActions, setDefenseActions] = useState<DefenseAction[]>([]);
  const activeBlocksCount = defenseActions.filter(
    (a) => a.status === "APPLIED" && a.action_type === "BLOCK_IP_NFTABLES",
  ).length;
  const [securityToasts, setSecurityToasts] = useState<SecurityToastPayload[]>([]);

  const requestId = useRef(0);
  const historyRequestId = useRef(0);

  const pushSecurityToast = useCallback((toast: SecurityToastPayload) => {
    setSecurityToasts((previous) => {
      const filtered =
        toast.type === "settings"
          ? previous.filter((item) => item.type !== "settings")
          : previous;
      return [...filtered, toast].slice(-3);
    });
  }, []);

  const dismissSecurityToast = useCallback((toastId?: string) => {
    if (!toastId) {
      setSecurityToasts([]);
      return;
    }
    setSecurityToasts((previous) => previous.filter((item) => item.id !== toastId));
  }, []);

  const handleMessage = useCallback(
    (message: RealtimeMessage) => {
      if (message.event === "pong") return;

      if (message.event === "incident_alert") {
        setIncidentRevision((r) => r + 1);
        void fetchIncidents({ limit: 100 })
          .then((items) => setIncidents(items))
          .catch(() => null);
        pushSecurityToast({
          id: `toast-inc-${Date.now()}`,
          type: "incident",
          title: "Phát hiện sự cố an ninh mới",
          message: String(
            message.data.summary ||
              message.data.title ||
              "Tấn công bất thường được ghi nhận",
          ),
          attackerIp:
            typeof message.data.attacker_ip === "string"
              ? message.data.attacker_ip
              : null,
          severity:
            typeof message.data.severity === "string"
              ? message.data.severity
              : "CRITICAL",
          targetView: "incidents",
        });
      } else if (message.event === "incident_update") {
        setIncidentRevision((r) => r + 1);
        const updatedId = typeof message.data.id === "string" ? message.data.id : null;
        if (updatedId) {
          setIncidents((prev) =>
            prev.map((item) =>
              item.id === updatedId
                ? {
                    ...item,
                    status:
                      typeof message.data.status === "string"
                        ? (message.data.status as Incident["status"])
                        : item.status,
                    severity:
                      typeof message.data.severity === "string"
                        ? (message.data.severity as Incident["severity"])
                        : item.severity,
                    summary:
                      typeof message.data.summary === "string"
                        ? message.data.summary
                        : item.summary,
                    attacker_ip:
                      typeof message.data.attacker_ip === "string"
                        ? message.data.attacker_ip
                        : item.attacker_ip,
                    resolved_at:
                      typeof message.data.resolved_at === "string"
                        ? message.data.resolved_at
                        : message.data.resolved_at === null
                          ? null
                          : item.resolved_at,
                    defense_status:
                      message.data.defense_status === "DELIVERY_FAILED" ||
                      message.data.defense_status === "EXECUTION_FAILED"
                        ? message.data.defense_status
                        : message.data.status && message.data.status !== "DETECTED"
                          ? null
                          : item.defense_status,
                  }
                : item,
            ),
          );
        }
      } else if (message.event === "defense_action_created") {
        setIncidentRevision((r) => r + 1);
        void fetchDefenseActions({ limit: 100 })
          .then((items) => setDefenseActions(items))
          .catch(() => null);
        const actionType = String(message.data.action_type ?? "");
        const actionStatus = String(message.data.status ?? "PENDING");
        const targetIp =
          typeof message.data.target_ip === "string" ? message.data.target_ip : null;
        if (actionType === "UNBLOCK_IP_NFTABLES") {
          pushSecurityToast({
            id: `toast-def-${Date.now()}`,
            type: "defense",
            title: "Đã tạo lệnh gỡ chặn IP",
            message: "Đang chờ Agent gỡ quy tắc trên nftables",
            attackerIp: targetIp,
            targetView: "defense",
          });
        } else if (actionType === "RESTART_SERVICE" || actionType === "CLEAR_OS_CACHE") {
          pushSecurityToast({
            id: `toast-def-${Date.now()}`,
            type: "defense",
            title: "Đã xếp hàng lệnh khôi phục",
            message: "Đang chờ Agent thực thi khôi phục dịch vụ",
            targetView: "incidents",
          });
        } else {
          pushSecurityToast({
            id: `toast-def-${Date.now()}`,
            type: "defense",
            title: actionStatus === "APPLIED" ? "Tường lửa đã kích hoạt" : "Lệnh tường lửa mới",
            message:
              actionStatus === "APPLIED"
                ? "Đã chặn địa chỉ IP nguồn tấn công"
                : "Đang chờ Agent tải lệnh chặn IP",
            attackerIp: targetIp,
            targetView: "defense",
          });
        }
      } else if (message.event === "defense_action_updated") {
        setIncidentRevision((r) => r + 1);
        void fetchDefenseActions({ limit: 100 })
          .then((items) => setDefenseActions(items))
          .catch(() => null);
        const actionType = String(message.data.action_type ?? "");
        const actionStatus = String(message.data.status ?? "");
        if (actionStatus === "APPLIED" && actionType === "BLOCK_IP_NFTABLES") {
          pushSecurityToast({
            id: `toast-def-ack-${Date.now()}`,
            type: "defense",
            title: "Tường lửa đã kích hoạt",
            message: "Agent đã áp dụng lệnh chặn IP vào nftables",
            attackerIp:
              typeof message.data.target_ip === "string" ? message.data.target_ip : null,
            targetView: "defense",
          });
        }
      } else if (
        message.event === "defense_action_reverted" ||
        message.event === "recovery_completed"
      ) {
        setIncidentRevision((r) => r + 1);
        void fetchDefenseActions({ limit: 100 })
          .then((items) => setDefenseActions(items))
          .catch(() => null);
      }

      if (message.event === "network_feature_update") return;

      setSnapshot((previous) => {
        const { node_id: nodeId, samples } = message.data;
        const latest =
          nodeId && samples?.length
            ? mergeSamples(previous.histories[nodeId] ?? [], samples).at(-1)
            : undefined;
        const nodes = previous.nodes.map((node) => {
          if (node.id !== nodeId) return node;
          if (message.event === "metric_update" && latest) {
            return {
              ...node,
              status: "online" as const,
              last_seen:
                typeof message.data.received_at === "string"
                  ? message.data.received_at
                  : message.timestamp,
              latestCpu: latest.cpu_percent,
              latestMemory: latest.memory_percent,
              latestDisk: latest.disk_percent ?? undefined,
              latestRxBytes: latest.network_rx_bytes ?? undefined,
              latestTxBytes: latest.network_tx_bytes ?? undefined,
            };
          }
          const rawStatus = message.data.status;
          if (
            message.event === "node_status" &&
            (rawStatus === "online" || rawStatus === "offline" || rawStatus === "unenrolled")
          ) {
            const nextStatus = rawStatus as Node["status"];
            return {
              ...node,
              status: nextStatus,
              last_seen:
                typeof message.data.last_seen === "string"
                  ? message.data.last_seen
                  : node.last_seen,
            };
          }
          return node;
        });
        const isMetricUpdate = message.event === "metric_update";
        return {
          ...previous,
          nodes,
          events: mergeEvents([message], previous.events),
          notableEvents: isMetricUpdate
            ? previous.notableEvents
            : mergeEvents([message], previous.notableEvents).slice(0, 50),
          histories:
            nodeId && samples?.length
              ? {
                  ...previous.histories,
                  [nodeId]: mergeSamples(previous.histories[nodeId] ?? [], samples),
                }
              : previous.histories,
        };
      });
    },
    [pushSecurityToast],
  );

  const { isConnected, latencyMs } = useWebSocket({
    onMessage: handleMessage,
    enabled: true,
  });

  const loadData = useCallback(async (quiet = false) => {
    const ticket = ++requestId.current;
    setIsRefreshing(true);
    setConnectionError(null);
    try {
      const [projects, nodes] = await Promise.all([fetchProjects(), fetchNodes()]);
      if (ticket !== requestId.current) return;
      const [metrics, detections, loadedIncidents, loadedDefenseActions] = await Promise.all([
        Promise.allSettled(nodes.map((node) => fetchNodeMetrics(node.id, 1))),
        fetchDetectionEvents().catch(() => null),
        fetchIncidents({ limit: 100 }).catch(() => null),
        fetchDefenseActions({ limit: 100 }).catch(() => null),
      ]);
      if (ticket !== requestId.current) return;

      if (loadedIncidents !== null) {
        setIncidents(loadedIncidents);
      }
      if (loadedDefenseActions !== null) {
        setDefenseActions(loadedDefenseActions);
      }

      const histories: Record<string, MetricSample[]> = {};
      const hydratedNodes = nodes.map((node, index) => {
        const result = metrics[index];
        const samples = result.status === "fulfilled" ? result.value.samples : [];
        histories[node.id] = samples;
        const latest = samples.at(0);
        return latest
          ? {
              ...node,
              latestCpu: latest.cpu_percent,
              latestMemory: latest.memory_percent,
              latestDisk: latest.disk_percent ?? undefined,
              latestRxBytes: latest.network_rx_bytes ?? undefined,
              latestTxBytes: latest.network_tx_bytes ?? undefined,
            }
          : node;
      });
      setSnapshot((previous) => ({
        projects,
        nodes: hydratedNodes,
        histories: Object.fromEntries(
          nodes.map((node) => [
            node.id,
            mergeSamples(previous.histories[node.id] ?? [], histories[node.id]),
          ]),
        ),
        events: mergeEvents(detections ?? [], previous.events),
        notableEvents: mergeEvents(detections ?? [], previous.notableEvents).slice(0, 50),
      }));
      setHasLoadedOnce(true);
      if (detections === null || loadedIncidents === null || loadedDefenseActions === null) {
        setConnectionError(
          "Đã kết nối Controller nhưng một phần dữ liệu bảo mật chưa tải được. Nhấn Thử lại để đồng bộ.",
        );
      }
    } catch (err) {
      if (ticket === requestId.current && !quiet) {
        const detail = err instanceof Error ? ` (${err.message})` : "";
        setConnectionError(
          `Chưa thể kết nối Controller.${detail} Kiểm tra dịch vụ backend rồi thử lại.`,
        );
      }
    } finally {
      if (ticket === requestId.current) setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  useEffect(() => {
    if (!isConnected) return;
    let disposed = false;
    void Promise.allSettled([
      fetchDetectionEvents(),
      fetchNodes(),
      fetchIncidents({ limit: 100 }),
      fetchDefenseActions({ limit: 100 }),
    ]).then(([detRes, nodesRes, incRes, defRes]) => {
      if (disposed) return;
      if (incRes.status === "fulfilled") {
        setIncidents(incRes.value);
      }
      if (defRes.status === "fulfilled") {
        setDefenseActions(defRes.value);
      }
      setSnapshot((previous) => ({
        ...previous,
        nodes:
          nodesRes.status === "fulfilled"
            ? nodesRes.value.map((fresh) => {
                const prevNode = previous.nodes.find((n) => n.id === fresh.id);
                return prevNode
                  ? {
                      ...fresh,
                      latestCpu: prevNode.latestCpu,
                      latestMemory: prevNode.latestMemory,
                      latestDisk: prevNode.latestDisk,
                      latestRxBytes: prevNode.latestRxBytes,
                      latestTxBytes: prevNode.latestTxBytes,
                    }
                  : fresh;
              })
            : previous.nodes,
        events:
          detRes.status === "fulfilled"
            ? mergeEvents(detRes.value, previous.events)
            : previous.events,
        notableEvents:
          detRes.status === "fulfilled"
            ? mergeEvents(detRes.value, previous.notableEvents).slice(0, 50)
            : previous.notableEvents,
      }));
    });
    return () => {
      disposed = true;
    };
  }, [isConnected]);

  const cancelRequests = useCallback(() => {
    requestId.current++;
    historyRequestId.current++;
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "r" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        void loadData();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      cancelRequests();
    };
  }, [loadData, cancelRequests]);

  const loadHistory = useCallback(async (nodeId: string, limit: number) => {
    const ticket = ++historyRequestId.current;
    setChartRequest({ nodeId, loading: true, error: null });
    try {
      const response = await fetchNodeMetrics(nodeId, limit);
      if (ticket !== historyRequestId.current) return;
      setSnapshot((previous) => ({
        ...previous,
        histories: {
          ...previous.histories,
          [nodeId]: mergeSamples(previous.histories[nodeId] ?? [], response.samples),
        },
      }));
      setChartRequest(null);
    } catch (err) {
      if (ticket === historyRequestId.current) {
        setChartRequest({
          nodeId,
          loading: false,
          error:
            err instanceof Error
              ? err.message
              : "Không tải được lịch sử mẫu dữ liệu. Vui lòng thử lại.",
        });
      }
    }
  }, []);

  const syncProjectDefenseActions = useCallback(
    (nodeIds: string[], items: DefenseAction[]) => {
      const idSet = new Set(nodeIds);
      setDefenseActions((prev) => {
        const others = prev.filter((act) => !idSet.has(act.node_id));
        return [...items, ...others];
      });
    },
    [],
  );

  const syncProjectIncidents = useCallback(
    (projectId: string | null, items: Incident[]) => {
      setIncidents((prev) => {
        if (!projectId) return items;
        const others = prev.filter((inc) => inc.project_id !== projectId);
        return [...items, ...others];
      });
    },
    [],
  );

  const syncNodeSettings = useCallback(
    (nodeIds: string[], profile: PresetProfileType, updatedAt: string) => {
      const idSet = new Set(nodeIds);
      setSnapshot((prev) => ({
        ...prev,
        nodes: prev.nodes.map((n) =>
          idSet.has(n.id)
            ? {
                ...n,
                agent_capabilities: {
                  ...(n.agent_capabilities ?? {}),
                  settings: {
                    active_profile: profile,
                    updated_at: updatedAt,
                    updated_by: "operator@sentinelx.local",
                  },
                },
              }
            : n,
        ),
      }));
    },
    [],
  );

  const addNode = (node: Node) =>
    setSnapshot((previous) => ({
      ...previous,
      nodes: [node, ...previous.nodes],
    }));

  const createProject = async (
    name: string,
    description?: string,
    loadBalancer?: ProjectLBConfig,
  ): Promise<Project> => {
    const created = await apiCreateProject(name, description, loadBalancer);
    await seedDefaultPolicies(created.id).catch(() => null);
    setSnapshot((prev) => ({
      ...prev,
      projects: [...prev.projects, created],
    }));
    return created;
  };

  const updateProject = async (
    projectId: string,
    payload: { name?: string; description?: string | null; load_balancer?: ProjectLBConfig },
  ): Promise<Project> => {
    const updated = await apiUpdateProject(projectId, payload);
    setSnapshot((prev) => ({
      ...prev,
      projects: prev.projects.map((p) => (p.id === projectId ? updated : p)),
    }));
    return updated;
  };

  const updateNode = async (
    nodeId: string,
    payload: {
      hostname?: string;
      lb_role?: NodeLBRoleType;
      lb_backend_port?: number;
      lb_health_path?: string | null;
    },
  ): Promise<Node> => {
    const updated = await apiUpdateNode(nodeId, payload);
    setSnapshot((prev) => ({
      ...prev,
      nodes: prev.nodes.map((n) => (n.id === nodeId ? { ...n, ...updated } : n)),
    }));
    return updated;
  };

  return {
    ...snapshot,
    isRefreshing,
    hasLoadedOnce,
    connectionError,
    chartRequest,
    isConnected,
    latencyMs,
    incidents,
    incidentRevision,
    defenseActions,
    activeBlocksCount,
    securityToasts,
    pushSecurityToast,
    dismissSecurityToast,
    loadData: () => loadData(),
    loadHistory,
    addNode,
    createProject,
    updateProject,
    updateNode,
    syncProjectIncidents,
    syncProjectDefenseActions,
    syncNodeSettings,
  };
}
