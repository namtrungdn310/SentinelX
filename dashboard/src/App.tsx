import { useCallback, useEffect, useState } from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { Header } from './components/Header';
import { KPICards } from './components/KPICards';
import { NodeMatrix } from './components/NodeMatrix';
import { TelemetryChart } from './components/TelemetryChart';
import { LiveEventStream } from './components/LiveEventStream';
import { AddNodeModal } from './components/AddNodeModal';
import { NodeDetailModal } from './components/NodeDetailModal';
import { useWebSocket } from './useWebSocket';
import { fetchProjects, fetchNodes, fetchNodeMetrics } from './api';
import {
  MOCK_PROJECTS,
  MOCK_NODES,
  MOCK_INITIAL_EVENTS,
  generateMockTelemetryHistory,
} from './mockData';
import type { Project, Node, MetricSample, RealtimeMessage } from './types';

export function App() {
  const [isDemoMode, setIsDemoMode] = useState(true);

  const [projects, setProjects] = useState<Project[]>(MOCK_PROJECTS);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  const [nodes, setNodes] = useState<Node[]>(MOCK_NODES);
  const [selectedNode, setSelectedNode] = useState<Node | null>(MOCK_NODES[0]);

  const [telemetrySamples, setTelemetrySamples] = useState<MetricSample[]>(() =>
    generateMockTelemetryHistory(MOCK_NODES[0])
  );
  const [events, setEvents] = useState<RealtimeMessage[]>(MOCK_INITIAL_EVENTS);

  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // 1. Handle incoming realtime WebSocket events (from real Controller)
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

  // 2. Fetch data from real backend Controller or fallback to Demo Data
  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [projList, nodeList] = await Promise.all([
        fetchProjects(),
        fetchNodes(selectedProjectId || undefined),
      ]);

      if (projList.length === 0 && nodeList.length === 0) {
        // Backend is up but database has 0 records -> activate demo mode
        setIsDemoMode(true);
        setProjects(MOCK_PROJECTS);
        setNodes(MOCK_NODES);
        setSelectedNode(MOCK_NODES[0]);
        setTelemetrySamples(generateMockTelemetryHistory(MOCK_NODES[0]));
        setEvents(MOCK_INITIAL_EVENTS);
      } else {
        // Live data detected!
        setIsDemoMode(false);
        setProjects(projList);
        setNodes(nodeList);
        if (nodeList.length > 0) {
          setSelectedNode((prev) => {
            if (!prev || !nodeList.some((n) => n.id === prev.id)) {
              return nodeList[0];
            }
            return prev;
          });
        }
      }
    } catch {
      // Backend offline / connection error -> maintain demo mode
      setIsDemoMode(true);
      setProjects(MOCK_PROJECTS);
      setNodes(MOCK_NODES);
      setSelectedNode((prev) => prev || MOCK_NODES[0]);
      setTelemetrySamples((prev) => (prev.length > 0 ? prev : generateMockTelemetryHistory(MOCK_NODES[0])));
      setEvents((prev) => (prev.length > 0 ? prev : MOCK_INITIAL_EVENTS));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 3. Simulated Realtime Ticker during Demo Mode (Live breathing chart & stream)
  useEffect(() => {
    if (!isDemoMode) return;

    const interval = setInterval(() => {
      const nowIso = new Date().toISOString();

      // Fluctuate online nodes slightly
      setNodes((prevNodes) =>
        prevNodes.map((node) => {
          if (node.status !== 'online') return node;
          const cpuDelta = (Math.random() - 0.48) * 3.5;
          const memDelta = (Math.random() - 0.5) * 1.2;
          const newCpu = Math.round(Math.max(8, Math.min(97, (node.latestCpu ?? 30) + cpuDelta)) * 10) / 10;
          const newMem = Math.round(Math.max(15, Math.min(98, (node.latestMemory ?? 50) + memDelta)) * 10) / 10;

          return {
            ...node,
            latestCpu: newCpu,
            latestMemory: newMem,
            latestRxBytes: Math.max(1000000, (node.latestRxBytes ?? 5000000) + Math.round((Math.random() - 0.5) * 400000)),
            latestTxBytes: Math.max(1000000, (node.latestTxBytes ?? 3000000) + Math.round((Math.random() - 0.5) * 400000)),
            last_seen: nowIso,
          };
        })
      );

      // Fluctuate selected node and push new sample to chart
      setSelectedNode((curr) => {
        if (!curr || curr.status !== 'online') return curr;
        const cpuDelta = (Math.random() - 0.48) * 3.5;
        const memDelta = (Math.random() - 0.5) * 1.2;
        const newCpu = Math.round(Math.max(8, Math.min(97, (curr.latestCpu ?? 30) + cpuDelta)) * 10) / 10;
        const newMem = Math.round(Math.max(15, Math.min(98, (curr.latestMemory ?? 50) + memDelta)) * 10) / 10;

        const newSample: MetricSample = {
          observed_at: nowIso,
          cpu_percent: newCpu,
          memory_percent: newMem,
          disk_percent: curr.latestDisk ?? 35,
          network_rx_bytes: curr.latestRxBytes ?? 18000000,
          network_tx_bytes: curr.latestTxBytes ?? 12000000,
        };

        setTelemetrySamples((prev) => [...prev.slice(-29), newSample]);

        // Push new realtime event
        const sampleMsg: RealtimeMessage = {
          event: 'metric_update',
          data: {
            node_id: curr.id,
            samples: [newSample],
            received_at: nowIso,
          },
          timestamp: nowIso,
        };
        setEvents((prev) => [sampleMsg, ...prev.slice(0, 24)]);

        return {
          ...curr,
          latestCpu: newCpu,
          latestMemory: newMem,
          last_seen: nowIso,
        };
      });
    }, 2400);

    return () => clearInterval(interval);
  }, [isDemoMode]);

  // 4. Load historical telemetry when selected node changes
  useEffect(() => {
    if (!selectedNode) {
      setTelemetrySamples([]);
      return;
    }

    if (isDemoMode) {
      setTelemetrySamples(generateMockTelemetryHistory(selectedNode));
      setIsLoadingChart(false);
      return;
    }

    let isMounted = true;
    setIsLoadingChart(true);

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
        if (isMounted) setIsLoadingChart(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedNode?.id, isDemoMode]);

  const handleToggleDemoMode = () => {
    if (isDemoMode) {
      setIsDemoMode(false);
      loadData();
    } else {
      setIsDemoMode(true);
      setProjects(MOCK_PROJECTS);
      setNodes(MOCK_NODES);
      setSelectedNode(MOCK_NODES[0]);
      setTelemetrySamples(generateMockTelemetryHistory(MOCK_NODES[0]));
      setEvents(MOCK_INITIAL_EVENTS);
    }
  };

  const handleSelectNode = (node: Node) => {
    setSelectedNode(node);
  };

  const handleNodeCreated = (newNode: Node) => {
    setNodes((prev) => [newNode, ...prev]);
    setSelectedNode(newNode);
  };

  // Filter nodes by selected project if chosen
  const displayedNodes = selectedProjectId
    ? nodes.filter((n) => n.project_id === selectedProjectId)
    : nodes;

  return (
    <div className="app-container">
      {/* Top Header */}
      <Header
        projects={projects}
        selectedProject={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        isConnected={isConnected}
        latencyMs={latencyMs}
        isDemoMode={isDemoMode}
        onToggleDemoMode={handleToggleDemoMode}
        onOpenAddNode={() => setIsAddNodeOpen(true)}
        onRefresh={loadData}
        isRefreshing={isRefreshing}
      />

      {/* Main Workspace */}
      <main className="main-content">
        {/* Demo Mode Notice Banner */}
        {isDemoMode && (
          <div className="demo-banner">
            <div className="demo-banner-content">
              <Sparkles size={16} color="#7c3aed" />
              <span>
                <strong>Chế độ Dữ liệu Mẫu (Demo Data) đang bật:</strong> Đang hiển thị 5 máy chủ Linux giả lập với luồng WebSocket và đồ thị thời gian thực.
              </span>
            </div>
            <div className="demo-banner-actions">
              <button
                className="btn btn-outline btn-sm"
                style={{ fontSize: '11px', padding: '3px 8px', borderColor: '#bbf7d0', color: '#15803d' }}
                onClick={loadData}
              >
                <span>Kiểm tra Controller thực tế</span>
                <ArrowRight size={12} />
              </button>
            </div>
          </div>
        )}

        {/* KPI Cards */}
        <KPICards nodes={displayedNodes} isLoading={isLoading} />

        {/* Node Health Matrix */}
        <NodeMatrix
          nodes={displayedNodes}
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
          <LiveEventStream events={events} isConnected={isConnected || isDemoMode} />
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
