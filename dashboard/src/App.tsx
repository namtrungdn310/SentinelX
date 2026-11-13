import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ChevronRight,
  Box,
  LayoutDashboard,
  Server,
  ShieldAlert,
  Sliders,
  Flame,
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
  validMetric,
} from "./presentation";
import type { Health } from "./presentation";
import { Header } from "./components/Header";
import { KPICards } from "./components/KPICards";
import { NodeMatrix } from "./components/NodeMatrix";
import type { HostTableState } from "./components/NodeMatrix";
import { TelemetryChart } from "./components/TelemetryChart";
import { LiveEventStream } from "./components/LiveEventStream";
import { AddNodeModal } from "./components/AddNodeModal";
import { IncidentsView } from "./components/IncidentsView";
import { DefenseView } from "./components/DefenseView";
import { PoliciesView } from "./components/PoliciesView";
import { SecurityToast } from "./components/SecurityToast";
import { NodeDetailModal } from "./components/NodeDetailModal";
import { ProjectsView } from "./components/ProjectsView";
import { AddProjectModal } from "./components/AddProjectModal";
import { AuthView } from "./components/AuthView";
import { authService, type User } from "./auth";
import { useInfrastructure } from "./useInfrastructure";
import type { Node } from "./types";

const STORAGE_KEY_SELECTED_PROJECT = "sentinelx_selected_project_id";

const getSavedProjectId = (): string | null => {
  try {
    return localStorage.getItem(STORAGE_KEY_SELECTED_PROJECT);
  } catch {
    return null;
  }
};

const views = ["projects", "overview", "hosts", "metrics", "events", "incidents", "defense", "policies"];
const currentView = () => {
  const hash = window.location.hash.slice(1);
  if (views.includes(hash)) {
    return hash;
  }
  return getSavedProjectId() ? "overview" : "projects";
};

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
    createProject,
    activeIncidentsCount,
    activeBlocksCount,
    securityToast,
    dismissSecurityToast,
  } = useInfrastructure();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(getSavedProjectId);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(() => nodes[0]?.id ?? null);
  const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sampleLimit, setSampleLimit] = useState(30);
  const [activeView, setActiveView] = useState(currentView);
  const [statusFacet, setStatusFacet] = useState<"all" | Health>("all");
  const [tableState, setTableState] = useState<HostTableState>({ view: "table", sort: null });
  const [currentUser, setCurrentUser] = useState<User | null>(() => authService.getCurrentUser());
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? null;
  const effectiveView = !selectedProjectId
    ? "projects"
    : activeView === "projects"
      ? "overview"
      : activeView;
  const mainRef = useRef<HTMLElement>(null);
  const previousView = useRef(activeView);

  useEffect(() => {
    try {
      if (selectedProjectId) {
        localStorage.setItem(STORAGE_KEY_SELECTED_PROJECT, selectedProjectId);
      } else {
        localStorage.removeItem(STORAGE_KEY_SELECTED_PROJECT);
      }
    } catch {
      // Ignore storage errors
    }
  }, [selectedProjectId]);

  useEffect(() => {
    const onHash = () => {
      setActiveView(currentView());
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (previousView.current !== effectiveView) {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
      mainRef.current?.focus({ preventScroll: true });
      previousView.current = effectiveView;
    }
  }, [effectiveView]);

  useEffect(() => {
    const viewTitles: Record<string, string> = {
      projects: "Dự Án Hạ Tầng",
      overview: "Tổng Quan Hạ Tầng",
      hosts: "Ma Trận Máy Chủ",
      metrics: "Chỉ Số Đo Lường",
      events: "Nhật Ký Sự Kiện",
      incidents: "Quản Lý Sự Cố An Ninh",
      defense: "Tường Lửa & Lệnh Phòng Thủ",
      policies: "Chính Sách & Whitelist",
    };
    const subtitle =
      viewTitles[effectiveView] || "Giám Sát Hạ Tầng & Bảo Vệ Tự Động";
    document.title = `SentinelX — ${subtitle}`;
  }, [effectiveView]);
  const navigate = (view: string) => {
    window.location.hash = view;
    setActiveView(view);
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
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
  const displayedProjects = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.id.toLowerCase().includes(query) ||
        (p.description && p.description.toLowerCase().includes(query)),
    );
  }, [projects, searchQuery]);
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
    projects: "Dự án hạ tầng",
    overview: "Tổng quan hạ tầng",
    hosts: "Danh sách máy chủ",
    metrics: "Telemetry tài nguyên",
    events: "Nhật ký hệ thống",
    incidents: "Quản lý Sự cố An ninh",
    defense: "Tường lửa & Lệnh phòng thủ",
    policies: "Chính sách phòng thủ & Danh sách an toàn",
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
  const statusFilter = (effectiveView === "overview" || effectiveView === "hosts") && (
    <div className="scope-filters">
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

  if (!currentUser) {
    return <AuthView onAuthenticated={(user) => setCurrentUser(user)} />;
  }

  return (
    <div className="app-container">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          window.scrollTo({ top: 0, left: 0, behavior: "instant" });
          mainRef.current?.focus({ preventScroll: true });
        }}
      >
        Đi đến nội dung
      </a>
      <aside className="app-sidebar">
        <a className="brand" href={selectedProjectId ? "#overview" : "#projects"} aria-label="SentinelX dự án">
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
        <div className="project-context-card">
          <span className="project-context-badge">
            {selectedProject ? "DỰ ÁN HIỆN TẠI" : "NGỮ CẢNH"}
          </span>
          <strong className="project-context-name">
            {selectedProject ? selectedProject.name : "Chưa chọn dự án"}
          </strong>
          {selectedProject ? (
            <button
              type="button"
              className="project-switch-btn"
              onClick={() => {
                setSelectedProjectId(null);
                setSearchQuery("");
                navigate("projects");
              }}
            >
              ⇄ Đổi dự án
            </button>
          ) : (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Chọn 1 dự án để tiếp tục
            </span>
          )}
        </div>
        {selectedProject ? (
          <>
            <span className="nav-label">GIÁM SÁT HẠ TẦNG</span>
            <nav aria-label="Điều hướng chính">
              {[
                { id: "overview", label: "Tổng quan", Icon: LayoutDashboard },
                { id: "hosts", label: "Máy chủ", Icon: Server, count: projectNodes.length },
                { id: "metrics", label: "Telemetry", Icon: Activity },
                { id: "events", label: "Nhật ký sự kiện", Icon: Terminal },
              ].map(({ id, label, Icon, count }) => (
                <a
                  key={id}
                  className={`nav-item ${effectiveView === id ? "active" : ""}`}
                  href={`#${id}`}
                  onClick={() => {
                    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
                  }}
                  aria-current={effectiveView === id ? "page" : undefined}
                >
                  <Icon size={18} />
                  <span>{label}</span>
                  {count !== undefined && <small>{count}</small>}
                  {effectiveView === id && <span className="nav-active-dot" />}
                </a>
              ))}
            </nav>
            <span className="nav-label" style={{ marginTop: 16 }}>AN NINH & PHÒNG THỦ</span>
            <nav aria-label="Điều hướng an ninh">
              {[
                { id: "incidents", label: "Sự cố an ninh", Icon: ShieldAlert, count: activeIncidentsCount, tone: "crit" },
                { id: "defense", label: "Tường lửa nftables", Icon: Flame, count: activeBlocksCount, tone: "danger" },
                { id: "policies", label: "Chính sách & Whitelist", Icon: Sliders },
              ].map(({ id, label, Icon, count, tone }) => (
                <a
                  key={id}
                  className={`nav-item ${effectiveView === id ? "active" : ""}`}
                  href={`#${id}`}
                  onClick={() => {
                    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
                  }}
                  aria-current={effectiveView === id ? "page" : undefined}
                >
                  <Icon size={18} />
                  <span>{label}</span>
                  {count !== undefined && count > 0 && (
                    <span className={`sidebar-badge badge-${tone || "crit"}`}>{count}</span>
                  )}
                  {effectiveView === id && <span className="nav-active-dot" />}
                </a>
              ))}
            </nav>
          </>
        ) : (
          <>
            <span className="nav-label">CỔNG DỰ ÁN</span>
            <nav aria-label="Điều hướng cổng dự án">
              <a
                className="nav-item active"
                href="#projects"
                aria-current="page"
              >
                <Box size={18} />
                <span>Danh sách dự án</span>
                <small>{projects.length}</small>
              </a>
            </nav>
          </>
        )}

        {currentUser && (
          <div className="sidebar-user-footer">
            <div className="sidebar-user-profile">
              <span className="sidebar-user-avatar">
                {currentUser.username.charAt(0).toUpperCase()}
              </span>
              <div className="sidebar-user-info">
                <span className="sidebar-user-name" title={currentUser.username}>
                  {currentUser.username}
                </span>
                <span className="sidebar-user-email" title={currentUser.email}>
                  {currentUser.email}
                </span>
              </div>
            </div>
            <button
              type="button"
              className="sidebar-logout-btn"
              title="Đăng xuất khỏi hệ thống"
              onClick={() => {
                authService.logout();
                setCurrentUser(null);
                setSelectedProjectId(null);
              }}
            >
              Đăng xuất
            </button>
          </div>
        )}
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
          {effectiveView === "projects" ? (
            <ProjectsView
              projects={displayedProjects}
              onSelectProject={(projectId) => {
                setSelectedProjectId(projectId);
                setSearchQuery("");
                navigate("overview");
              }}
              onOpenCreateModal={() => setIsAddProjectOpen(true)}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <h1>{pageHeadings[effectiveView]}</h1>
                  <div className="page-heading-context">
                    <p>
                      <strong>{selectedProject?.name}</strong> · {projectNodes.length} máy chủ
                    </p>
                    {statusFilter}
                  </div>
                </div>
                {(effectiveView === "overview" || effectiveView === "hosts") && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setIsAddNodeOpen(true)}
                  >
                    + Thêm máy chủ
                  </button>
                )}
              </div>
          {connectionError && (
            <div className="connection-error" role="alert">
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

          {effectiveView === "overview" && (
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
          {effectiveView === "hosts" && (
            <NodeMatrix
              projects={projects}
              nodes={displayedNodes}
              selectedNodeId={selectedNode?.id || null}
              onSelectNode={handleSelectNode}
              isLoading={isLoading}
              onOpenDetail={openDetail}
              state={tableState}
              onStateChange={setTableState}
            />
          )}
          {effectiveView === "metrics" && (
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
                    {!validMetric(selectedNode.latestDisk) && <small>Không có dữ liệu ổ đĩa</small>}
                  </article>
                  <article className="panel">
                    <span>RX giữa hai lần đo</span>
                    <strong>
                      {selectedNode.latestRxBytes === undefined
                        ? "—"
                        : formatBytes(selectedNode.latestRxBytes)}
                    </strong>
                  </article>
                  <article className="panel">
                    <span>TX giữa hai lần đo</span>
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
          {effectiveView === "events" && (
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
          {effectiveView === "incidents" && (
            <IncidentsView
              selectedProjectId={selectedProjectId}
              isDemoMode={isDemoMode}
            />
          )}
          {effectiveView === "defense" && (
            <DefenseView
              nodes={projectNodes}
              isDemoMode={isDemoMode}
            />
          )}
          {effectiveView === "policies" && (
            <PoliciesView
              selectedProjectId={selectedProjectId}
              projects={projects}
              isDemoMode={isDemoMode}
            />
          )}
            </>
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
      <AddProjectModal
        isOpen={isAddProjectOpen}
        onClose={() => setIsAddProjectOpen(false)}
        onCreateProject={async (name, desc) => {
          const created = await createProject(name, desc);
          if (created) {
            setSelectedProjectId(created.id);
            navigate("overview");
          }
        }}
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
      {selectedProject && (
        <SecurityToast
          toast={securityToast}
          onClose={dismissSecurityToast}
          onNavigate={navigate}
        />
      )}

    </div>
  );
}
export default App;
