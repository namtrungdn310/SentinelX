import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  Filter,
  RefreshCw,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Zap,
} from "lucide-react";
import type {
  DefensePolicy,
  DetectionSeverity,
  Incident,
  IncidentStatus,
  Node,
} from "../types";
import { fetchIncidents, fetchPolicies } from "../api";
import { MOCK_INCIDENTS, MOCK_POLICIES } from "../mockData";
import {
  classifyIncidentHandling,
  getPortSummary,
  type IncidentHandlingMode,
  SEVERITY_LABELS,
} from "../presentation";
import { IncidentDetailModal } from "./IncidentDetailModal";

interface Props {
  selectedProjectId: string | null;
  nodes?: Node[];
  isDemoMode: boolean;
}

export function IncidentsView({ selectedProjectId, nodes, isDemoMode }: Props) {
  const [incidents, setIncidents] = useState<Incident[]>(() => {
    if (isDemoMode) {
      return selectedProjectId
        ? MOCK_INCIDENTS.filter((i) => i.project_id === selectedProjectId)
        : MOCK_INCIDENTS;
    }
    return [];
  });
  const [policies, setPolicies] = useState<DefensePolicy[]>(() =>
    isDemoMode ? MOCK_POLICIES : []
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [handlingFilter, setHandlingFilter] = useState<"all" | IncidentHandlingMode>("all");
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  const loadIncidents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        let items = MOCK_INCIDENTS;
        if (selectedProjectId) {
          items = items.filter((i) => i.project_id === selectedProjectId);
        }
        setIncidents(items);
        setPolicies(MOCK_POLICIES);
        return;
      }
      const [incidentList, policyList] = await Promise.all([
        fetchIncidents({
          projectId: selectedProjectId ?? undefined,
          limit: 100,
        }),
        fetchPolicies(selectedProjectId ?? undefined).catch(() => []),
      ]);
      setIncidents(incidentList);
      setPolicies(policyList);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi tải danh sách sự cố");
    } finally {
      setIsLoading(false);
    }
  }, [selectedProjectId, isDemoMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadIncidents();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadIncidents]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter((inc) => {
      if (statusFilter !== "all" && inc.status !== statusFilter) return false;
      if (severityFilter !== "all" && inc.severity !== severityFilter) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchTitle = inc.title.toLowerCase().includes(query);
        const matchId = inc.id.toLowerCase().includes(query);
        const matchSummary = inc.summary?.toLowerCase().includes(query) ?? false;
        const matchIp = inc.attacker_ip?.toLowerCase().includes(query) ?? false;
        if (!matchTitle && !matchId && !matchSummary && !matchIp) return false;
      }
      return true;
    });
  }, [incidents, statusFilter, severityFilter, searchQuery]);

  const { autoIncidents, manualIncidents } = useMemo(() => {
    const auto: { incident: Incident; label: string; reason: string }[] = [];
    const manual: { incident: Incident; label: string; reason: string }[] = [];
    for (const incident of filteredIncidents) {
      const info = classifyIncidentHandling(incident, policies);
      if (info.mode === "auto") {
        auto.push({ incident, label: info.label, reason: info.reason });
      } else {
        manual.push({ incident, label: info.label, reason: info.reason });
      }
    }
    return { autoIncidents: auto, manualIncidents: manual };
  }, [filteredIncidents, policies]);

  // Metric counts
  const countDetected = useMemo(
    () => incidents.filter((i) => i.status === "DETECTED").length,
    [incidents]
  );
  const countMitigating = useMemo(
    () => incidents.filter((i) => i.status === "MITIGATING").length,
    [incidents]
  );
  const countResolved = useMemo(
    () => incidents.filter((i) => i.status === "RESOLVED").length,
    [incidents]
  );

  const handleIncidentUpdated = (updated: Incident) => {
    setIncidents((prev) =>
      prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item))
    );
  };

  const getStatusBadge = (status: IncidentStatus) => {
    switch (status) {
      case "RESOLVED":
        return (
          <span className="status-badge ok">
            <i /> Đã giải quyết
          </span>
        );
      case "MITIGATING":
        return (
          <span className="status-badge warn">
            <i /> Đang ngăn chặn
          </span>
        );
      case "DETECTED":
        return (
          <span className="status-badge crit">
            <i /> Đang diễn ra
          </span>
        );
      default:
        return (
          <span className="status-badge unknown">
            <i /> {status}
          </span>
        );
    }
  };

  const getSeverityBadge = (severity: DetectionSeverity) => {
    switch (severity) {
      case "CRITICAL":
        return <span className="severity-badge crit">{SEVERITY_LABELS.CRITICAL}</span>;
      case "HIGH":
        return <span className="severity-badge warn">{SEVERITY_LABELS.HIGH}</span>;
      default:
        return <span className="severity-badge medium">{SEVERITY_LABELS.MEDIUM}</span>;
    }
  };

  const renderIncidentSection = (
    mode: IncidentHandlingMode,
    title: string,
    subtitle: string,
    rows: { incident: Incident; label: string; reason: string }[],
    emptyText: string,
  ) => (
    <section
      className="panel table-panel incident-section-panel"
      aria-label={title}
    >
      <div className={`incident-section-header ${mode === "auto" ? "is-auto" : "is-manual"}`}>
        <div className="incident-section-heading">
          {mode === "auto" ? (
            <Zap size={15} className="incident-section-icon-auto" aria-hidden="true" />
          ) : (
            <ShieldAlert size={15} className="incident-section-icon-manual" aria-hidden="true" />
          )}
          <h3>{title}</h3>
          <span className="count-badge">{rows.length}</span>
        </div>
        <span className="incident-section-desc">{subtitle}</span>
      </div>

      <div className="table-scroll">
        <table className="host-table" aria-label={title}>
          <thead>
            <tr>
              <th>Sự cố an ninh</th>
              <th>Máy chủ</th>
              <th>Cổng sự cố</th>
              <th>Mức độ</th>
              <th>Trạng thái</th>
              <th>Số sự kiện</th>
              <th>Thời điểm phát hiện</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "32px 20px" }}>
                  <div className="attention-empty" style={{ justifyContent: "center" }}>
                    <ShieldCheck size={22} style={{ color: "var(--status-ok)" }} />
                    <div>
                      <strong>Không có sự cố</strong>
                      <p style={{ margin: "2px 0 0", color: "var(--text-muted)", fontSize: 13 }}>
                        {searchQuery || statusFilter !== "all" || severityFilter !== "all"
                          ? "Không tìm thấy sự cố nào khớp với bộ lọc hiện tại."
                          : emptyText}
                      </p>
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              rows.map(({ incident: inc, label, reason }) => {
                const node = nodes?.find((n) => n.id === inc.node_id);
                return (
                  <tr key={inc.id} onClick={() => setSelectedIncident(inc)} style={{ cursor: "pointer" }}>
                    <td>
                      <div className="incident-title-cell">
                        <strong className="incident-title-text">{inc.title}</strong>
                        <div className="incident-sub-meta">
                          <small className="font-mono" style={{ color: "var(--text-muted)", fontSize: 12 }}>
                            Mã: {inc.id}
                          </small>
                          <span className={`handling-chip ${mode}`} title={reason}>
                            {label}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="incident-node-cell">
                        <span className="node-host-name">
                          <Server size={13} className="text-muted" style={{ display: "inline", marginRight: 5, verticalAlign: -1 }} />
                          <strong>{node?.hostname || (inc.node_id ? inc.node_id.slice(0, 8) : "—")}</strong>
                        </span>
                        {node?.ip_address && (
                          <small className="font-mono text-muted">
                            {node.ip_address}
                          </small>
                        )}
                      </div>
                    </td>
                    <td>
                      {(() => {
                        const summary = getPortSummary(inc.targeted_ports);
                        if (!summary) return <span className="font-mono text-muted">—</span>;
                        return (
                          <span
                            className="font-mono text-muted port-summary-wrap"
                            style={{ fontWeight: 500, fontSize: 13, whiteSpace: "nowrap" }}
                            title={inc.targeted_ports?.join(", ")}
                          >
                            <span>{summary.visible}</span>
                            {summary.remaining > 0 && (
                              <span className="port-overflow-badge">+{summary.remaining}</span>
                            )}
                          </span>
                        );
                      })()}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>{getSeverityBadge(inc.severity)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{getStatusBadge(inc.status)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <span className="font-mono count-badge">
                        {inc.event_count} sự kiện
                      </span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <span className="font-mono" style={{ fontSize: 13 }}>
                        {new Date(inc.started_at).toLocaleTimeString("vi-VN")} · {new Date(inc.started_at).toLocaleDateString("vi-VN")}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );

  return (
    <div className="incidents-container">
      {/* 1. Header KPI Cards */}
      <div className="kpi-grid">
        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Tổng số sự cố</span>
            <ShieldAlert size={18} className="kpi-icon" />
          </div>
          <div className="kpi-value">{incidents.length}</div>
          <span className="kpi-footnote">Tự động phát hiện từ lưu lượng &amp; tài nguyên</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đang diễn ra</span>
            <AlertOctagon size={18} style={{ color: "var(--status-crit)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-crit)" }}>
            {countDetected}
          </div>
          <span className="kpi-footnote">Cần rà soát hoặc kích hoạt ngăn chặn</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đang ngăn chặn</span>
            <ShieldX size={18} style={{ color: "var(--status-warn)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-warn)" }}>
            {countMitigating}
          </div>
          <span className="kpi-footnote">Lệnh nftables / Safe Mode đang có hiệu lực</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đã giải quyết</span>
            <CheckCircle2 size={18} style={{ color: "var(--status-ok)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-ok)" }}>
            {countResolved}
          </div>
          <span className="kpi-footnote">Đã gỡ chặn hoặc xử lý an toàn</span>
        </div>
      </div>

      {/* 2. Segmented Classification Tabs & Filter Toolbar */}
      <div className="incidents-segmented-row">
        <div className="defense-segmented-group" role="tablist" aria-label="Phân loại cơ chế xử lý sự cố">
          <button
            type="button"
            role="tab"
            aria-selected={handlingFilter === "all"}
            className={`segmented-tab ${handlingFilter === "all" ? "active" : ""}`}
            onClick={() => setHandlingFilter("all")}
          >
            <span>Tất cả</span>
            <span className="count-pill">{filteredIncidents.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={handlingFilter === "auto"}
            className={`segmented-tab ${handlingFilter === "auto" ? "active" : ""}`}
            onClick={() => setHandlingFilter("auto")}
          >
            <span>Xử lý tự động</span>
            <span className="count-pill">{autoIncidents.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={handlingFilter === "manual"}
            className={`segmented-tab ${handlingFilter === "manual" ? "active" : ""}`}
            onClick={() => setHandlingFilter("manual")}
          >
            <span>Cần xử lý thủ công</span>
            <span className="count-pill">{manualIncidents.length}</span>
          </button>
        </div>
      </div>

      <div className="panel table-toolbar">
        <div className="search-box">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            placeholder="Tìm theo tiêu đề, IP nguồn, mã sự cố..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <Filter size={15} style={{ color: "var(--text-muted)" }} />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Lọc theo trạng thái sự cố"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="DETECTED">Đang diễn ra</option>
            <option value="MITIGATING">Đang ngăn chặn</option>
            <option value="RESOLVED">Đã giải quyết</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            aria-label="Lọc theo mức độ nghiêm trọng"
          >
            <option value="all">Tất cả mức độ</option>
            <option value="CRITICAL">{SEVERITY_LABELS.CRITICAL}</option>
            <option value="HIGH">{SEVERITY_LABELS.HIGH}</option>
            <option value="MEDIUM">{SEVERITY_LABELS.MEDIUM}</option>
          </select>

          <button
            className="btn btn-outline"
            onClick={loadIncidents}
            disabled={isLoading}
            title="Tải lại danh sách sự cố"
          >
            <RefreshCw size={15} className={isLoading ? "spin" : ""} />
            Làm mới
          </button>
        </div>
      </div>

      {error && (
        <div className="connection-error" role="alert">
          <span>{error}</span>
          <button className="text-button" onClick={loadIncidents}>
            Thử lại
          </button>
        </div>
      )}

      {/* 3. Separated Incidents Sections */}
      {(handlingFilter === "all" || handlingFilter === "auto") &&
        renderIncidentSection(
          "auto",
          "Sự cố có xử lý tự động",
          "Khớp chính sách tự động thực thi (tường lửa nftables hoặc phục hồi thích ứng)",
          autoIncidents,
          "Không có sự cố nào thuộc nhóm xử lý tự động."
        )}

      {(handlingFilter === "all" || handlingFilter === "manual") &&
        renderIncidentSection(
          "manual",
          "Sự cố chỉ báo cáo · Cần xử lý thủ công",
          "Chưa có chính sách tự động hoặc chính sách đang tắt — cần quản trị viên kiểm tra và đóng thủ công",
          manualIncidents,
          "Không có sự cố nào cần xử lý thủ công."
        )}

      {/* 4. Incident Detail Modal */}
      {selectedIncident && (
        <IncidentDetailModal
          key={selectedIncident.id}
          incident={selectedIncident}
          nodes={nodes}
          policies={policies}
          isOpen={Boolean(selectedIncident)}
          onClose={() => setSelectedIncident(null)}
          onIncidentUpdated={handleIncidentUpdated}
          isDemoMode={isDemoMode}
        />
      )}
    </div>
  );
}
