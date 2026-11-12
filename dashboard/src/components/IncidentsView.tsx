import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  ChevronRight,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import type { Incident, IncidentStatus, DetectionSeverity } from "../types";
import { fetchIncidents } from "../api";
import { MOCK_INCIDENTS } from "../mockData";
import { IncidentDetailModal } from "./IncidentDetailModal";

interface Props {
  selectedProjectId: string | null;
  isDemoMode: boolean;
}

export function IncidentsView({ selectedProjectId, isDemoMode }: Props) {
  const [incidents, setIncidents] = useState<Incident[]>(() => {
    if (isDemoMode) {
      return selectedProjectId
        ? MOCK_INCIDENTS.filter((i) => i.project_id === selectedProjectId)
        : MOCK_INCIDENTS;
    }
    return [];
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
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
        return;
      }
      const data = await fetchIncidents({
        projectId: selectedProjectId ?? undefined,
        limit: 100,
      });
      setIncidents(data);
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
        if (!matchTitle && !matchId && !matchSummary) return false;
      }
      return true;
    });
  }, [incidents, statusFilter, severityFilter, searchQuery]);

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
            <i /> Đang phòng thủ
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
        return (
          <span className="severity-badge crit">
            <AlertOctagon size={13} /> {severity}
          </span>
        );
      case "HIGH":
        return (
          <span className="severity-badge warn">
            <ShieldX size={13} /> {severity}
          </span>
        );
      case "MEDIUM":
        return (
          <span className="severity-badge medium">
            <ShieldAlert size={13} /> {severity}
          </span>
        );
      default:
        return (
          <span className="severity-badge low">
            <ShieldCheck size={13} /> {severity}
          </span>
        );
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
          <span className="kpi-footnote">Ghi nhận qua Detector M3 & M4</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đang diễn ra</span>
            <AlertOctagon size={18} style={{ color: "var(--status-crit)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-crit)" }}>
            {countDetected}
          </div>
          <span className="kpi-footnote">Cần rà soát hoặc kích hoạt phòng thủ</span>
        </div>

        <div className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đang phòng thủ</span>
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
          <span className="kpi-footnote">Đã unblock hoặc xử lý an toàn</span>
        </div>
      </div>

      {/* 2. Filter Toolbar */}
      <div className="panel table-toolbar">
        <div className="search-box">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            placeholder="Tìm theo tiêu đề, IP kẻ tấn công, mã sự cố..."
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
            <option value="DETECTED">Đang diễn ra (Detected)</option>
            <option value="MITIGATING">Đang phòng thủ (Mitigating)</option>
            <option value="RESOLVED">Đã giải quyết (Resolved)</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            aria-label="Lọc theo mức độ nghiêm trọng"
          >
            <option value="all">Tất cả mức độ</option>
            <option value="CRITICAL">Khẩn cấp (Critical)</option>
            <option value="HIGH">Cao (High)</option>
            <option value="MEDIUM">Trung bình (Medium)</option>
            <option value="LOW">Thấp (Low)</option>
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

      {/* 3. Incidents Table Panel */}
      <div className="panel table-panel">
        {error && (
          <div className="connection-error" role="alert">
            <span>{error}</span>
            <button className="text-button" onClick={loadIncidents}>
              Thử lại
            </button>
          </div>
        )}

        <div className="table-scroll">
          <table className="host-table" aria-label="Bảng danh sách sự cố an ninh">
            <thead>
              <tr>
                <th>Vụ việc an ninh</th>
                <th>Mức độ</th>
                <th>Trạng thái</th>
                <th>Số sự kiện</th>
                <th>Thời điểm phát hiện</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "48px 20px" }}>
                    <div className="attention-empty" style={{ justifyContent: "center" }}>
                      <ShieldCheck size={28} style={{ color: "var(--status-ok)" }} />
                      <div>
                        <strong>Hạ tầng an toàn</strong>
                        <p style={{ margin: "4px 0 0", color: "var(--text-muted)", fontSize: 13 }}>
                          {searchQuery || statusFilter !== "all" || severityFilter !== "all"
                            ? "Không tìm thấy sự cố nào khớp với bộ lọc hiện tại."
                            : "Không có sự cố tấn công mạng hay bất thường tài nguyên nào."}
                        </p>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => (
                  <tr key={inc.id} onClick={() => setSelectedIncident(inc)} style={{ cursor: "pointer" }}>
                    <td>
                      <div className="incident-title-cell">
                        <strong className="incident-title-text">{inc.title}</strong>
                        <small className="font-mono" style={{ color: "var(--text-muted)", fontSize: 12 }}>
                          ID: {inc.id.slice(0, 8)}...
                        </small>
                      </div>
                    </td>
                    <td>{getSeverityBadge(inc.severity)}</td>
                    <td>{getStatusBadge(inc.status)}</td>
                    <td>
                      <span className="font-mono count-badge">
                        {inc.event_count} events
                      </span>
                    </td>
                    <td>
                      <span className="font-mono" style={{ fontSize: 13 }}>
                        {new Date(inc.started_at).toLocaleTimeString("vi-VN")} · {new Date(inc.started_at).toLocaleDateString("vi-VN")}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedIncident(inc);
                        }}
                      >
                        Chi tiết <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Incident Detail Modal */}
      {selectedIncident && (
        <IncidentDetailModal
          key={selectedIncident.id}
          incident={selectedIncident}
          isOpen={Boolean(selectedIncident)}
          onClose={() => setSelectedIncident(null)}
          onIncidentUpdated={handleIncidentUpdated}
          isDemoMode={isDemoMode}
        />
      )}
    </div>
  );
}
