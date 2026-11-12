import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  Info,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sliders,
  Trash2,
  Zap,
} from "lucide-react";
import type { Project, DefensePolicy, IPWhitelist } from "../types";
import {
  fetchPolicies,
  updatePolicy,
  deletePolicy,
  fetchWhitelist,
  deleteWhitelist,
} from "../api";
import { MOCK_POLICIES, MOCK_WHITELIST } from "../mockData";
import { AddWhitelistModal } from "./AddWhitelistModal";

interface Props {
  selectedProjectId: string | null;
  projects: Project[];
  isDemoMode: boolean;
}

type TabType = "whitelist" | "policies";

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

export function PoliciesView({ selectedProjectId, projects, isDemoMode }: Props) {
  const [activeTab, setActiveTab] = useState<TabType>("whitelist");
  const effectiveProjectId = selectedProjectId || projects[0]?.id || "";

  // Whitelist State
  const [whitelist, setWhitelist] = useState<IPWhitelist[]>(() => {
    if (isDemoMode) {
      return selectedProjectId
        ? MOCK_WHITELIST.filter((w) => w.project_id === selectedProjectId)
        : MOCK_WHITELIST;
    }
    return [];
  });
  const [isWhitelistModalOpen, setIsWhitelistModalOpen] = useState(false);
  const [whitelistSearch, setWhitelistSearch] = useState("");
  const [isWhitelistLoading, setIsWhitelistLoading] = useState(false);
  const [deletingWhitelistId, setDeletingWhitelistId] = useState<string | null>(null);

  // Policies State
  const [policies, setPolicies] = useState<DefensePolicy[]>(() => {
    return isDemoMode ? MOCK_POLICIES : [];
  });
  const [isPoliciesLoading, setIsPoliciesLoading] = useState(false);
  const [togglingPolicyId, setTogglingPolicyId] = useState<string | null>(null);

  // Common UI State
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load Whitelist
  const loadWhitelist = useCallback(async () => {
    if (!effectiveProjectId) return;
    setIsWhitelistLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        let items = MOCK_WHITELIST;
        if (selectedProjectId) {
          items = items.filter((w) => w.project_id === selectedProjectId);
        }
        setWhitelist(items);
        return;
      }
      const data = await fetchWhitelist(effectiveProjectId);
      setWhitelist(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi tải danh sách IP an toàn");
    } finally {
      setIsWhitelistLoading(false);
    }
  }, [effectiveProjectId, selectedProjectId, isDemoMode]);

  // Load Policies
  const loadPolicies = useCallback(async () => {
    setIsPoliciesLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        setPolicies(MOCK_POLICIES);
        return;
      }
      const data = await fetchPolicies(effectiveProjectId || undefined);
      setPolicies(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi tải danh mục chính sách");
    } finally {
      setIsPoliciesLoading(false);
    }
  }, [effectiveProjectId, isDemoMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadWhitelist();
      void loadPolicies();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadWhitelist, loadPolicies]);

  // Handle Delete Whitelist
  const handleDeleteWhitelist = async (item: IPWhitelist) => {
    if (!window.confirm(`Bạn có chắc muốn xóa dải IP an toàn ${item.cidr}?`)) {
      return;
    }
    setDeletingWhitelistId(item.id);
    setFeedback(null);
    try {
      if (isDemoMode) {
        setWhitelist((prev) => prev.filter((w) => w.id !== item.id));
        setFeedback({
          type: "success",
          text: `Đã xóa dải IP ${item.cidr} khỏi danh sách an toàn.`,
        });
        return;
      }
      await deleteWhitelist(item.id);
      setWhitelist((prev) => prev.filter((w) => w.id !== item.id));
      setFeedback({
        type: "success",
        text: `Đã xóa dải IP ${item.cidr} thành công.`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa dải IP",
      });
    } finally {
      setDeletingWhitelistId(null);
    }
  };

  const handleWhitelistCreated = (newItem: IPWhitelist) => {
    setWhitelist((prev) => [newItem, ...prev]);
    setFeedback({
      type: "success",
      text: `Đã thêm dải IP ${newItem.cidr} vào danh sách an toàn!`,
    });
  };

  // Handle Policy Toggles
  const handleToggleActive = async (policy: DefensePolicy) => {
    setTogglingPolicyId(policy.id);
    const nextVal = !policy.is_active;
    try {
      if (isDemoMode) {
        setPolicies((prev) =>
          prev.map((p) => (p.id === policy.id ? { ...p, is_active: nextVal } : p))
        );
        setFeedback({
          type: "success",
          text: `Đã ${nextVal ? "kích hoạt" : "tạm dừng"} chính sách "${policy.name}".`,
        });
        return;
      }
      const updated = await updatePolicy(policy.id, { is_active: nextVal });
      setPolicies((prev) => prev.map((p) => (p.id === policy.id ? updated : p)));
      setFeedback({
        type: "success",
        text: `Đã cập nhật trạng thái chính sách "${policy.name}".`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Lỗi cập nhật chính sách",
      });
    } finally {
      setTogglingPolicyId(null);
    }
  };

  const handleToggleAutoExecute = async (policy: DefensePolicy) => {
    setTogglingPolicyId(policy.id);
    const nextVal = !policy.is_auto_execute;
    try {
      if (isDemoMode) {
        setPolicies((prev) =>
          prev.map((p) => (p.id === policy.id ? { ...p, is_auto_execute: nextVal } : p))
        );
        setFeedback({
          type: "success",
          text: `Chế độ tự động cho "${policy.name}" đã được ${nextVal ? "BẬT" : "TẮT (cần duyệt)"}.`,
        });
        return;
      }
      const updated = await updatePolicy(policy.id, { is_auto_execute: nextVal });
      setPolicies((prev) => prev.map((p) => (p.id === policy.id ? updated : p)));
      setFeedback({
        type: "success",
        text: `Đã cập nhật cấu hình tự động thực thi.`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Lỗi cập nhật chính sách",
      });
    } finally {
      setTogglingPolicyId(null);
    }
  };

  // Handle Delete Policy
  const handleDeletePolicy = async (policy: DefensePolicy) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa chính sách "${policy.name}"?`)) {
      return;
    }
    try {
      if (isDemoMode) {
        setPolicies((prev) => prev.filter((p) => p.id !== policy.id));
        setFeedback({
          type: "success",
          text: `Đã xóa chính sách "${policy.name}".`,
        });
        return;
      }
      await deletePolicy(policy.id);
      setPolicies((prev) => prev.filter((p) => p.id !== policy.id));
      setFeedback({
        type: "success",
        text: `Đã xóa chính sách "${policy.name}" thành công.`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa chính sách",
      });
    }
  };

  const getProjectName = (projId: string) => {
    const proj = projects.find((p) => p.id === projId);
    return proj ? proj.name : projId;
  };

  const filteredWhitelist = useMemo(() => {
    return whitelist.filter((item) => {
      if (!whitelistSearch.trim()) return true;
      const q = whitelistSearch.toLowerCase();
      const matchCidr = item.cidr.toLowerCase().includes(q);
      const matchDesc = item.description?.toLowerCase().includes(q) ?? false;
      return matchCidr || matchDesc;
    });
  }, [whitelist, whitelistSearch]);

  return (
    <div className="policies-view">
      {/* Feedback banner */}
      {feedback && (
        <div
          className={`feedback-banner ${feedback.type === "success" ? "feedback-success" : "feedback-error"}`}
          role="alert"
        >
          {feedback.type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <span>{feedback.text}</span>
          <button
            type="button"
            className="icon-button"
            aria-label="Đóng thông báo"
            onClick={() => setFeedback(null)}
          >
            ×
          </button>
        </div>
      )}

      {error && (
        <div className="panel error-panel" role="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Sub-tab Navigation */}
      <div className="subtabs-bar">
        <button
          type="button"
          className={`subtab-button ${activeTab === "whitelist" ? "active" : ""}`}
          onClick={() => setActiveTab("whitelist")}
          aria-selected={activeTab === "whitelist"}
          role="tab"
        >
          <ShieldCheck size={16} />
          <span>Danh sách IP An Toàn (Whitelist)</span>
          <span className="count-badge">{whitelist.length}</span>
        </button>

        <button
          type="button"
          className={`subtab-button ${activeTab === "policies" ? "active" : ""}`}
          onClick={() => setActiveTab("policies")}
          aria-selected={activeTab === "policies"}
          role="tab"
        >
          <Sliders size={16} />
          <span>Chính sách Phòng thủ (Defense Policies)</span>
          <span className="count-badge">{policies.length}</span>
        </button>
      </div>

      {/* TAB 1: IP Whitelist */}
      {activeTab === "whitelist" && (
        <section className="panel whitelist-section" aria-label="Danh sách IP an toàn">
          <div className="tab-toolbar">
            <div className="search-box">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                placeholder="Tìm theo CIDR hoặc mô tả..."
                value={whitelistSearch}
                onChange={(e) => setWhitelistSearch(e.target.value)}
                aria-label="Tìm kiếm CIDR"
              />
            </div>

            <div className="toolbar-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => void loadWhitelist()}
                disabled={isWhitelistLoading}
                aria-label="Tải lại danh sách an toàn"
              >
                <RefreshCw size={15} className={isWhitelistLoading ? "spin" : ""} />
                Làm mới
              </button>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setIsWhitelistModalOpen(true)}
              >
                <Plus size={16} />
                Thêm IP an toàn
              </button>
            </div>
          </div>

          <div className="info-banner">
            <Info size={16} />
            <span>
              <strong>Nguyên tắc An Toàn Cốt Lõi:</strong> Các IP thuộc danh sách Whitelist sẽ không bao giờ bị khóa bởi tường lửa nftables hoặc chịu các biện pháp cắt giảm lưu lượng. Hãy thêm dải IP Gateway, DNS nội bộ và IP kết nối quản trị để tránh mất quyền truy cập.
            </span>
          </div>

          {filteredWhitelist.length === 0 ? (
            <div className="empty-state-card">
              <ShieldCheck size={36} style={{ color: "var(--brand-indigo)" }} />
              <h3>Chưa có dải IP an toàn nào</h3>
              <p>Thêm các dải mạng nội bộ hoặc IP tin cậy để bảo vệ hệ thống khỏi việc tự chặn nhầm.</p>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setIsWhitelistModalOpen(true)}
              >
                <Plus size={15} /> Thêm dải IP an toàn đầu tiên
              </button>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="host-table">
                <thead>
                  <tr>
                    <th scope="col">Dải IP / CIDR</th>
                    <th scope="col">Mô tả mục đích</th>
                    <th scope="col">Dự án</th>
                    <th scope="col">Thời điểm thêm</th>
                    <th scope="col" style={{ textAlign: "right" }}>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredWhitelist.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="cidr-cell">
                          <ShieldCheck size={14} style={{ color: "var(--status-ok)" }} />
                          <code className="font-mono ip-pill-safe">{item.cidr}</code>
                        </div>
                      </td>
                      <td>
                        <span>{item.description || "Không có mô tả"}</span>
                      </td>
                      <td>
                        <span className="project-badge">{getProjectName(item.project_id)}</span>
                      </td>
                      <td>
                        <span title={item.created_at}>{formatRelativeTime(item.created_at)}</span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          type="button"
                          className="icon-button danger-icon-button"
                          aria-label={`Xóa dải IP ${item.cidr}`}
                          title="Xóa khỏi danh sách an toàn"
                          onClick={() => void handleDeleteWhitelist(item)}
                          disabled={deletingWhitelistId === item.id}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* TAB 2: Defense Policies */}
      {activeTab === "policies" && (
        <section className="policies-section" aria-label="Danh mục chính sách phòng thủ">
          <div className="tab-toolbar">
            <div>
              <h2 style={{ fontSize: 16, margin: 0, fontWeight: 600 }}>Quy tắc tự động ứng phó</h2>
              <small style={{ color: "var(--text-muted)" }}>Cấu hình hành vi phòng thủ hạt nhân khi phát hiện tấn công</small>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => void loadPolicies()}
                disabled={isPoliciesLoading}
                aria-label="Tải lại danh mục chính sách"
              >
                <RefreshCw size={15} className={isPoliciesLoading ? "spin" : ""} />
                Làm mới chính sách
              </button>
            </div>
          </div>

          <div className="info-banner" style={{ marginBottom: 16 }}>
            <Zap size={16} />
            <span>
              <strong>Cơ chế Pipeline Phòng thủ SentinelX:</strong> Khi Detector phát hiện bất thường, Policy Engine sẽ khớp với chính sách tương ứng để kích hoạt lệnh chặn IP bằng Linux nftables hoặc khởi động lại dịch vụ sau chu kỳ Cooldown.
            </span>
          </div>

          <div className="policies-grid">
            {policies.map((policy) => {
              const isNftables = policy.action_type === "BLOCK_IP_NFTABLES";
              const isToggling = togglingPolicyId === policy.id;

              return (
                <article
                  key={policy.id}
                  className={`panel policy-card ${policy.is_active ? "policy-card-active" : "policy-card-disabled"}`}
                >
                  <div className="policy-card-header">
                    <div>
                      <div className="policy-card-eyebrow">
                        <span className="detector-event-tag font-mono">
                          {policy.event_type}
                        </span>
                        {isNftables && (
                          <span className="nftables-badge">
                            <Flame size={12} /> Kernel nftables
                          </span>
                        )}
                      </div>
                      <h3>{policy.name}</h3>
                    </div>
                    <button
                      type="button"
                      className="icon-button danger-icon-button"
                      aria-label={`Xóa chính sách ${policy.name}`}
                      title="Xóa chính sách"
                      onClick={() => void handleDeletePolicy(policy)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>

                  <div className="policy-meta-grid">
                    <div className="policy-meta-item">
                      <span className="meta-label">Hành động thực thi</span>
                      <strong className="meta-value font-mono">
                        {policy.action_type === "BLOCK_IP_NFTABLES"
                          ? "Khóa IP (DROP)"
                          : policy.action_type}
                      </strong>
                    </div>

                    <div className="policy-meta-item">
                      <span className="meta-label">Thời hạn khóa</span>
                      <strong className="meta-value">
                        {policy.block_duration_seconds === 0
                          ? "Vĩnh viễn"
                          : `${Math.floor(policy.block_duration_seconds / 60)} phút (${policy.block_duration_seconds}s)`}
                      </strong>
                    </div>

                    <div className="policy-meta-item">
                      <span className="meta-label">Chu kỳ Cooldown</span>
                      <strong className="meta-value">
                        <Clock size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                        {policy.cooldown_seconds} giây
                      </strong>
                    </div>
                  </div>

                  <div className="policy-controls">
                    {/* Toggle: Auto Execute */}
                    <div className="policy-toggle-row">
                      <div className="toggle-info">
                        <strong>Tự động thực thi (Auto Execute)</strong>
                        <small>
                          {policy.is_auto_execute
                            ? "Tự động áp dụng lệnh phòng thủ qua nftables ngay khi phát hiện"
                            : "Yêu cầu Quản trị viên duyệt thủ công trên giao diện Sự Cố"}
                        </small>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={policy.is_auto_execute}
                        className={`toggle-switch ${policy.is_auto_execute ? "toggle-on" : "toggle-off"}`}
                        onClick={() => void handleToggleAutoExecute(policy)}
                        disabled={isToggling || !policy.is_active}
                        aria-label={`Bật tắt tự động thực thi cho ${policy.name}`}
                      >
                        <span className="toggle-handle" />
                      </button>
                    </div>

                    {/* Toggle: Active */}
                    <div className="policy-toggle-row">
                      <div className="toggle-info">
                        <strong>Trạng thái chính sách</strong>
                        <small>
                          {policy.is_active ? "Chính sách đang bật" : "Chính sách tạm thời bị vô hiệu hóa"}
                        </small>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={policy.is_active}
                        className={`toggle-switch ${policy.is_active ? "toggle-on" : "toggle-off"}`}
                        onClick={() => void handleToggleActive(policy)}
                        disabled={isToggling}
                        aria-label={`Kích hoạt chính sách ${policy.name}`}
                      >
                        <span className="toggle-handle" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Add Whitelist Modal */}
      <AddWhitelistModal
        isOpen={isWhitelistModalOpen}
        onClose={() => setIsWhitelistModalOpen(false)}
        projectId={effectiveProjectId}
        onWhitelistCreated={handleWhitelistCreated}
        isDemoMode={isDemoMode}
      />
    </div>
  );
}
