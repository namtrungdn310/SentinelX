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
  ShieldAlert,
  ShieldCheck,
  XCircle,
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

function getKernelSetName(targetIp: string | null): string {
  if (!targetIp) return "sentinelx.blocked_v4";
  return targetIp.includes(":") ? "inet sentinelx.blocked_v6" : "inet sentinelx.blocked_v4";
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
      setError(err instanceof Error ? err.message : "Lỗi tải danh sách lệnh phòng thủ");
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
          text: `Đã gỡ chặn thành công IP ${action.target_ip ?? "mục tiêu"} khỏi kernel nftables set!`,
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
      text: `Đã kích hoạt thành công lệnh phòng thủ cho IP ${newAction.target_ip ?? "mục tiêu"}!`,
    });
  };

  // Node hostname helper
  const getNodeName = (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId);
    return node ? `${node.hostname} (${node.ip_address})` : nodeId;
  };

  // Filtered lists
  const activeBlockedActions = useMemo(() => {
    return actions.filter(
      (a) => a.status === "APPLIED" && a.action_type === "BLOCK_IP_NFTABLES" && a.target_ip
    );
  }, [actions]);

  const filteredHistory = useMemo(() => {
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

  // KPIs
  const totalCount = actions.length;
  const activeBlockCount = activeBlockedActions.length;
  const appliedCount = actions.filter((a) => a.status === "APPLIED").length;
  const failedCount = actions.filter((a) => a.status === "FAILED").length;
  const successRate = totalCount > 0 ? Math.round((appliedCount / (appliedCount + failedCount || 1)) * 100) : 100;
  const revertedCount = actions.filter((a) => a.status === "REVERTED").length;

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
        <article className="kpi-card">
          <div className="kpi-meta">
            <span className="kpi-label">IP đang bị chặn (Active)</span>
            <Flame size={18} style={{ color: "var(--status-crit)" }} />
          </div>
          <strong className="kpi-value" style={{ color: "var(--status-crit)" }}>
            {activeBlockCount}
          </strong>
          <small className="kpi-hint">Đang DROP trực tiếp tại kernel hook</small>
        </article>

        <article className="kpi-card">
          <div className="kpi-meta">
            <span className="kpi-label">Tổng lệnh phòng thủ</span>
            <Shield size={18} style={{ color: "var(--brand-indigo)" }} />
          </div>
          <strong className="kpi-value">{totalCount}</strong>
          <small className="kpi-hint">Bao gồm tự động và thủ công</small>
        </article>

        <article className="kpi-card">
          <div className="kpi-meta">
            <span className="kpi-label">Tỷ lệ thực thi thành công</span>
            <CheckCircle2 size={18} style={{ color: "var(--status-ok)" }} />
          </div>
          <strong className="kpi-value" style={{ color: "var(--status-ok)" }}>
            {successRate}%
          </strong>
          <small className="kpi-hint">
            {appliedCount} thành công · {failedCount} thất bại
          </small>
        </article>

        <article className="kpi-card">
          <div className="kpi-meta">
            <span className="kpi-label">Đã thu hồi / Gỡ bỏ</span>
            <ShieldCheck size={18} style={{ color: "var(--status-neutral)" }} />
          </div>
          <strong className="kpi-value">{revertedCount}</strong>
          <small className="kpi-hint">Hết hạn hoặc do admin gỡ</small>
        </article>
      </section>

      {/* Toolbar */}
      <div className="defense-toolbar">
        <div className="search-box">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            placeholder="Tìm theo IP mục tiêu, mã lệnh, máy chủ..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Tìm kiếm lệnh phòng thủ"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="defense-node-filter" className="sr-only">Lọc theo máy chủ</label>
          <select
            id="defense-node-filter"
            value={nodeFilter}
            onChange={(e) => setNodeFilter(e.target.value)}
          >
            <option value="all">Tất cả máy chủ</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.hostname} ({n.ip_address})
              </option>
            ))}
          </select>

          <label htmlFor="defense-status-filter" className="sr-only">Lọc theo trạng thái</label>
          <select
            id="defense-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="APPLIED">Đang áp dụng (APPLIED)</option>
            <option value="REVERTED">Đã gỡ bỏ (REVERTED)</option>
            <option value="FAILED">Thất bại (FAILED)</option>
            <option value="PENDING">Đang chờ (PENDING)</option>
          </select>

          <button
            type="button"
            className="btn btn-outline"
            onClick={() => void loadActions()}
            disabled={isLoading}
            aria-label="Làm mới dữ liệu phòng thủ"
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
        <div className="panel error-panel" role="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button type="button" className="text-button" onClick={() => void loadActions()}>
            Thử lại
          </button>
        </div>
      )}

      {/* SECTION 1: Active Blocked IPs Table */}
      <section className="panel defense-active-section" aria-label="Danh sách IP đang bị khóa">
        <div className="panel-header">
          <div className="section-header-title">
            <Flame size={18} style={{ color: "var(--status-crit)" }} />
            <h2>Bảng phần tử khóa hoạt động (Active nftables Drop Sets)</h2>
            <span className="badge badge-crit font-mono">{activeBlockedActions.length} IP</span>
          </div>
          <small className="section-header-subtitle">
            Các IP bị chặn lưu lượng truy cập trực tiếp tại Linux kernel hook (table inet sentinelx, set blocked_v4/v6)
          </small>
        </div>

        {activeBlockedActions.length === 0 ? (
          <div className="empty-state-card">
            <ShieldCheck size={36} style={{ color: "var(--status-ok)" }} />
            <h3>Tường lửa thông suốt — Không có IP nào đang bị khóa</h3>
            <p>
              Tất cả các máy chủ đang hoạt động bình thường và không ghi nhận lưu lượng độc hại bị chặn tại kernel set.
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="host-table defense-table">
              <thead>
                <tr>
                  <th scope="col">IP Mục tiêu</th>
                  <th scope="col">Kernel Table &amp; Set</th>
                  <th scope="col">Máy chủ thực thi</th>
                  <th scope="col">Áp dụng lúc</th>
                  <th scope="col">Thời hạn</th>
                  <th scope="col">Đếm ngược tự động gỡ</th>
                  <th scope="col" style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {activeBlockedActions.map((act) => {
                  const durationSec = Number(act.command_payload?.duration_seconds ?? 0);
                  const createdAtMs = new Date(act.created_at).getTime();
                  const expiresAtMs = durationSec > 0 ? createdAtMs + durationSec * 1000 : 0;
                  const remainingSec = expiresAtMs > 0 ? Math.max(0, Math.floor((expiresAtMs - now) / 1000)) : 0;
                  const isExpiringSoon = remainingSec > 0 && remainingSec <= 60;
                  const isExpired = durationSec > 0 && remainingSec === 0;

                  return (
                    <tr key={act.id} className="active-block-row">
                      <td>
                        <div className="ip-cell">
                          <code className="font-mono ip-pill-danger">{act.target_ip}</code>
                        </div>
                      </td>
                      <td>
                        <span className="font-mono kernel-set-tag">
                          {getKernelSetName(act.target_ip)}
                        </span>
                      </td>
                      <td>
                        <span className="node-tag">{getNodeName(act.node_id)}</span>
                      </td>
                      <td>
                        <span title={act.created_at}>{formatRelativeTime(act.created_at)}</span>
                      </td>
                      <td>
                        {durationSec === 0 ? "Vĩnh viễn" : `${Math.floor(durationSec / 60)} phút`}
                      </td>
                      <td>
                        {durationSec === 0 ? (
                          <span className="badge badge-neutral">Vĩnh viễn</span>
                        ) : isExpired ? (
                          <span className="badge badge-warn">
                            <Clock size={12} /> Hết hạn (Đang thu hồi)
                          </span>
                        ) : (
                          <span className={`badge ${isExpiringSoon ? "badge-warn" : "badge-crit"} font-mono timer-badge`}>
                            <Clock size={12} /> {formatDuration(remainingSec)} còn lại
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => void handleUnblock(act)}
                          disabled={revertingId === act.id}
                        >
                          {revertingId === act.id ? (
                            <RefreshCw size={13} className="spin" />
                          ) : (
                            <MinusCircle size={13} />
                          )}
                          Gỡ chặn ngay
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* SECTION 2: Defense Actions Audit Trail */}
      <section className="panel defense-audit-section" aria-label="Nhật ký lệnh phòng thủ">
        <div className="panel-header">
          <div className="section-header-title">
            <ShieldAlert size={18} style={{ color: "var(--brand-indigo)" }} />
            <h2>Nhật ký lệnh phòng thủ (Defense Audit Trail)</h2>
            <span className="badge badge-neutral font-mono">{filteredHistory.length} lệnh</span>
          </div>
          <small className="section-header-subtitle">
            Toàn bộ lịch sử lệnh chặn/gỡ chặn IP, khởi động lại dịch vụ được ghi nhận và đồng bộ từ các Agent.
          </small>
        </div>

        {filteredHistory.length === 0 ? (
          <div className="empty-state-card">
            <p>Không tìm thấy lệnh phòng thủ nào phù hợp với bộ lọc hiện tại.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="host-table">
              <thead>
                <tr>
                  <th scope="col">Thời gian</th>
                  <th scope="col">Mã lệnh</th>
                  <th scope="col">Loại hành động</th>
                  <th scope="col">Mục tiêu</th>
                  <th scope="col">Máy chủ</th>
                  <th scope="col">Nguồn kích hoạt</th>
                  <th scope="col">Trạng thái</th>
                  <th scope="col">Chi tiết / Lỗi</th>
                  <th scope="col" style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((act) => {
                  const isApplied = act.status === "APPLIED";
                  const isFailed = act.status === "FAILED";
                  const isReverted = act.status === "REVERTED";

                  return (
                    <tr key={act.id}>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <span title={act.created_at}>{formatRelativeTime(act.created_at)}</span>
                      </td>
                      <td>
                        <code className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                          {act.id}
                        </code>
                      </td>
                      <td>
                        <span className="action-type-badge font-mono">
                          {act.action_type === "BLOCK_IP_NFTABLES" ? "Khóa IP (nftables)" : act.action_type}
                        </span>
                      </td>
                      <td>
                        {act.target_ip ? (
                          <code className="font-mono ip-pill">{act.target_ip}</code>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td>
                        <span className="node-tag">{getNodeName(act.node_id)}</span>
                      </td>
                      <td>
                        {act.incident_id ? (
                          <span className="trigger-tag auto-trigger">
                            Sự cố {act.incident_id}
                          </span>
                        ) : (
                          <span className="trigger-tag manual-trigger">
                            Thủ công
                          </span>
                        )}
                      </td>
                      <td>
                        {isApplied && (
                          <span className="status-badge ok">
                            <i /> Đang áp dụng
                          </span>
                        )}
                        {isReverted && (
                          <span className="status-badge unknown">
                            <i /> Đã gỡ bỏ
                          </span>
                        )}
                        {isFailed && (
                          <span className="status-badge crit">
                            <i /> Thất bại
                          </span>
                        )}
                        {!isApplied && !isReverted && !isFailed && (
                          <span className="status-badge warn">
                            <i /> {act.status}
                          </span>
                        )}
                      </td>
                      <td>
                        {act.error_message ? (
                          <span className="error-detail-text" title={act.error_message}>
                            <XCircle size={13} style={{ color: "var(--status-crit)" }} />
                            {act.error_message}
                          </span>
                        ) : isApplied ? (
                          <span className="success-detail-text">
                            <CheckCircle2 size={13} style={{ color: "var(--status-ok)" }} />
                            Kernel drop set active
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {isApplied && act.action_type === "BLOCK_IP_NFTABLES" && (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => void handleUnblock(act)}
                            disabled={revertingId === act.id}
                          >
                            {revertingId === act.id ? "Đang gỡ..." : "Gỡ chặn"}
                          </button>
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

