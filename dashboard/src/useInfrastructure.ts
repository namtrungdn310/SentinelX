import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNodeMetrics, fetchNodes, fetchProjects } from "./api";
import {
  generateMockTelemetryHistory,
  MOCK_INITIAL_EVENTS,
  MOCK_NODES,
  MOCK_PROJECTS,
} from "./mockData";
import type { MetricSample, Node, Project, RealtimeMessage } from "./types";
import { useWebSocket } from "./useWebSocket";
import { mergeSamples } from "./telemetry";

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
  const requestId = useRef(0);
  const historyRequestId = useRef(0);
  const modeRef = useRef(true);

  const handleMessage = useCallback((message: RealtimeMessage) => {
    if (modeRef.current || message.event === "pong") return;
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
        events: [message, ...previous.events].slice(0, 40),
        notableEvents:
          message.event === "metric_update"
            ? previous.notableEvents
            : [message, ...previous.notableEvents].slice(0, 20),
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
      const metrics = await Promise.allSettled(
        nodes.map((node) => fetchNodeMetrics(node.id, 1)),
      );
      if (ticket !== requestId.current) return;
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
        events: wasDemoMode ? [] : previous.events,
        notableEvents: wasDemoMode ? [] : previous.notableEvents,
        isDemoMode: false,
      }));
    } catch {
      if (ticket === requestId.current && !quiet)
        setConnectionError(
          "Chưa thể kết nối Controller. Kiểm tra địa chỉ API và trạng thái dịch vụ, rồi thử lại.",
        );
    } finally {
      if (ticket === requestId.current) setIsRefreshing(false);
    }
  }, []);

  const cancelRequests = useCallback(() => {
    requestId.current++;
    historyRequestId.current++;
  }, []);

  useEffect(() => {
    const initialRequest = window.setTimeout(() => void loadData(true), 0);
    return () => {
      window.clearTimeout(initialRequest);
      cancelRequests();
    };
  }, [loadData, cancelRequests]);

  useEffect(() => {
    if (!snapshot.isDemoMode) return;
    const interval = window.setInterval(() => {
      setSnapshot((previous) => {
        if (!previous.isDemoMode) return previous;
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
            network_rx_bytes: (node.latestRxBytes ?? 0) + 250000,
            network_tx_bytes: (node.latestTxBytes ?? 0) + 150000,
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
        return {
          ...previous,
          nodes,
          histories,
          events: event
            ? [event, ...previous.events].slice(0, 40)
            : previous.events,
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
      if (ticket !== historyRequestId.current || modeRef.current) return;
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
      setChartRequest({ nodeId, loading: false, error: null });
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
    setIsRefreshing(false);
    setConnectionError(null);
    setChartRequest(null);
    setSnapshot(demoSnapshot());
  };

  const addNode = (node: Node) =>
    setSnapshot((previous) => ({
      ...previous,
      nodes: [node, ...previous.nodes],
    }));
  return {
    ...snapshot,
    isRefreshing,
    connectionError,
    chartRequest,
    isConnected,
    latencyMs,
    loadData: () => loadData(),
    loadHistory,
    toggleDemo,
    addNode,
  };
}
