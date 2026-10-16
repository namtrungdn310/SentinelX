import { useCallback, useEffect, useState } from 'react';
import { Sparkles, ArrowRight, Layers, Tag, Activity, ShieldCheck } from 'lucide-react';
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

  // Bộ lọc tìm kiếm và Facets theo tiếng Việt
  const [searchQuery, setSearchQuery] = useState('');
  const [timeRange, setTimeRange] = useState('Trực tiếp 5p');
  const [statusFacet, setStatusFacet] = useState<'all' | 'ok' | 'warn' | 'crit' | 'unenrolled'>('all');
  const [roleFacet, setRoleFacet] = useState<'all' | 'lb' | 'worker' | 'db'>('all');

  // 1. Xử lý gói tin WebSocket thời gian thực từ Controller
  const handleWebSocketMessage = useCallback((msg: RealtimeMessage) => {
    // Thêm vào dòng nhật ký sự kiện trực tiếp
    setEvents((prev) => [msg, ...prev.slice(0, 39)]);

    if (msg.event === 'metric_update' && msg.data.node_id && msg.data.samples) {
      const nodeId = msg.data.node_id;
      const latestSample = msg.data.samples[msg.data.samples.length - 1];

      // Cập nhật trạng thái Node
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

      // Thêm mẫu đo mới vào đồ thị nếu node đang được chọn
      setSelectedNode((curr) => {
        if (curr && curr.id === nodeId) {
          setTelemetrySamples((prev) => [...prev.slice(-29), latestSample]);
          return {
            ...curr,
            status: 'online',
            last_seen: msg.data.received_at || new Date().toISOString(),
            latestCpu: latestSample.cpu_percent,
            latestMemory: latestSample.memory_percent,
          };
        }
        return curr;
      });
    }

    if (msg.event === 'node_status' && msg.data.node_id && msg.data.status) {
      const nodeId = msg.data.node_id;
      const status = msg.data.status as Node['status'];
      setNodes((prev) =>
        prev.map((n) => (n.id === nodeId ? { ...n, status } : n))
      );
      setSelectedNode((curr) => (curr && curr.id === nodeId ? { ...curr, status } : curr));
    }
  }, []);

  const { isConnected, latencyMs } = useWebSocket({
    onMessage: handleWebSocketMessage,
  });

  // 2. Tải danh sách dự án và máy chủ từ Controller REST API
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      const [projList, nodeList] = await Promise.all([
        fetchProjects(),
        fetchNodes(selectedProjectId || undefined),
      ]);

      if (projList && projList.length > 0) {
        setProjects(projList);
        setNodes(nodeList);
        setIsDemoMode(false); // Kết nối thành công tới Controller thật!

        if (nodeList.length > 0) {
          setSelectedNode((prev) => {
            if (!prev) return nodeList[0];
            const found = nodeList.find((n) => n.id === prev.id);
            return found || nodeList[0];
          });
        }
      }
    } catch {
      // Backend offline -> tiếp tục chế độ demo
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

  // 3. Giả lập luồng telemetry động trong chế độ mẫu
  useEffect(() => {
    if (!isDemoMode) return;

    const interval = setInterval(() => {
      const nowIso = new Date().toISOString();

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
          network_tx_bytes: curr.latestTxBytes ?? 1000000,
          network_rx_bytes: curr.latestRxBytes ?? 2000000,
        };

        setTelemetrySamples((prev) => [...prev.slice(-29), newSample]);

        return {
          ...curr,
          latestCpu: newCpu,
          latestMemory: newMem,
          last_seen: nowIso,
        };
      });
    }, 2200);

    return () => clearInterval(interval);
  }, [isDemoMode]);

  // 4. Nạp lịch sử telemetry khi đổi node
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

  // Tính số lượng máy chủ theo từng trạng thái
  const countOk = nodes.filter((n) => n.status === 'online' && (n.latestCpu ?? 0) <= 75).length;
  const countWarn = nodes.filter((n) => n.status === 'online' && (n.latestCpu ?? 0) > 75).length;
  const countCrit = nodes.filter((n) => n.status === 'offline').length;
  const countUnenrolled = nodes.filter((n) => n.status === 'unenrolled').length;

  // Lọc máy chủ theo Dự án -> Trạng thái -> Vai trò -> Ô Tìm kiếm
  const displayedNodes = nodes.filter((node) => {
    if (selectedProjectId && node.project_id !== selectedProjectId) return false;

    if (statusFacet === 'ok' && (node.status !== 'online' || (node.latestCpu ?? 0) > 75)) return false;
    if (statusFacet === 'warn' && (node.status !== 'online' || (node.latestCpu ?? 0) <= 75)) return false;
    if (statusFacet === 'crit' && node.status !== 'offline') return false;
    if (statusFacet === 'unenrolled' && node.status !== 'unenrolled') return false;

    const h = node.hostname.toLowerCase();
    if (roleFacet === 'lb' && !(h.includes('ingress') || h.includes('lb') || h.includes('gateway'))) return false;
    if (roleFacet === 'worker' && !(h.includes('worker') || h.includes('backend') || h.includes('api'))) return false;
    if (roleFacet === 'db' && !(h.includes('db') || h.includes('pg') || h.includes('primary'))) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const match =
        node.hostname.toLowerCase().includes(q) ||
        node.ip_address.toLowerCase().includes(q) ||
        node.status.toLowerCase().includes(q) ||
        (q.startsWith('host:') && node.hostname.toLowerCase().includes(q.replace('host:', ''))) ||
        (q.startsWith('ip:') && node.ip_address.toLowerCase().includes(q.replace('ip:', '')));
      if (!match) return false;
    }

    return true;
  });

  return (
    <div className="app-container">
      {/* 1. Thanh Điều Hướng Trên Cùng */}
      <Header
        projects={projects}
        selectedProject={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        isConnected={isConnected}
        latencyMs={latencyMs}
        isDemoMode={isDemoMode}
        onToggleDemoMode={handleToggleDemoMode}
        onOpenAddNode={() => setIsAddNodeOpen(true)}
        onRefresh={loadData}
        isRefreshing={isRefreshing}
      />

      {/* 2. Không Gian Quan Trắc Hạ Tầng (Sidebar + Màn Hình Chính) */}
      <div className="observability-workspace">
        {/* Thanh Bộ Lọc Bên Trái (Facets) */}
        <aside className="facets-sidebar">
          {/* Nhóm Lọc Trạng Thái */}
          <div>
            <div className="facet-group-title">
              <span>Trạng Thái</span>
              <Activity size={12} />
            </div>
            <div
              className={`facet-item ${statusFacet === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFacet('all')}
            >
              <div className="facet-item-left">
                <span>Tất cả máy chủ</span>
              </div>
              <span className="facet-badge-count">{nodes.length}</span>
            </div>
            <div
              className={`facet-item ${statusFacet === 'ok' ? 'active' : ''}`}
              onClick={() => setStatusFacet('ok')}
            >
              <div className="facet-item-left">
                <span className="facet-status-indicator ok" />
                <span>Bình thường (OK)</span>
              </div>
              <span className="facet-badge-count">{countOk}</span>
            </div>
            <div
              className={`facet-item ${statusFacet === 'warn' ? 'active' : ''}`}
              onClick={() => setStatusFacet('warn')}
            >
              <div className="facet-item-left">
                <span className="facet-status-indicator warn" />
                <span>Cảnh báo (&gt;75%)</span>
              </div>
              <span className="facet-badge-count">{countWarn}</span>
            </div>
            {countCrit > 0 && (
              <div
                className={`facet-item ${statusFacet === 'crit' ? 'active' : ''}`}
                onClick={() => setStatusFacet('crit')}
              >
                <div className="facet-item-left">
                  <span className="facet-status-indicator crit" />
                  <span>Mất kết nối</span>
                </div>
                <span className="facet-badge-count">{countCrit}</span>
              </div>
            )}
            <div
              className={`facet-item ${statusFacet === 'unenrolled' ? 'active' : ''}`}
              onClick={() => setStatusFacet('unenrolled')}
            >
              <div className="facet-item-left">
                <span className="facet-status-indicator unenrolled" />
                <span>Chưa đăng ký</span>
              </div>
              <span className="facet-badge-count">{countUnenrolled}</span>
            </div>
          </div>

          {/* Nhóm Lọc Vai Trò Hạ Tầng */}
          <div>
            <div className="facet-group-title">
              <span>Vai Trò Hạ Tầng</span>
              <Layers size={12} />
            </div>
            <div
              className={`facet-item ${roleFacet === 'all' ? 'active' : ''}`}
              onClick={() => setRoleFacet('all')}
            >
              <div className="facet-item-left">
                <span>Tất cả vai trò</span>
              </div>
            </div>
            <div
              className={`facet-item ${roleFacet === 'lb' ? 'active' : ''}`}
              onClick={() => setRoleFacet('lb')}
            >
              <div className="facet-item-left">
                <span className="host-tag role">cổng-lb</span>
                <span>Cổng vào &amp; Cân bằng tải</span>
              </div>
            </div>
            <div
              className={`facet-item ${roleFacet === 'worker' ? 'active' : ''}`}
              onClick={() => setRoleFacet('worker')}
            >
              <div className="facet-item-left">
                <span className="host-tag role">worker</span>
                <span>Máy chủ xử lý (Worker)</span>
              </div>
            </div>
            <div
              className={`facet-item ${roleFacet === 'db' ? 'active' : ''}`}
              onClick={() => setRoleFacet('db')}
            >
              <div className="facet-item-left">
                <span className="host-tag role">csdl</span>
                <span>Cụm CSDL PostgreSQL</span>
              </div>
            </div>
          </div>

          {/* Nhóm Lọc Môi Trường */}
          <div>
            <div className="facet-group-title">
              <span>Môi Trường</span>
              <Tag size={12} />
            </div>
            <div className="facet-item active">
              <div className="facet-item-left">
                <span className="host-tag env">mt:prod</span>
                <span>Production Chính Thức</span>
              </div>
              <span className="facet-badge-count">{nodes.length}</span>
            </div>
          </div>

          {/* Thông Số Kỹ Thuật Lõi */}
          <div style={{ marginTop: 'auto', padding: '12px', background: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-primary)', fontWeight: 700, marginBottom: '5px' }}>
              <ShieldCheck size={14} style={{ color: 'var(--brand-indigo)' }} />
              <span>Lõi SentinelX v0.1</span>
            </div>
            <div>Quan trắc: psutil + /proc</div>
            <div>Cân bằng tải: Eject &amp; Re-add</div>
          </div>
        </aside>

        {/* Màn Hình Quan Trắc Chính */}
        <main className="main-viewport">
          {/* Thông Báo Bản Mẫu */}
          {isDemoMode && (
            <div className="demo-banner">
              <div className="demo-banner-content">
                <Sparkles size={14} color="#6366f1" />
                <span>
                  <strong>Chế Độ Giả Lập Telemetry Đang Bật:</strong> Đang mô phỏng luồng chỉ số tài nguyên và nhật ký sự kiện của 5 máy chủ Linux thời gian thực.
                </span>
              </div>
              <div>
                <button
                  className="btn btn-outline btn-sm"
                  style={{ borderColor: 'var(--border-strong)', color: 'var(--text-primary)' }}
                  onClick={loadData}
                >
                  <span>Kết nối Controller Thực Tế</span>
                  <ArrowRight size={11} />
                </button>
              </div>
            </div>
          )}

          {/* 3. Thanh Tổng Hợp Chỉ Số Toàn Cụm (KPI Bar) */}
          <KPICards nodes={displayedNodes} isLoading={isLoading} />

          {/* 4. Bản Đồ Ma Trận Máy Chủ */}
          <NodeMatrix
            nodes={displayedNodes}
            selectedNodeId={selectedNode?.id || null}
            onSelectNode={handleSelectNode}
            isLoading={isLoading}
            onOpenDetail={(node) => {
              setSelectedNode(node);
              setIsDetailOpen(true);
            }}
          />

          {/* 5. Đồ Thị Chuỗi Thời Gian & Dòng Nhật Ký Trực Tiếp */}
          <div className="telemetry-row">
            <TelemetryChart
              selectedNode={selectedNode}
              samples={telemetrySamples}
              isLoading={isLoadingChart}
            />
            <LiveEventStream events={events} isConnected={isConnected || isDemoMode} />
          </div>
        </main>
      </div>

      {/* Hộp Thoại */}
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
