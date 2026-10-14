import { useCallback, useEffect, useState } from 'react';
import { Header } from './components/Header';
import { KPICards } from './components/KPICards';
import { NodeMatrix } from './components/NodeMatrix';
import { TelemetryChart } from './components/TelemetryChart';
import { LiveEventStream } from './components/LiveEventStream';
import { AddNodeModal } from './components/AddNodeModal';
import { NodeDetailModal } from './components/NodeDetailModal';
import { useWebSocket } from './useWebSocket';
import { fetchProjects, fetchNodes, fetchNodeMetrics } from './api';
import type { Project, Node, MetricSample, RealtimeMessage } from './types';

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  const [nodes, setNodes] = useState<Node[]>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const [telemetrySamples, setTelemetrySamples] = useState<MetricSample[]>([]);
  const [events, setEvents] = useState<RealtimeMessage[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // 1. Handle incoming realtime WebSocket events
  const handleWebSocketMessage = useCallback((msg: RealtimeMessage) => {
    // Add to live audit event stream
    setEvents((prev) => [msg, ...prev.slice(0, 24)]);

    if (msg.event === 'metric_update' && msg.data.node_id && msg.data.samples) {
      const nodeId = msg.data.node_id;
      const latestSample = msg.data.samples[msg.data.samples.length - 1];

      // Update Node in state with fresh metrics
      setNodes((prevNodes) =>
        prevNodes.map((n) => {
          if (n.id === nodeId) {
            return {
              ...n,
              status: 'online',
              last_seen: msg.data.received_at || new Date().toISOString(),
              latestCpu: latestSample.cpu_percent,
              latestMemory: latestSample.memory_percent,
              latestDisk: latestSample.disk_percent ?? n.latestDisk,
              latestRxBytes: latestSample.network_rx_bytes ?? n.latestRxBytes,
              latestTxBytes: latestSample.network_tx_bytes ?? n.latestTxBytes,
            };
          }
          return n;
        })
      );

      // If this event belongs to the currently selected node, append samples to chart
      setSelectedNode((curr) => {
        if (curr && curr.id === nodeId) {
          setTelemetrySamples((prevSamples) => {
            const updated = [...prevSamples, ...msg.data.samples!];
            return updated.slice(-50); // Keep last 50 points
          });
          return {
            ...curr,
            status: 'online',
            latestCpu: latestSample.cpu_percent,
            latestMemory: latestSample.memory_percent,
          };
        }
        return curr;
      });
    }
  }, []);

  const { isConnected, latencyMs } = useWebSocket({
    onMessage: handleWebSocketMessage,
  });

  // 2. Initial Data Loading
  const loadData = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const [projList, nodeList] = await Promise.all([
        fetchProjects(),
        fetchNodes(selectedProjectId || undefined),
      ]);

      setProjects(projList);
      setNodes(nodeList);

      // Auto-select first node if none selected or current is missing
      if (nodeList.length > 0) {
        setSelectedNode((prev) => {
          if (!prev || !nodeList.some((n) => n.id === prev.id)) {
            return nodeList[0];
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Lỗi tải dữ liệu ban đầu:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 3. Load historical telemetry when selected node changes
  useEffect(() => {
    if (!selectedNode) {
      setTelemetrySamples([]);
      return;
    }

    let isMounted = true;
    setIsChartLoading(true);

    fetchNodeMetrics(selectedNode.id, 30)
      .then((res) => {
        if (isMounted) {
          setTelemetrySamples(res.samples || []);
        }
      })
      .catch((err) => {
        console.warn('Chưa có lịch sử metric cho node này:', err);
        if (isMounted) setTelemetrySamples([]);
      })
      .finally(() => {
        if (isMounted) setIsChartLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedNode?.id]);

  function setIsChartLoading(loading: boolean) {
    setIsLoadingChart(loading);
  }

  const handleSelectNode = (node: Node) => {
    setSelectedNode(node);
  };

  const handleNodeCreated = (newNode: Node) => {
    setNodes((prev) => [newNode, ...prev]);
    setSelectedNode(newNode);
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <Header
        projects={projects}
        selectedProject={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        isConnected={isConnected}
        latencyMs={latencyMs}
        onOpenAddNode={() => setIsAddNodeOpen(true)}
        onRefresh={loadData}
        isRefreshing={isRefreshing}
      />

      {/* Main Workspace */}
      <main className="main-content">
        {/* KPI Cards */}
        <KPICards nodes={nodes} isLoading={isLoading} />

        {/* Node Health Matrix */}
        <NodeMatrix
          nodes={nodes}
          selectedNodeId={selectedNode?.id || null}
          onSelectNode={handleSelectNode}
          isLoading={isLoading}
        />

        {/* Realtime Telemetry Chart & Live Event Stream */}
        <div className="dashboard-columns">
          <TelemetryChart
            selectedNode={selectedNode}
            samples={telemetrySamples}
            isLoading={isLoadingChart}
          />
          <LiveEventStream events={events} isConnected={isConnected} />
        </div>
      </main>

      {/* Modals */}
      <AddNodeModal
        projects={projects}
        selectedProjectId={selectedProjectId}
        isOpen={isAddNodeOpen}
        onClose={() => setIsAddNodeOpen(false)}
        onNodeCreated={handleNodeCreated}
      />

      <NodeDetailModal
        node={selectedNode}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
      />
    </div>
  );
}

export default App;
