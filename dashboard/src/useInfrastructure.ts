import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchDetectionEvents,
  fetchDefenseActions,
  fetchIncidents,
  fetchNodeMetrics,
  fetchNodes,
  fetchProjects,
  createProject as apiCreateProject,
} from "./api";
import { mergeEvents } from "./events";
import {
  generateMockTelemetryHistory,
  MOCK_INITIAL_EVENTS,
  MOCK_INCIDENTS,
  MOCK_DEFENSE_ACTIONS,
  MOCK_NODES,
  MOCK_PROJECTS,
} from "./mockData";
import type { MetricSample, Node, Project, RealtimeMessage } from "./types";
import { useWebSocket } from "./useWebSocket";
import { mergeSamples } from "./telemetry";
import type { SecurityToastPayload } from "./components/SecurityToast";

interface Snapshot {
  projects: Project[];
  nodes: Node[];
  events: RealtimeMessage[];
  notableEvents: RealtimeMessage[];
  histories: Record<string, MetricSample[]>;
  isDemoMode: boolean;
}

function demoSnapshot(): Snapshot {
  return {
    projects: MOCK_PROJECTS,
    nodes: MOCK_NODES,
    events: MOCK_INITIAL_EVENTS,
    notableEvents: MOCK_INITIAL_EVENTS.filter(
      (event) => event.event !== "metric_update" && event.event !== "pong",
    ),
    histories: Object.fromEntries(
      MOCK_NODES.map((node) => [
        node.id,
        node.status === "online" ? generateMockTelemetryHistory(node, 120) : [],
      ]),
    ),
    isDemoMode: true,
  };
}

export function useInfrastructure() {
  const [snapshot, setSnapshot] = useState<Snapshot>(demoSnapshot);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [chartRequest, setChartRequest] = useState<{
    nodeId: string;
    loading: boolean;
    error: string | null;
  } | null>(null);
  const [activeIncidentsCount, setActiveIncidentsCount] = useState<number>(() => {
    return MOCK_INCIDENTS.filter((i) => i.status !== "RESOLVED").length;
  });
  const [activeBlocksCount, setActiveBlocksCount] = useState<number>(() => {
    return MOCK_DEFENSE_ACTIONS.filter(
      (a) => a.status === "APPLIED" && a.action_type === "BLOCK_IP_NFTABLES",
    ).length;
  });
  const [securityToast, setSecurityToast] = useState<SecurityToastPayload | null>(null);

  const requestId = useRef(0);
  const historyRequestId = useRef(0);
  const modeRef = useRef(true);
  const demoTickRef = useRef(0);

  const dismissSecurityToast = useCallback(() => {
    setSecurityToast(null);
  }, []);

  const handleMessage = useCallback((message: RealtimeMessage) => {
    // Ping/Pong check
    if (message.event === "pong") return;

    // In live mode, handle security events
    if (!modeRef.current) {
      if (message.event === "incident_alert") {
        setActiveIncidentsCount((c) => c + 1);
        setSecurityToast({
          id: `toast-inc-${Date.now()}`,
          type: "incident",
          title: "Phát hiện sự cố an ninh mới",
          message: String(message.data.summary || message.data.title || "Tấn công bất thường được ghi nhận"),
          attackerIp: typeof message.data.attacker_ip === "string" ? message.data.attacker_ip : null,
          severity: typeof message.data.severity === "string" ? message.data.severity : "CRITICAL",
          targetView: "incidents",
        });
      } else if (message.event === "incident_update") {
        if (message.data.status === "RESOLVED") {
          setActiveIncidentsCount((c) => Math.max(0, c - 1));
        }
      } else if (message.event === "defense_action_created") {
        setActiveBlocksCount((c) => c + 1);
        setSecurityToast({
          id: `toast-def-${Date.now()}`,
          type: "defense",
          title: "Tường lửa nftables đã kích hoạt",
          message: `Đã khóa địa chỉ IP tại bảng inet sentinelx (DROP)`,
          attackerIp: typeof message.data.target_ip === "string" ? message.data.target_ip : null,
          targetView: "defense",
        });
      } else if (
        message.event === "defense_action_reverted" ||
        message.event === "recovery_completed"
      ) {
        setActiveBlocksCount((c) => Math.max(0, c - 1));
      }
    }

    if (modeRef.current || message.event === "network_feature_update") return;

    setSnapshot((previous) => {
      const { node_id: nodeId, samples } = message.data;
      const latest = nodeId && samples?.length ? mergeSamples(previous.histories[nodeId] ?? [], samples).at(-1) : undefined;
      const nodes = previous.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        if (message.event === "metric_update" && latest)
          return {
            ...node,
            latestCpu: latest.cpu_percent,
            latestMemory: latest.memory_percent,
            latestDisk: latest.disk_percent ?? undefined,
            latestRxBytes: latest.network_rx_bytes ?? undefined,
            latestTxBytes: latest.network_tx_bytes ?? undefined,
          };
        const status = message.data.status;
        if (
          message.event === "node_status" &&
          ["online", "offline", "unenrolled", "degraded"].includes(
            String(status),
          )
        ) {
          return { ...node, status: status as Node["status"] };
        }
        return node;
      });
      return {
        ...previous,
        nodes,
        events: mergeEvents([message], previous.events),
        notableEvents:
          message.event === "metric_update"
            ? previous.notableEvents
            : mergeEvents([message], previous.notableEvents).slice(0, 20),
        histories:
          nodeId && samples?.length
            ? {
                ...previous.histories,
                [nodeId]: mergeSamples(
                  previous.histories[nodeId] ?? [],
                  samples,
                ),
              }
            : previous.histories,
      };
    });
  }, []);

  const { isConnected, latencyMs } = useWebSocket({
    onMessage: handleMessage,
    enabled: !snapshot.isDemoMode,
  });

  const loadData = useCallback(async (quiet = false) => {
    const ticket = ++requestId.current;
    setIsRefreshing(true);
    setConnectionError(null);
    try {
      const [projects, nodes] = await Promise.all([
        fetchProjects(),
        fetchNodes(),
      ]);
      if (ticket !== requestId.current) return;
      const [metrics, detections, incidents, defenseActions] = await Promise.all([
        Promise.allSettled(nodes.map((node) => fetchNodeMetrics(node.id, 1))),
        fetchDetectionEvents().catch(() => null),
        fetchIncidents({ limit: 100 }).catch(() => []),
        fetchDefenseActions({ status: "APPLIED", limit: 100 }).catch(() => []),
      ]);
      if (ticket !== requestId.current) return;

      setActiveIncidentsCount(incidents.filter((i) => i.status !== "RESOLVED").length);
      setActiveBlocksCount(
        defenseActions.filter(
          (a) => a.status === "APPLIED" && a.action_type === "BLOCK_IP_NFTABLES",
        ).length,
      );

      const histories: Record<string, MetricSample[]> = {};
      const hydratedNodes = nodes.map((node, index) => {
        const result = metrics[index];
        const samples =
          result.status === "fulfilled" ? result.value.samples : [];
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
      const wasDemoMode = modeRef.current;
      modeRef.current = false;
      setSnapshot((previous) => ({
        projects,
        nodes: hydratedNodes,
        histories: Object.fromEntries(
          nodes.map((node) => [
            node.id,
            mergeSamples(
              wasDemoMode ? [] : (previous.histories[node.id] ?? []),
              histories[node.id],
            ),
          ]),
        ),
        events: mergeEvents(detections ?? [], wasDemoMode ? [] : previous.events),
        notableEvents: mergeEvents(detections ?? [], wasDemoMode ? [] : previous.notableEvents).slice(0, 20),
        isDemoMode: false,
      }));
      if (detections === null) setConnectionError("Đã kết nối Controller nhưng chưa tải được lịch sử cảnh báo. Thử làm mới.");
    } catch {
      if (ticket === requestId.current && !quiet)
        setConnectionError(
          "Chưa thể kết nối Controller. Kiểm tra địa chỉ API và trạng thái dịch vụ, rồi thử lại.",
        );
    } finally {
      if (ticket === requestId.current) setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!isConnected || snapshot.isDemoMode) return;
    let disposed = false;
    void fetchDetectionEvents().then((events) => {
      if (disposed || modeRef.current) return;
      setSnapshot((previous) => ({
        ...previous,
        events: mergeEvents(events, previous.events),
        notableEvents: mergeEvents(events, previous.notableEvents).slice(0, 20),
      }));
    });
    return () => {
      disposed = true;
    };
  }, [isConnected, snapshot.isDemoMode]);

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

  // Demo mode real-time simulation
  useEffect(() => {
    if (!snapshot.isDemoMode) return;
    const interval = window.setInterval(() => {
      setSnapshot((previous) => {
        if (!previous.isDemoMode) return previous;
        demoTickRef.current += 1;
        const now = new Date().toISOString();
        const histories = { ...previous.histories };
        const nodes = previous.nodes.map((node) => {
          if (node.status !== "online") return node;
          const cpu =
            Math.round(
              Math.max(
                8,
                Math.min(
                  97,
                  (node.latestCpu ?? 30) + (Math.random() - 0.5) * 4,
                ),
              ) * 10,
            ) / 10;
          const memory =
            Math.round(
              Math.max(
                15,
                Math.min(98, (node.latestMemory ?? 50) + (Math.random() - 0.5)),
              ) * 10,
            ) / 10;
          const sample: MetricSample = {
            observed_at: now,
            cpu_percent: cpu,
            memory_percent: memory,
            disk_percent: node.latestDisk ?? null,
            network_rx_bytes: Math.round(250000 + Math.random() * 500000),
            network_tx_bytes: Math.round(150000 + Math.random() * 300000),
          };
          histories[node.id] = [
            ...(histories[node.id] ?? []).slice(-119),
            sample,
          ];
          return {
            ...node,
            latestCpu: cpu,
            latestMemory: memory,
            latestRxBytes: sample.network_rx_bytes!,
            latestTxBytes: sample.network_tx_bytes!,
            last_seen: now,
          };
        });
        const active = nodes.filter((node) => node.status === "online");
        const eventNode =
          active[Math.floor(Date.now() / 2400) % Math.max(1, active.length)];
        const event: RealtimeMessage | null = eventNode
          ? {
              event: "metric_update",
              timestamp: now,
              data: {
                node_id: eventNode.id,
                samples: histories[eventNode.id].slice(-1),
                received_at: now,
              },
            }
          : null;

        let newEvents = event ? [event, ...previous.events].slice(0, 50) : previous.events;
        let newNotable = previous.notableEvents;

        // Every 8 ticks (~19.2s), generate a simulated security event in Demo Mode
        if (demoTickRef.current % 8 === 0 && eventNode) {
          const isAttack = demoTickRef.current % 16 === 0;
          const secEvent: RealtimeMessage = isAttack
            ? {
                event: "incident_alert",
                timestamp: now,
                data: {
                  id: `inc-demo-${Date.now()}`,
                  title: "SYN Flood vượt ngưỡng cảnh báo (750 pps)",
                  severity: "CRITICAL",
                  attacker_ip: "198.51.100.19",
                  node_id: eventNode.id,
                  summary: "Phát hiện bão gói tin TCP SYN tấn công cổng web 443",
                },
              }
            : {
                event: "defense_action_created",
                timestamp: now,
                data: {
                  id: `def-demo-${Date.now()}`,
                  action_type: "BLOCK_IP_NFTABLES",
                  target_ip: "198.51.100.19",
                  node_id: eventNode.id,
                  duration_seconds: 1800,
                },
              };

          newEvents = [secEvent, ...newEvents].slice(0, 50);
          newNotable = [secEvent, ...newNotable].slice(0, 20);

          if (isAttack) {
            setActiveIncidentsCount((c) => c + 1);
            setSecurityToast({
              id: `toast-demo-${Date.now()}`,
              type: "incident",
              title: "Phát hiện sự cố an ninh mới",
              message: "SYN Flood vượt ngưỡng cảnh báo (750 pps)",
              attackerIp: "198.51.100.19",
              severity: "CRITICAL",
              targetView: "incidents",
            });
          } else {
            setActiveBlocksCount((c) => c + 1);
            setSecurityToast({
              id: `toast-demo-${Date.now()}`,
              type: "defense",
              title: "Tường lửa nftables đã kích hoạt",
              message: "Đã khóa địa chỉ IP tại bảng inet sentinelx (DROP)",
              attackerIp: "198.51.100.19",
              targetView: "defense",
            });
          }
        }

        return {
          ...previous,
          nodes,
          histories,
          events: newEvents,
          notableEvents: newNotable,
        };
      });
    }, 2400);
    return () => window.clearInterval(interval);
  }, [snapshot.isDemoMode]);

  const loadHistory = useCallback(async (nodeId: string, limit: number) => {
    if (modeRef.current) return;
    const ticket = ++historyRequestId.current;
    setChartRequest({ nodeId, loading: true, error: null });
    try {
      const response = await fetchNodeMetrics(nodeId, limit);
      if (ticket !== historyRequestId.current) return;
      setSnapshot((previous) => ({
        ...previous,
        histories: {
          ...previous.histories,
          [nodeId]: mergeSamples(
            previous.histories[nodeId] ?? [],
            response.samples,
          ),
        },
      }));
      setChartRequest(null);
    } catch {
      if (ticket === historyRequestId.current)
        setChartRequest({
          nodeId,
          loading: false,
          error: "Không tải được lịch sử telemetry. Vui lòng thử lại.",
        });
    }
  }, []);

  const toggleDemo = () => {
    if (snapshot.isDemoMode) {
      void loadData();
      return;
    }
    requestId.current++;
    historyRequestId.current++;
    modeRef.current = true;
    demoTickRef.current = 0;
    setIsRefreshing(false);
    setConnectionError(null);
    setChartRequest(null);
    setSnapshot(demoSnapshot());
    setActiveIncidentsCount(MOCK_INCIDENTS.filter((i) => i.status !== "RESOLVED").length);
    setActiveBlocksCount(
      MOCK_DEFENSE_ACTIONS.filter(
        (a) => a.status === "APPLIED" && a.action_type === "BLOCK_IP_NFTABLES",
      ).length,
    );
  };

  const addNode = (node: Node) =>
    setSnapshot((previous) => ({
      ...previous,
      nodes: [node, ...previous.nodes],
    }));

  const createProject = async (name: string, description?: string): Promise<Project> => {
    if (snapshot.isDemoMode) {
      const newProj: Project = {
        id: crypto.randomUUID(),
        name,
        description: description ?? null,
        created_at: new Date().toISOString(),
      };
      setSnapshot((prev) => ({
        ...prev,
        projects: [...prev.projects, newProj],
      }));
      return newProj;
    }
    const created = await apiCreateProject(name, description);
    setSnapshot((prev) => ({
      ...prev,
      projects: [...prev.projects, created],
    }));
    return created;
  };

  return {
    ...snapshot,
    isRefreshing,
    connectionError,
    chartRequest,
    isConnected,
    latencyMs,
    activeIncidentsCount,
    activeBlocksCount,
    securityToast,
    dismissSecurityToast,
    loadData: () => loadData(),
    loadHistory,
    toggleDemo,
    addNode,
    createProject,
  };
}
