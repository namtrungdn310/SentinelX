import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ChevronRight,
  Box,
  CircleHelp,
  LayoutDashboard,
  ListFilter,
  Plus,
  Radio,
  Server,
  Terminal,
  X,
} from "lucide-react";
import { InfrastructureOverview } from "./components/InfrastructureOverview";
import {
  formatBytes,
  formatPercent,
  healthLabels,
  nodeHealth,
  nodeHealthLabel,
} from "./presentation";
import type { Health } from "./presentation";
import { Header } from "./components/Header";
import { KPICards } from "./components/KPICards";
import { NodeMatrix } from "./components/NodeMatrix";
import type { HostTableState } from "./components/NodeMatrix";
import { TelemetryChart } from "./components/TelemetryChart";
import { LiveEventStream } from "./components/LiveEventStream";
import { AddNodeModal } from "./components/AddNodeModal";
import { NodeDetailModal } from "./components/NodeDetailModal";
import { Modal } from "./components/Modal";
import { useInfrastructure } from "./useInfrastructure";
import type { Node } from "./types";

const views = ["overview", "hosts", "metrics", "events"];
const currentView = () =>
  views.includes(window.location.hash.slice(1))
    ? window.location.hash.slice(1)
    : "overview";

export function App() {
  const {
    projects,
    nodes,
    histories,
    events,
    notableEvents,
    isDemoMode,
    isRefreshing,
    connectionError,
    chartRequest,
    isConnected,
    latencyMs,
    loadData,
    loadHistory,
    toggleDemo,
    addNode,
  } = useInfrastructure();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(() => nodes[0]?.id ?? null);
  const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sampleLimit, setSampleLimit] = useState(30);
  const [activeView, setActiveView] = useState(currentView);
  const [showHelp, setShowHelp] = useState(false);
  const [statusFacet, setStatusFacet] = useState<"all" | Health>("all");
  const [tableState, setTableState] = useState<HostTableState>({ view: "table", sort: null });
  const mainRef = useRef<HTMLElement>(null);
  const previousView = useRef(activeView);
  useEffect(() => {
    const onHash = () => setActiveView(currentView());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (previousView.current !== activeView) {
      mainRef.current?.focus();
      previousView.current = activeView;
    }
  }, [activeView]);

  useEffect(() => {
    const viewTitles: Record<string, string> = {
      overview: "Tổng Quan Hạ Tầng",
      hosts: "Ma Trận Máy Chủ",
      metrics: "Chỉ Số Đo Lường",
      events: "Nhật Ký Sự Kiện",
    };
    const subtitle =
      viewTitles[activeView] || "Giám Sát Hạ Tầng & Bảo Vệ Tự Động";
    document.title = `SentinelX — ${subtitle}`;
  }, [activeView]);
  const navigate = (view: string) => {
    window.location.hash = view;
    setActiveView(view);
  };
  const handleSelectNode = (node: Node) => {
    setSelectedNodeId(node.id);
    navigate("metrics");
  };
  const handleNodeCreated = (node: Node) => {
    addNode(node);
    setSelectedNodeId(node.id);
  };
  const projectNodes = nodes.filter(
    (node) => !selectedProjectId || node.project_id === selectedProjectId,
  );
  const counts: Record<Health, number> = {
    ok: 0,
    warn: 0,
    crit: 0,
    unenrolled: 0,
    unknown: 0,
  };
  projectNodes.forEach((node) => counts[nodeHealth(node)]++);
  const displayedNodes = projectNodes.filter((node) => {
    if (statusFacet !== "all" && nodeHealth(node) !== statusFacet) return false;
    const query = searchQuery.trim().toLowerCase();
    if (query.startsWith("host:"))
      return node.hostname.toLowerCase().includes(query.slice(5));
    if (query.startsWith("ip:"))
      return node.ip_address.toLowerCase().includes(query.slice(3));
    return (
      !query ||
      [node.hostname, node.ip_address, node.status].some((value) =>
        value.toLowerCase().includes(query),
      )
    );
  });
  const selectedNode =
    projectNodes.find((node) => node.id === selectedNodeId) ??
    projectNodes[0] ??
    null;
  const nodeId = selectedNode?.id;
  const visibleNode = selectedNode;
  const detailNode = nodes.find((node) => node.id === detailNodeId) ?? null;
  useEffect(() => {
    if (activeView === "metrics" && nodeId && !isDemoMode)
      void loadHistory(nodeId, sampleLimit);
  }, [activeView, nodeId, isDemoMode, sampleLimit, loadHistory]);
  const telemetrySamples = nodeId ? (histories[nodeId] ?? []) : [];
  const isLoadingChart =
    chartRequest?.nodeId === nodeId && chartRequest.loading;
  const isLoading = isRefreshing && nodes.length === 0;
  const filtered = Boolean(
    searchQuery ||
    statusFacet !== "all",
  );
  const pageHeadings: Record<string, string> = {
    overview: "Tổng quan hạ tầng",
    hosts: "Danh sách máy chủ",
    metrics: "Telemetry tài nguyên",
    events: "Nhật ký hệ thống",
  };
  const openDetail = (node: Node) => {
    setSelectedNodeId(node.id);
    setDetailNodeId(node.id);
  };
  const matchesEventScope = (event: (typeof events)[number]) => {
    if (event.event === "pong") return false;
    if (!event.data.node_id) return !selectedProjectId;
    return projectNodes.some((node) => node.id === event.data.node_id);
  };
  const selectedEvents = events.filter(matchesEventScope);
  const recentEvents = notableEvents.filter(matchesEventScope);
  const statusFilter = (activeView === "overview" || activeView === "hosts") && (
    <div className="scope-filters">
      <ListFilter size={15} aria-hidden="true" />
      <select
        aria-label="Lọc trạng thái"
        value={statusFacet}
        onChange={(event) => setStatusFacet(event.target.value as typeof statusFacet)}
      >
        <option value="all">Tất cả trạng thái</option>
        {Object.entries(healthLabels).map(([health, label]) => (
          <option key={health} value={health}>{label} ({counts[health as Health]})</option>
        ))}
      </select>
      {filtered && (
        <button className="clear-filters" onClick={() => {
          setSearchQuery("");
          setStatusFacet("all");
        }}>
          <X size={12} /> Xóa bộ lọc
        </button>
      )}
    </div>
  );
  return (
    <div className="app-container">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          mainRef.current?.focus();
        }}
      >
        Đi đến nội dung
      </a>
      <aside className="app-sidebar">
        <a className="brand" href="#overview" aria-label="SentinelX tổng quan">
          <span className="brand-mark">
            <img
              src={`${import.meta.env.BASE_URL}sentinelx-mark-v2.svg`}
              alt=""
              width={36}
              height={36}
              decoding="async"
            />
          </span>
          <span>
            Sentinel<span className="brand-x">X</span>
          </span>
        </a>
        <div className="workspace-card">
          <span className="workspace-icon">
            <Box size={19} />
          </span>
          <div>
            <strong>SentinelX Lab</strong>
            <small>Linux infrastructure</small>
          </div>
        </div>
        <span className="nav-label">GIÁM SÁT</span>
        <nav aria-label="Điều hướng chính">
          {[
            { id: "overview", label: "Tổng quan", Icon: LayoutDashboard },
            { id: "hosts", label: "Máy chủ", Icon: Server },
            { id: "metrics", label: "Telemetry", Icon: Activity },
            { id: "events", label: "Nhật ký sự kiện", Icon: Terminal },
          ].map(({ id, label, Icon }) => (
            <a
              key={id}
              className={`nav-item ${activeView === id ? "active" : ""}`}
              href={`#${id}`}
              aria-current={activeView === id ? "page" : undefined}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === "hosts" && <small>{projectNodes.length}</small>}
              {id === "overview" && <span className="nav-active-dot" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setShowHelp(true)}>
            <CircleHelp size={18} />
            <span>Hướng dẫn sử dụng</span>
            <ChevronRight size={15} />
          </button>
        </div>
      </aside>
      <div className="app-workspace">
        <Header
          projects={projects}
          selectedProject={selectedProjectId}
          onSelectProject={setSelectedProjectId}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSearchSubmit={() => navigate("hosts")}
          isConnected={isConnected}
          latencyMs={latencyMs}
          isDemoMode={isDemoMode}
          onToggleDemoMode={toggleDemo}
          onRefresh={loadData}
          isRefreshing={isRefreshing}
        />
        <main
          ref={mainRef}
          tabIndex={-1}
          className="main-viewport"
          id="main-content"
        >
          <div className="page-heading">
            <div>
              <h1>{pageHeadings[activeView]}</h1>
              <div className="page-heading-context">
              <p>
                {projectNodes.length} máy chủ trong phạm vi ·{" "}
                {selectedProjectId
                  ? projects.find((project) => project.id === selectedProjectId)
                      ?.name
                  : `${projects.length} dự án`}
              </p>
              {statusFilter}
              </div>
            </div>
            {(activeView === "overview" || activeView === "hosts") && <button
              className={`btn ${activeView === "hosts" ? "btn-primary" : "btn-outline"}`}
              onClick={() => setIsAddNodeOpen(true)}
            >
              <Plus size={17} />
              Thêm máy chủ
            </button>}
          </div>
          {connectionError && (
            <div className="connection-error" role="alert">
              <Radio size={16} />
              <span>{connectionError}</span>
              <button
                className="text-button"
                onClick={loadData}
                disabled={isRefreshing}
              >
                Thử lại <ChevronRight size={14} />
              </button>
            </div>
          )}

          {activeView === "overview" && (
            <>
              <KPICards nodes={displayedNodes} isLoading={isLoading} />
              <InfrastructureOverview
                nodes={displayedNodes}
                projects={projects}
                selectedProjectId={selectedProjectId}
                onStatusSelect={(status) => {
                  setStatusFacet(status);
                  navigate("hosts");
                }}
                onProjectSelect={(projectId) => {
                  setSelectedProjectId(projectId);
                  navigate("hosts");
                }}
                onInspectNode={handleSelectNode}
                onOpenDetail={openDetail}
                onViewHosts={() => navigate("hosts")}
              />
              <LiveEventStream
                key={JSON.stringify([
                  selectedProjectId,
                  statusFacet,
                  searchQuery,
                  isDemoMode,
                ])}
                events={recentEvents}
                nodes={nodes}
                isConnected={isConnected || isDemoMode}
                isDemoMode={isDemoMode}
                preview
                onOpenAll={() => navigate("events")}
              />
            </>
          )}
          {activeView === "hosts" && (
            <NodeMatrix
              nodes={displayedNodes}
              selectedNodeId={selectedNode?.id || null}
              onSelectNode={handleSelectNode}
              isLoading={isLoading}
              onOpenDetail={openDetail}
              state={tableState}
              onStateChange={setTableState}
            />
          )}
          {activeView === "metrics" && (
            <div className="telemetry-detail">
              <div className="panel telemetry-host-toolbar">
                <label htmlFor="telemetry-host">Máy chủ phân tích</label>
                <select
                  id="telemetry-host"
                  value={nodeId ?? ""}
                  onChange={(event) => setSelectedNodeId(event.target.value)}
                  disabled={!projectNodes.length}
                >
                  {!projectNodes.length && (
                    <option value="">Không có máy chủ phù hợp</option>
                  )}
                  {projectNodes.map((node) => (
                    <option key={node.id} value={node.id}>
                      {node.hostname} · {node.ip_address}
                    </option>
                  ))}
                </select>
                {selectedNode && (
                  <span className={`status-badge ${nodeHealth(selectedNode)}`}>
                    <i />
                    {nodeHealthLabel(selectedNode)}
                  </span>
                )}
                {selectedNode && (
                  <button
                    className="text-button"
                    onClick={() => openDetail(selectedNode)}
                  >
                    Chi tiết host <ChevronRight size={14} />
                  </button>
                )}
              </div>
              <div className="telemetry-wrap">
                <div className="telemetry-controls">
                  <h2>
                    Lịch sử CPU &amp; RAM <span className="panel-unit">%</span>
                  </h2>
                  <select
                    aria-label="Số mẫu telemetry"
                    value={sampleLimit}
                    onChange={(event) =>
                      setSampleLimit(Number(event.target.value))
                    }
                  >
                    {[30, 60, 120].map((count) => (
                      <option key={count} value={count}>
                        {count} mẫu gần nhất
                      </option>
                    ))}
                  </select>
                </div>
                <TelemetryChart
                  key={nodeId}
                  selectedNode={visibleNode}
                  samples={telemetrySamples.slice(-sampleLimit)}
                  isLoading={isLoadingChart}
                  error={
                    chartRequest?.nodeId === nodeId ? chartRequest.error : null
                  }
                  onRetry={() =>
                    nodeId && void loadHistory(nodeId, sampleLimit)
                  }
                />
              </div>
              {selectedNode && (
                <section
                  className="telemetry-snapshot"
                  aria-label="Mẫu tài nguyên host gần nhất"
                >
                  <article className="panel">
                    <span>Ổ đĩa sử dụng</span>
                    <strong>
                      {formatPercent(selectedNode.latestDisk)}
                    </strong>
                  </article>
                  <article className="panel">
                    <span>RX tích lũy</span>
                    <strong>
                      {selectedNode.latestRxBytes === undefined
                        ? "—"
                        : formatBytes(selectedNode.latestRxBytes)}
                    </strong>
                  </article>
                  <article className="panel">
                    <span>TX tích lũy</span>
                    <strong>
                      {selectedNode.latestTxBytes === undefined
                        ? "—"
                        : formatBytes(selectedNode.latestTxBytes)}
                    </strong>
                  </article>
                </section>
              )}
            </div>
          )}
          {activeView === "events" && (
            <LiveEventStream
              key={JSON.stringify([
                selectedProjectId,
                statusFacet,
                searchQuery,
                isDemoMode,
              ])}
              events={selectedEvents}
              nodes={nodes}
              isConnected={isConnected || isDemoMode}
              isDemoMode={isDemoMode}
            />
          )}
        </main>
      </div>
      <AddNodeModal
        key={isAddNodeOpen ? (selectedProjectId ?? "all") : "closed"}
        projects={projects}
        selectedProjectId={selectedProjectId}
        isOpen={isAddNodeOpen}
        onClose={() => setIsAddNodeOpen(false)}
        onNodeCreated={handleNodeCreated}
        isDemoMode={isDemoMode}
      />
      {detailNode && (
        <NodeDetailModal
          isDemoMode={isDemoMode}
          key={detailNode.id}
          node={detailNode}
          isOpen={Boolean(detailNode)}
          onClose={() => setDetailNodeId(null)}
        />
      )}
      {showHelp && (
        <Modal
          onClose={() => setShowHelp(false)}
          labelledBy="help-title"
          className="help-modal"
        >
          <div className="modal-header">
            <h2 id="help-title">Hướng dẫn console</h2>
            <button
              className="icon-button"
              aria-label="Đóng hướng dẫn"
              onClick={() => setShowHelp(false)}
            >
              <X size={19} />
            </button>
          </div>
          <div className="modal-body">
            <p>SentinelX v0.1 · Foundation F14</p>
            <p>
              Chọn dự án, lọc theo trạng thái hoặc tìm hostname / IP để thu hẹp
              phạm vi quan trắc.
            </p>
            <p>
              Tổng quan tổng hợp toàn cụm. Chọn host trong bảng xếp hạng tài nguyên hoặc danh
              sách máy chủ để mở Telemetry và phân tích lịch sử CPU/RAM. Nút mũi tên
              trong bảng mở thông tin chi tiết.
            </p>
            <p>
              Dùng <kbd>/</kbd> để tìm nhanh. Chế độ demo dùng dữ liệu mô phỏng;
              nút bình thí nghiệm trên thanh công cụ chuyển sang Controller.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => setShowHelp(false)}
            >
              Đã hiểu <ChevronRight size={15} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
export default App;
