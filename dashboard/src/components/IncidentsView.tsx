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
  Trash2,
} from "lucide-react";
import type {
  DefenseAction,
  DefensePolicy,
  DetectionSeverity,
  Incident,
  Node,
} from "../types";
import { deleteIncident, fetchDefenseActions, fetchIncidents, fetchPolicies } from "../api";
import {
  classifyIncidentHandling,
  getPortSummary,
  type IncidentHandlingMode,
  resolveIncidentDefenseFailure,
  SEVERITY_LABELS,
} from "../presentation";
import { IncidentDetailModal } from "./IncidentDetailModal";
import type { SecurityToastPayload } from "./SecurityToast";

type IncidentsTab = IncidentHandlingMode | "resolved";

interface Props {
  selectedProjectId: string | null;
  nodes?: Node[];
  incidentRevision?: number;
  onIncidentsSynced?: (items: Incident[]) => void;
  onNotify?: (toast: SecurityToastPayload) => void;
  initialTab?: IncidentsTab;
  initialIncidents?: Incident[];
  initialPolicies?: DefensePolicy[];
  initialDefenseActions?: DefenseAction[];
}

export function IncidentsView({
  selectedProjectId,
  nodes,
  incidentRevision = 0,
  onIncidentsSynced,
  onNotify,
  initialTab = "auto",
  initialIncidents = [],
  initialPolicies = [],
  initialDefenseActions = [],
}: Props) {
  const [incidents, setIncidents] = useState<Incident[]>(initialIncidents);
  const [policies, setPolicies] = useState<DefensePolicy[]>(initialPolicies);
  const [defenseActions, setDefenseActions] = useState<DefenseAction[]>(initialDefenseActions);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [handlingTab, setHandlingTab] = useState<IncidentsTab>(initialTab);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadIncidents = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    setError(null);
    try {
      const [incidentList, policyList, actionList] = await Promise.all([
        fetchIncidents({
          projectId: selectedProjectId ?? undefined,
          limit: 100,
        }),
        fetchPolicies(selectedProjectId ?? undefined).catch(() => []),
        fetchDefenseActions({
          projectId: selectedProjectId ?? undefined,
          limit: 100,
        }).catch(() => []),
      ]);
      setIncidents(incidentList);
      setPolicies(policyList);
      setDefenseActions(actionList);
      onIncidentsSynced?.(incidentList);
    } catch (err: unknown) {
      if (!quiet) {
        setError(err instanceof Error ? err.message : "Lỗi tải danh sách sự cố");
      }
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, [selectedProjectId, onIncidentsSynced]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadIncidents();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadIncidents]);

  useEffect(() => {
    if (incidentRevision <= 0) return;
    const timer = window.setTimeout(() => {
      void loadIncidents(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [incidentRevision, loadIncidents]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter((inc) => {
      if (statusFilter !== "all") {
        const failure = resolveIncidentDefenseFailure(inc, defenseActions);
        if (statusFilter === "DELIVERY_FAILED") {
          if (failure !== "DELIVERY_FAILED") return false;
        } else if (statusFilter === "EXECUTION_FAILED") {
          if (failure !== "EXECUTION_FAILED") return false;
        } else if (statusFilter === "DETECTED" && handlingTab === "auto") {
          if (inc.status !== "DETECTED" || failure !== null) return false;
        } else if (inc.status !== statusFilter) {
          return false;
        }
      }
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
  }, [incidents, statusFilter, severityFilter, searchQuery, defenseActions, handlingTab]);

  const { autoIncidents, manualIncidents, resolvedIncidents } = useMemo(() => {
    const auto: Incident[] = [];
    const manual: Incident[] = [];
    const resolved: Incident[] = [];
    for (const incident of filteredIncidents) {
      if (incident.status === "RESOLVED" || incident.status === "FALSE_POSITIVE") {
        resolved.push(incident);
        continue;
      }
      const info = classifyIncidentHandling(incident, policies);
      if (info.mode === "auto") {
        auto.push(incident);
      } else {
        manual.push(incident);
      }
    }
    return {
      autoIncidents: auto,
      manualIncidents: manual,
      resolvedIncidents: resolved,
    };
  }, [filteredIncidents, policies]);

  const activeIncidents =
    handlingTab === "auto"
      ? autoIncidents
      : handlingTab === "manual"
        ? manualIncidents
        : resolvedIncidents;

  const switchHandlingTab = (nextTab: IncidentsTab) => {
    setHandlingTab(nextTab);
    setStatusFilter("all");
  };

  const handleDeleteIncident = async (inc: Incident) => {
    try {
      setDeletingId(inc.id);
      setError(null);
      await deleteIncident(inc.id);
      const next = incidents.filter((item) => item.id !== inc.id);
      setIncidents(next);
      onIncidentsSynced?.(next);
      setSelectedIncident((prev) => (prev && prev.id === inc.id ? null : prev));
      onNotify?.({
        id: `incident-delete-${inc.id}`,
        type: "settings",
        title: "Đã xóa sự cố khỏi danh sách",
        message: `${inc.title} (${inc.id}) đã được gỡ khỏi mục đã giải quyết.`,
        targetView: "incidents",
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi xóa sự cố");
    } finally {
      setDeletingId(null);
    }
  };

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
    () =>
      incidents.filter(
        (i) => i.status === "RESOLVED" || i.status === "FALSE_POSITIVE",
      ).length,
    [incidents],
  );

  const activeModalIncident = useMemo(
    () =>
      selectedIncident
        ? incidents.find((i) => i.id === selectedIncident.id) ?? selectedIncident
        : null,
    [selectedIncident, incidents],
  );

  const handleIncidentUpdated = (updated: Incident) => {
    const next = incidents.map((item) =>
      item.id === updated.id ? { ...item, ...updated } : item
    );
    setIncidents(next);
    onIncidentsSynced?.(next);
    setSelectedIncident((prev) =>
      prev && prev.id === updated.id ? { ...prev, ...updated } : prev
    );
  };

  const getStatusBadge = (inc: Incident) => {
    switch (inc.status) {
      case "RESOLVED":
        return (
          <span className="status-badge ok">
            <i /> Đã giải quyết
          </span>
        );
      case "MITIGATING":
        return (
          <span className="status-badge info">
            <i /> Đang kích hoạt
          </span>
        );
      case "DETECTED": {
        if (handlingTab === "auto") {
          const failure = resolveIncidentDefenseFailure(inc, defenseActions);
          if (failure === "DELIVERY_FAILED") {
            return (
              <span className="status-badge crit">
                <i /> Tải lệnh bị lỗi
              </span>
            );
          }
          if (failure === "EXECUTION_FAILED") {
            return (
              <span className="status-badge crit">
                <i /> Kích hoạt bị lỗi
              </span>
            );
          }
        }
        return (
          <span className="status-badge pending">
            <i /> {handlingTab === "auto" ? "Đang chờ Agent tải lệnh" : "Đang diễn ra"}
          </span>
        );
      }
      case "FALSE_POSITIVE":
        return (
          <span className="status-badge unknown">
            <i /> Báo động giả
          </span>
        );
      default:
        return (
          <span className="status-badge unknown">
            <i /> {inc.status}
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
            <span className="kpi-label">Chờ xử lý</span>
            <AlertOctagon size={18} style={{ color: "var(--status-crit)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-crit)" }}>
            {countDetected}
          </div>
          <span className="kpi-footnote">Chờ Agent tải lệnh hoặc xử lý thủ công</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đang kích hoạt</span>
            <ShieldX size={18} style={{ color: "var(--status-warn)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-warn)" }}>
            {countMitigating}
          </div>
          <span className="kpi-footnote">Lệnh nftables / phục hồi dịch vụ đang có hiệu lực</span>
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

      {/* Compact Severity Criteria Strip */}
      <div className="panel severity-guide-bar" aria-label="Điều kiện phân loại mức độ sự cố">
        <div className="severity-guide-item">
          <span className="severity-badge warn">{SEVERITY_LABELS.HIGH}</span>
          <span className="severity-guide-text">Vượt ngưỡng cảnh báo ban đầu</span>
        </div>
        <div className="severity-guide-item">
          <span className="severity-badge crit">{SEVERITY_LABELS.CRITICAL}</span>
          <span className="severity-guide-text">
            Duy trì vượt ngưỡng ≥ 60 giây (hoặc đạt ≥ 95% / tấn công lớn)
          </span>
        </div>
      </div>

      {/* 2. Segmented Classification Tabs & Filter Toolbar */}
      <div className="incidents-segmented-row">
        <div className="defense-segmented-group" role="tablist" aria-label="Phân loại cơ chế xử lý sự cố">
          <button
            type="button"
            role="tab"
            aria-selected={handlingTab === "auto"}
            className={`segmented-tab ${handlingTab === "auto" ? "active" : ""}`}
            onClick={() => switchHandlingTab("auto")}
          >
            <span>Xử lý tự động</span>
            <span className="count-pill">{autoIncidents.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={handlingTab === "manual"}
            className={`segmented-tab ${handlingTab === "manual" ? "active" : ""}`}
            onClick={() => switchHandlingTab("manual")}
          >
            <span>Xử lý thủ công</span>
            <span className="count-pill">{manualIncidents.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={handlingTab === "resolved"}
            className={`segmented-tab ${handlingTab === "resolved" ? "active" : ""}`}
            onClick={() => switchHandlingTab("resolved")}
          >
            <span>Đã giải quyết</span>
            <span className="count-pill">{resolvedIncidents.length}</span>
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
            {handlingTab === "auto" && (
              <>
                <option value="DETECTED">Đang chờ Agent tải lệnh</option>
                <option value="MITIGATING">Đang kích hoạt</option>
                <option value="DELIVERY_FAILED">Tải lệnh bị lỗi</option>
                <option value="EXECUTION_FAILED">Kích hoạt bị lỗi</option>
              </>
            )}
            {handlingTab === "manual" && (
              <option value="DETECTED">Đang diễn ra</option>
            )}
            {handlingTab === "resolved" && (
              <>
                <option value="RESOLVED">Đã giải quyết</option>
                <option value="FALSE_POSITIVE">Báo động giả</option>
              </>
            )}
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            aria-label="Lọc theo mức độ nghiêm trọng"
          >
            <option value="all">Tất cả mức độ</option>
            <option value="CRITICAL">{SEVERITY_LABELS.CRITICAL}</option>
            <option value="HIGH">{SEVERITY_LABELS.HIGH}</option>
          </select>

          <button
            className="btn btn-outline"
            onClick={() => void loadIncidents()}
            disabled={isLoading}
            title="Tải lại danh sách sự cố"
          >
            <RefreshCw size={15} className={isLoading ? "spin" : ""} />
            Làm mới
          </button>
        </div>
      </div>

      {/* 3. Incidents Table Panel */}
      <div className="panel table-panel">
        {error && (
          <div className="connection-error" role="alert">
            <span>{error}</span>
            <button className="text-button" onClick={() => void loadIncidents()}>
              Thử lại
            </button>
          </div>
        )}

        <div className="table-scroll">
          <table
            className="host-table"
            aria-label={
              handlingTab === "auto"
                ? "Danh sách sự cố có xử lý tự động"
                : handlingTab === "manual"
                  ? "Danh sách sự cố xử lý thủ công"
                  : "Danh sách sự cố đã giải quyết"
            }
          >
            <thead>
              <tr>
                <th>Sự cố an ninh</th>
                <th>Máy chủ</th>
                <th>Cổng sự cố</th>
                <th>Mức độ</th>
                <th>Trạng thái</th>
                <th>Số sự kiện</th>
                <th>Thời điểm phát hiện</th>
                {handlingTab === "resolved" && (
                  <th style={{ textAlign: "right" }}>Thao tác</th>
                )}
              </tr>
            </thead>
            <tbody>
              {activeIncidents.length === 0 ? (
                <tr>
                  <td
                    colSpan={handlingTab === "resolved" ? 8 : 7}
                    style={{ padding: 0 }}
                  >
                    <div className="empty-state-card">
                      <ShieldCheck size={36} style={{ color: "var(--status-ok)" }} />
                      <h3>
                        {handlingTab === "resolved"
                          ? "Chưa có sự cố đã giải quyết"
                          : "Hạ tầng an toàn"}
                      </h3>
                      <p>
                        {searchQuery || statusFilter !== "all" || severityFilter !== "all"
                          ? "Không tìm thấy sự cố nào khớp với bộ lọc hiện tại."
                          : handlingTab === "auto"
                            ? "Không có sự cố đang mở nào thuộc nhóm xử lý tự động."
                            : handlingTab === "manual"
                              ? "Không có sự cố đang mở nào thuộc nhóm xử lý thủ công."
                              : "Không còn sự cố nào trong lịch sử đã giải quyết."}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                activeIncidents.map((inc) => {
                  const node = nodes?.find((n) => n.id === inc.node_id);
                  return (
                    <tr key={inc.id} onClick={() => setSelectedIncident(inc)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="incident-title-cell">
                          <strong className="incident-title-text">{inc.title}</strong>
                          <small className="font-mono" style={{ color: "var(--text-muted)", fontSize: 12 }}>
                            Mã: {inc.id}
                          </small>
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
                      <td style={{ whiteSpace: "nowrap" }}>{getStatusBadge(inc)}</td>
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
                      {handlingTab === "resolved" && (
                        <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                          <button
                            type="button"
                            className="icon-button danger-icon-button"
                            aria-label={`Xóa sự cố ${inc.id}`}
                            title="Xóa sự cố đã giải quyết"
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleDeleteIncident(inc);
                            }}
                            disabled={deletingId === inc.id}
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Incident Detail Modal */}
      {activeModalIncident && (
        <IncidentDetailModal
          key={activeModalIncident.id}
          incident={activeModalIncident}
          nodes={nodes}
          policies={policies}
          defenseActions={defenseActions}
          isOpen={Boolean(activeModalIncident)}
          onClose={() => setSelectedIncident(null)}
          onIncidentUpdated={handleIncidentUpdated}
          onNotify={onNotify}
        />
      )}
    </div>
  );
}
