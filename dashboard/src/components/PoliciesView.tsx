import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Edit3,
  Flame,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
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
import { formatPolicyDuration } from "../presentation";
import { AddWhitelistModal } from "./AddWhitelistModal";
import { EditPolicyModal } from "./EditPolicyModal";

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
  const [editingPolicy, setEditingPolicy] = useState<DefensePolicy | null>(null);
  const [isCreatePolicyOpen, setIsCreatePolicyOpen] = useState(false);

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
    if (!window.confirm(`Bạn có chắc muốn xóa IP an toàn ${item.cidr}?`)) {
      return;
    }
    setDeletingWhitelistId(item.id);
    setFeedback(null);
    try {
      if (isDemoMode) {
        setWhitelist((prev) => prev.filter((w) => w.id !== item.id));
        setFeedback({
          type: "success",
          text: `Đã xóa IP ${item.cidr} khỏi danh sách an toàn.`,
        });
        return;
      }
      await deleteWhitelist(item.id);
      setWhitelist((prev) => prev.filter((w) => w.id !== item.id));
      setFeedback({
        type: "success",
        text: `Đã xóa IP ${item.cidr} thành công.`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Không thể xóa IP",
      });
    } finally {
      setDeletingWhitelistId(null);
    }
  };

  const handleWhitelistCreated = (newItem: IPWhitelist) => {
    setWhitelist((prev) => [newItem, ...prev]);
    setFeedback({
      type: "success",
      text: `Đã thêm IP ${newItem.cidr} vào danh sách an toàn!`,
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

  const handlePolicyUpdated = (updated: DefensePolicy) => {
    setPolicies((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    setFeedback({
      type: "success",
      text: `Đã cập nhật chính sách "${updated.name}" thành công!`,
    });
  };

  const handlePolicyCreated = (created: DefensePolicy) => {
    setPolicies((prev) => [created, ...prev]);
    setFeedback({
      type: "success",
      text: `Đã tạo chính sách bảo vệ "${created.name}" thành công!`,
    });
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
        <div className="connection-error" role="alert">
          <span>{error}</span>
        </div>
      )}

      {/* Sub-tab Navigation (Consistent Segmented Control) */}
      <div className="policies-segmented-bar" role="tablist" aria-label="Phân nhóm cấu hình">
        <button
          type="button"
          className={`segmented-tab ${activeTab === "whitelist" ? "active" : ""}`}
          onClick={() => setActiveTab("whitelist")}
          role="tab"
          aria-selected={activeTab === "whitelist"}
        >
          <ShieldCheck size={15} />
          <span>Danh sách an toàn</span>
          <span className="count-pill">{whitelist.length}</span>
        </button>

        <button
          type="button"
          className={`segmented-tab ${activeTab === "policies" ? "active" : ""}`}
          onClick={() => setActiveTab("policies")}
          role="tab"
          aria-selected={activeTab === "policies"}
        >
          <Sliders size={15} />
          <span>Chính sách bảo vệ tự động</span>
          <span className="count-pill">{policies.length}</span>
        </button>
      </div>

      {/* TAB 1: IP Whitelist */}
      {activeTab === "whitelist" && (
        <section className="panel whitelist-panel" aria-label="Danh sách IP an toàn">
          <div className="table-toolbar">
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

          {filteredWhitelist.length === 0 ? (
            <div className="empty-state-card">
              <ShieldCheck size={36} style={{ color: "var(--status-ok)" }} />
              <h3>Chưa có IP an toàn nào</h3>
              <p>Thêm các mạng nội bộ hoặc IP tin cậy để bảo vệ hệ thống khỏi việc tự chặn nhầm.</p>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setIsWhitelistModalOpen(true)}
              >
                <Plus size={15} /> Thêm IP an toàn đầu tiên
              </button>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="host-table" aria-label="Bảng IP an toàn">
                <thead>
                  <tr>
                    <th scope="col">IP / CIDR</th>
                    <th scope="col">Mô tả</th>
                    <th scope="col">Dự án áp dụng</th>
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
                        <span>{item.description || "—"}</span>
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
                          aria-label={`Xóa IP ${item.cidr}`}
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
        <section className="policies-container-section" aria-label="Danh mục chính sách bảo vệ">
          <div className="table-toolbar">
            <div className="policy-toolbar-title">
              <h3 style={{ fontSize: 15, margin: 0, fontWeight: 600 }}>Quy tắc tự động ứng phó</h3>
              <small style={{ color: "var(--text-muted)" }}>
                Hệ thống tự động kích hoạt ngăn chặn khi Detector phát hiện bất thường
              </small>
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

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setIsCreatePolicyOpen(true)}
                disabled={!effectiveProjectId}
              >
                <Plus size={16} />
                Thêm chính sách
              </button>
            </div>
          </div>

          {policies.length === 0 ? (
            <div className="panel empty-state-card">
              <Sliders size={36} style={{ color: "var(--brand-indigo)" }} />
              <h3>Chưa có chính sách tự động nào</h3>
              <p>
                Tạo quy tắc ứng phó tự động để hệ thống phản ứng khi Detector phát hiện tấn công mạng hoặc quá tải tài nguyên.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setIsCreatePolicyOpen(true)}
                disabled={!effectiveProjectId}
              >
                <Plus size={15} /> Tạo chính sách đầu tiên
              </button>
            </div>
          ) : (
            <div className="policies-grid-2x2">
            {policies.map((policy) => {
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
                        {policy.action_type === "ADAPTIVE" ? (
                          <span className="adaptive-badge">
                            <Zap size={12} /> Tự động tối ưu
                          </span>
                        ) : policy.action_type === "BLOCK_IP_NFTABLES" ? (
                          <span className="nftables-badge">
                            <Flame size={12} /> Khóa IP tường lửa
                          </span>
                        ) : policy.action_type === "RATE_LIMIT" ? (
                          <span className="rate-limit-badge">
                            <Sliders size={12} /> Giới hạn tốc độ
                          </span>
                        ) : policy.action_type === "CLEAR_OS_CACHE" ? (
                          <span className="cache-badge">
                            <Sparkles size={12} /> Giải phóng bộ nhớ đệm
                          </span>
                        ) : policy.action_type === "ALERT_ONLY" ? (
                          <span className="alert-badge">
                            <ShieldAlert size={12} /> Chỉ cảnh báo
                          </span>
                        ) : (
                          <span className="service-badge">
                            <RotateCcw size={12} /> Khởi động lại dịch vụ
                          </span>
                        )}
                      </div>
                      <h3>{policy.name}</h3>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Chỉnh sửa chính sách ${policy.name}`}
                        title="Chỉnh sửa chính sách"
                        onClick={() => setEditingPolicy(policy)}
                      >
                        <Edit3 size={15} />
                      </button>
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
                  </div>

                  <div className="policy-meta-grid">
                    <div className="policy-meta-item">
                      <span className="meta-label">Hành động</span>
                      <strong className="meta-value">
                        {policy.action_type === "ADAPTIVE"
                          ? "Tự động tối ưu"
                          : policy.action_type === "BLOCK_IP_NFTABLES"
                          ? "Khóa IP tường lửa"
                          : policy.action_type === "RATE_LIMIT"
                          ? "Giới hạn tốc độ"
                          : policy.action_type === "CLEAR_OS_CACHE"
                          ? "Giải phóng bộ nhớ đệm"
                          : policy.action_type === "ALERT_ONLY"
                          ? "Chỉ cảnh báo"
                          : "Khởi động lại dịch vụ"}
                      </strong>
                    </div>

                    <div className="policy-meta-item">
                      <span className="meta-label">
                        {policy.action_type === "ADAPTIVE"
                          ? "Tác động"
                          : policy.action_type === "ALERT_ONLY"
                          ? "Tác động"
                          : policy.action_type === "RESTART_SERVICE" || policy.action_type === "CLEAR_OS_CACHE"
                          ? "Tác động"
                          : policy.action_type === "RATE_LIMIT"
                          ? "Thời gian áp dụng"
                          : "Thời gian chặn IP"}
                      </span>
                      <strong className="meta-value">
                        {policy.action_type === "ADAPTIVE"
                          ? "Phân cấp tối ưu"
                          : policy.action_type === "ALERT_ONLY"
                          ? "Chỉ ghi nhận"
                          : policy.action_type === "RESTART_SERVICE" || policy.action_type === "CLEAR_OS_CACHE"
                          ? "Tức thời"
                          : formatPolicyDuration(policy.block_duration_seconds)}
                      </strong>
                    </div>

                    <div className="policy-meta-item">
                      <span className="meta-label">Thời gian nghỉ</span>
                      <strong className="meta-value">
                        <Clock size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                        {formatPolicyDuration(policy.cooldown_seconds)}
                      </strong>
                    </div>
                  </div>

                  <div className="policy-controls">
                    <div className="policy-toggle-row">
                      <div className="toggle-info">
                        <strong>{policy.is_active ? "Đang bật" : "Đang tắt"}</strong>
                        <small>
                          {!policy.is_active
                            ? "Tạm thời vô hiệu hóa quy tắc này"
                            : policy.action_type === "ALERT_ONLY"
                            ? "Chỉ ghi nhận cảnh báo, không can thiệp máy chủ"
                            : "Tự động kích hoạt bảo vệ khi phát hiện sự cố"}
                        </small>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={policy.is_active}
                        className={`toggle-switch ${policy.is_active ? "toggle-on" : "toggle-off"}`}
                        onClick={() => void handleToggleActive(policy)}
                        disabled={isToggling}
                        aria-label={`Bật tắt chính sách ${policy.name}`}
                      >
                        <span className="toggle-handle" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
            </div>
          )}
        </section>
      )}

      {/* Add Whitelist Modal */}
      <AddWhitelistModal
        isOpen={isWhitelistModalOpen}
        onClose={() => setIsWhitelistModalOpen(false)}
        projectId={effectiveProjectId}
        existingWhitelist={whitelist}
        onWhitelistCreated={handleWhitelistCreated}
        isDemoMode={isDemoMode}
      />

      {/* Create / Edit Policy Modal */}
      <EditPolicyModal
        isOpen={Boolean(editingPolicy) || isCreatePolicyOpen}
        onClose={() => {
          setEditingPolicy(null);
          setIsCreatePolicyOpen(false);
        }}
        policy={editingPolicy}
        projectId={effectiveProjectId}
        onPolicyUpdated={handlePolicyUpdated}
        onPolicyCreated={handlePolicyCreated}
        isDemoMode={isDemoMode}
      />
    </div>
  );
}
