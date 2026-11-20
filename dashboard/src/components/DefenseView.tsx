import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  MinusCircle,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldCheck,
} from "lucide-react";
import type { Node, DefenseAction, DefenseActionStatus } from "../types";
import { fetchDefenseActions, revertDefenseAction } from "../api";
import { MOCK_DEFENSE_ACTIONS } from "../mockData";
import { ManualBlockModal } from "./ManualBlockModal";

interface Props {
  nodes: Node[];
  isDemoMode: boolean;
}

function formatDuration(seconds: number): string {
  if (seconds <= 0) return "0s";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins >= 60) {
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hours}h ${remMins}m`;
  }
  if (mins > 0) {
    return `${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
  }
  return `${secs}s`;
}

function formatRelativeTime(dateString: string): string {
  const diffMs = Date.now() - new Date(dateString).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "Vừa xong";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} ngày trước`;
}

export function DefenseView({ nodes, isDemoMode }: Props) {
  const [actions, setActions] = useState<DefenseAction[]>(() => {
    return isDemoMode ? MOCK_DEFENSE_ACTIONS : [];
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeFilter, setNodeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [revertingId, setRevertingId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // Keep live countdown updated every second
  useEffect(() => {
    const interval = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  const loadActions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        setActions(MOCK_DEFENSE_ACTIONS);
        return;
      }
      const data = await fetchDefenseActions({
        nodeId: nodeFilter !== "all" ? nodeFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        limit: 100,
      });
      setActions(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi tải danh sách lệnh tường lửa");
    } finally {
      setIsLoading(false);
    }
  }, [nodeFilter, statusFilter, isDemoMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadActions();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadActions]);

  // Handle Unblocking
  const handleUnblock = async (action: DefenseAction) => {
    if (!action.id) return;
    setRevertingId(action.id);
    setFeedbackMessage(null);
    try {
      if (isDemoMode) {
        setActions((prev) =>
          prev.map((a) => (a.id === action.id ? { ...a, status: "REVERTED" as DefenseActionStatus } : a))
        );
        setFeedbackMessage({
          type: "success",
          text: `Đã gỡ chặn thành công IP ${action.target_ip ?? "mục tiêu"} khỏi tường lửa nftables!`,
        });
        return;
      }
      await revertDefenseAction(action.id);
      setActions((prev) =>
        prev.map((a) => (a.id === action.id ? { ...a, status: "REVERTED" as DefenseActionStatus } : a))
      );
      setFeedbackMessage({
        type: "success",
        text: `Đã gửi lệnh xóa IP ${action.target_ip} khỏi bảng chặn nftables.`,
      });
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể gỡ chặn IP",
      });
    } finally {
      setRevertingId(null);
    }
  };

  const handleActionCreated = (newAction: DefenseAction) => {
    setActions((prev) => [newAction, ...prev]);
    setFeedbackMessage({
      type: "success",
      text: `Đã kích hoạt thành công lệnh tường lửa cho IP ${newAction.target_ip ?? "mục tiêu"}!`,
    });
  };

  // KPIs
  const totalCount = actions.length;
  const appliedCount = actions.filter((a) => a.status === "APPLIED").length;
  const failedCount = actions.filter((a) => a.status === "FAILED").length;
  const successRate = totalCount > 0 ? Math.round((appliedCount / (appliedCount + failedCount || 1)) * 100) : 100;
  const revertedCount = actions.filter((a) => a.status === "REVERTED").length;

  // Filtered unified action list
  const filteredActions = useMemo(() => {
    return actions.filter((act) => {
      if (nodeFilter !== "all" && act.node_id !== nodeFilter) return false;
      if (statusFilter !== "all" && act.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchIp = act.target_ip?.toLowerCase().includes(query) ?? false;
        const matchId = act.id.toLowerCase().includes(query);
        const matchNode = act.node_id.toLowerCase().includes(query);
        const matchType = act.action_type.toLowerCase().includes(query);
        if (!matchIp && !matchId && !matchNode && !matchType) return false;
      }
      return true;
    });
  }, [actions, nodeFilter, statusFilter, searchQuery]);

  return (
    <div className="defense-view">
      {/* Feedback banner */}
      {feedbackMessage && (
        <div
          className={`feedback-banner ${feedbackMessage.type === "success" ? "feedback-success" : "feedback-error"}`}
          role="alert"
        >
          {feedbackMessage.type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <span>{feedbackMessage.text}</span>
          <button
            type="button"
            className="icon-button"
            aria-label="Đóng thông báo"
            onClick={() => setFeedbackMessage(null)}
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <section className="kpi-grid" aria-label="Thống kê tường lửa">
        <article className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">IP đang bị chặn</span>
            <Flame size={18} style={{ color: "var(--status-crit)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-crit)" }}>
            {appliedCount}
          </div>
          <span className="kpi-footnote">Đang chặn trực tiếp tại nhân hệ điều hành</span>
        </article>

        <article className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Tổng lệnh tường lửa</span>
            <Shield size={18} style={{ color: "var(--brand-indigo)" }} />
          </div>
          <div className="kpi-value">{totalCount}</div>
          <span className="kpi-footnote">Bao gồm tự động và thủ công</span>
        </article>

        <article className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Tỷ lệ thực thi thành công</span>
            <CheckCircle2 size={18} style={{ color: "var(--status-ok)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--status-ok)" }}>
            {successRate}%
          </div>
          <span className="kpi-footnote">
            {appliedCount} thành công · {failedCount} thất bại
          </span>
        </article>

        <article className="panel kpi-card">
          <div className="kpi-head">
            <span className="kpi-label">Đã thu hồi / gỡ bỏ</span>
            <ShieldCheck size={18} style={{ color: "var(--status-neutral)" }} />
          </div>
          <div className="kpi-value" style={{ color: "var(--text-secondary)" }}>
            {revertedCount}
          </div>
          <span className="kpi-footnote">Hết hạn hoặc do admin gỡ</span>
        </article>
      </section>

      {/* Unified Defense Console Panel */}
      <section className="panel defense-main-panel" aria-label="Bảng quản lý tường lửa">
        {/* Panel Header with Segmented Filter */}
        <div className="defense-panel-header">
          <div className="defense-header-info">
            <div className="section-header-title">
              <Flame size={18} style={{ color: "var(--status-crit)" }} />
              <h2>Tường lửa bảo vệ máy chủ</h2>
              <span className="badge badge-neutral font-mono">{filteredActions.length} lệnh</span>
            </div>
            <p className="defense-header-desc">
              Quản lý danh sách địa chỉ IP bị khóa và lịch sử thực thi bảo vệ trên các máy chủ.
            </p>
          </div>

          <div className="defense-segmented-group" role="group" aria-label="Lọc nhanh trạng thái">
            {[
              { id: "all", label: "Tất cả", count: totalCount },
              { id: "APPLIED", label: "Đang chặn", count: appliedCount },
              { id: "REVERTED", label: "Đã gỡ bỏ", count: revertedCount },
              { id: "FAILED", label: "Thất bại", count: failedCount },
            ].map(({ id, label, count }) => (
              <button
                key={id}
                type="button"
                className={`segmented-tab ${statusFilter === id ? "active" : ""}`}
                onClick={() => setStatusFilter(id)}
              >
                <span>{label}</span>
                <span className="count-pill">{count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Toolbar: Search, Node select, Refresh, Manual Block */}
        <div className="defense-toolbar">
          <div className="search-box">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              placeholder="Tìm theo đối tượng xử lý, mã lệnh, máy chủ..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Tìm kiếm lệnh tường lửa"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="defense-node-filter" className="sr-only">Lọc theo máy chủ</label>
            <select
              id="defense-node-filter"
              value={nodeFilter}
              onChange={(e) => setNodeFilter(e.target.value)}
              aria-label="Lọc theo máy chủ thực thi"
            >
              <option value="all">Tất cả máy chủ</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} ({n.ip_address})
                </option>
              ))}
            </select>

            <button
              type="button"
              className="btn btn-outline"
              onClick={() => void loadActions()}
              disabled={isLoading}
              title="Làm mới dữ liệu tường lửa"
            >
              <RefreshCw size={15} className={isLoading ? "spin" : ""} />
              Làm mới
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsManualModalOpen(true)}
            >
              <Plus size={16} />
              Chặn IP thủ công
            </button>
          </div>
        </div>

        {error && (
          <div className="connection-error" role="alert">
            <span>{error}</span>
            <button type="button" className="text-button" onClick={() => void loadActions()}>
              Thử lại
            </button>
          </div>
        )}

        {/* Unified Table */}
        {filteredActions.length === 0 ? (
          <div className="empty-state-card">
            <ShieldCheck size={36} style={{ color: "var(--status-ok)" }} />
            <h3>Tường lửa thông suốt — Không có dữ liệu</h3>
            <p>
              {searchQuery || nodeFilter !== "all" || statusFilter !== "all"
                ? "Không tìm thấy lệnh tường lửa nào phù hợp với bộ lọc hiện tại."
                : "Tất cả máy chủ đang hoạt động an toàn và không có địa chỉ IP nào bị khóa."}
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="host-table" aria-label="Danh sách lệnh tường lửa">
              <thead>
                <tr>
                  <th scope="col">Đối tượng xử lý</th>
                  <th scope="col">Máy chủ áp dụng</th>
                  <th scope="col">Nguồn kích hoạt</th>
                  <th scope="col">Thời gian khóa</th>
                  <th scope="col">Trạng thái</th>
                  <th scope="col" style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredActions.map((act) => {
                  const isApplied = act.status === "APPLIED";
                  const isFailed = act.status === "FAILED";
                  const isReverted = act.status === "REVERTED";

                  const durationSec = Number(act.command_payload?.duration_seconds ?? 0);
                  const createdAtMs = new Date(act.created_at).getTime();
                  const expiresAtMs = durationSec > 0 ? createdAtMs + durationSec * 1000 : 0;
                  const remainingSec = expiresAtMs > 0 ? Math.max(0, Math.floor((expiresAtMs - now) / 1000)) : 0;
                  const isExpiringSoon = remainingSec > 0 && remainingSec <= 60;
                  const isExpired = durationSec > 0 && remainingSec === 0;

                  return (
                    <tr key={act.id} className={isApplied ? "active-block-row" : ""}>
                      <td>
                        <div className="ip-cell">
                          {act.target_ip ? (
                            <code
                              className={`font-mono ${
                                isApplied
                                  ? "ip-pill-danger"
                                  : isFailed
                                    ? "ip-pill-failed"
                                    : "ip-pill"
                              }`}
                            >
                              {act.target_ip}
                            </code>
                          ) : (
                            <span className="font-mono" style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                              {String(act.command_payload?.service_name ?? act.command_payload?.target ?? "Dịch vụ")}
                            </span>
                          )}
                          <span
                            className={`action-type-badge font-mono ${
                              act.action_type === "RESTART_SERVICE"
                                ? "badge-action-restart"
                                : act.action_type === "RATE_LIMIT"
                                  ? "badge-action-limit"
                                  : act.action_type === "UNBLOCK_IP_NFTABLES"
                                    ? "badge-action-unblock"
                                    : "badge-action-drop"
                            }`}
                          >
                            {act.action_type === "RESTART_SERVICE"
                              ? "RESTART"
                              : act.action_type === "RATE_LIMIT"
                                ? "LIMIT"
                                : act.action_type === "UNBLOCK_IP_NFTABLES"
                                  ? "UNBLOCK"
                                  : "DROP"}
                          </span>
                        </div>
                      </td>
                      <td className="node-cell">
                        {(() => {
                          const node = nodes.find((n) => n.id === act.node_id);
                          if (node) {
                            return (
                              <div className="table-node-info">
                                <span className="node-hostname">{node.hostname}</span>
                                <span className="node-sub-ip font-mono">{node.ip_address}</span>
                              </div>
                            );
                          }
                          return (
                            <div className="table-node-info">
                              <span className="node-hostname font-mono">{act.node_id}</span>
                            </div>
                          );
                        })()}
                      </td>
                      <td>
                        {act.incident_id ? (
                          <span className="trigger-tag auto-trigger" title={`Kích hoạt từ sự cố ${act.incident_id}`}>
                            Sự cố {act.incident_id}
                          </span>
                        ) : (
                          <span className="trigger-tag manual-trigger">
                            Thủ công
                          </span>
                        )}
                      </td>
                      <td title={`Kích hoạt: ${formatRelativeTime(act.created_at)}`}>
                        {act.action_type === "RESTART_SERVICE" ? (
                          <span className="text-muted" style={{ fontSize: 13 }}>Tức thời</span>
                        ) : isApplied ? (
                          durationSec === 0 ? (
                            <span className="badge badge-neutral">Vĩnh viễn</span>
                          ) : isExpired ? (
                            <span className="badge badge-warn">
                              <Clock size={12} /> Hết hạn (Đang thu hồi)
                            </span>
                          ) : (
                            <span className={`badge ${isExpiringSoon ? "badge-warn" : "badge-crit"} font-mono timer-badge`}>
                              <Clock size={12} /> {formatDuration(remainingSec)} còn lại
                            </span>
                          )
                        ) : isReverted ? (
                          <span className="text-muted" style={{ fontSize: 13 }}>
                            {durationSec > 0 ? `${Math.round(durationSec / 60)} phút` : "Vĩnh viễn"}
                          </span>
                        ) : (
                          <span className="text-muted" style={{ fontSize: 13 }}>—</span>
                        )}
                      </td>
                      <td>
                        {isApplied && (
                          <span className="status-badge ok">
                            <i /> Đang áp dụng
                          </span>
                        )}
                        {isReverted && (
                          <span className="status-badge neutral">
                            <i /> Đã gỡ bỏ
                          </span>
                        )}
                        {isFailed && (
                          <span className="status-badge crit" title={act.error_message ?? "Lệnh thất bại"}>
                            <i /> Thất bại
                          </span>
                        )}
                        {act.status === "PENDING" && (
                          <span className="status-badge warn">
                            <i /> Đang chờ
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {isApplied ? (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => void handleUnblock(act)}
                            disabled={revertingId === act.id}
                            title="Gỡ bỏ lệnh chặn IP khỏi bảng tường lửa nftables"
                          >
                            {revertingId === act.id ? (
                              <RefreshCw size={13} className="spin" />
                            ) : (
                              <MinusCircle size={13} />
                            )}
                            Gỡ chặn
                          </button>
                        ) : isFailed ? (
                          <span
                            className="error-detail-text"
                            title={act.error_message ?? "Rào chắn an toàn từ chối IP"}
                          >
                            IP được bảo vệ
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Manual Block Modal */}
      <ManualBlockModal
        isOpen={isManualModalOpen}
        onClose={() => setIsManualModalOpen(false)}
        nodes={nodes}
        onActionCreated={handleActionCreated}
        isDemoMode={isDemoMode}
      />
    </div>
  );
}
