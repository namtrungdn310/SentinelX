import { useId, useState } from "react";
import { Sliders, ShieldAlert, X, Check } from "lucide-react";
import type { DefensePolicy } from "../types";
import { updatePolicy } from "../api";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  policy: DefensePolicy | null;
  onPolicyUpdated: (updated: DefensePolicy) => void;
  isDemoMode: boolean;
}

export function EditPolicyModal({
  isOpen,
  onClose,
  policy,
  onPolicyUpdated,
  isDemoMode,
}: Props) {
  if (!isOpen || !policy) return null;

  return (
    <EditPolicyModalForm
      key={policy.id}
      onClose={onClose}
      policy={policy}
      onPolicyUpdated={onPolicyUpdated}
      isDemoMode={isDemoMode}
    />
  );
}

function EditPolicyModalForm({
  onClose,
  policy,
  onPolicyUpdated,
  isDemoMode,
}: {
  onClose: () => void;
  policy: DefensePolicy;
  onPolicyUpdated: (updated: DefensePolicy) => void;
  isDemoMode: boolean;
}) {
  const id = useId();
  const [actionType, setActionType] = useState(policy.action_type);
  const [cooldownSeconds, setCooldownSeconds] = useState(policy.cooldown_seconds);
  const [blockDurationMinutes, setBlockDurationMinutes] = useState(
    policy.block_duration_seconds === 0 ? 0 : Math.floor(policy.block_duration_seconds / 60)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNetworkDetector =
    policy.event_type.includes("flood") ||
    policy.event_type.includes("scan") ||
    policy.event_type.includes("traffic");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const updatePayload = {
      name: policy.name,
      action_type: actionType,
      cooldown_seconds: cooldownSeconds,
      block_duration_seconds:
        actionType === "RESTART_SERVICE" || actionType === "CLEAR_OS_CACHE" || actionType === "ALERT_ONLY"
          ? 0
          : blockDurationMinutes * 60,
      is_auto_execute: actionType !== "ALERT_ONLY",
    };

    try {
      if (isDemoMode) {
        const updatedPolicy: DefensePolicy = {
          ...policy,
          ...updatePayload,
        };
        onPolicyUpdated(updatedPolicy);
        onClose();
        return;
      }

      const res = await updatePolicy(policy.id, updatePayload);
      onPolicyUpdated(res);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi cập nhật chính sách");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="policy-edit-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Sliders size={15} style={{ color: "var(--brand-indigo)" }} /> Cấu hình phản ứng tự động
          </span>
          <h2 id={`${id}-title`}>{policy.name}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng biểu mẫu chỉnh sửa"
          onClick={onClose}
          disabled={loading}
        >
          <X size={18} />
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="modal-body">
          {error && (
            <div className="form-error" role="alert">
              <ShieldAlert size={15} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label>Sự kiện kích hoạt</label>
            <div style={{ padding: "8px 12px", background: "var(--bg-subtle)", borderRadius: "var(--radius-xs)" }}>
              <code className="font-mono text-muted" style={{ fontSize: 13 }}>{policy.event_type}</code>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-action`}>Hành động</label>
            <select
              id={`${id}-action`}
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              disabled={loading}
              style={{ width: "100%", padding: "8px 10px" }}
            >
              {isNetworkDetector ? (
                <>
                  <option value="BLOCK_IP_NFTABLES">Khóa địa chỉ IP nguồn qua tường lửa</option>
                  <option value="ALERT_ONLY">Chỉ ghi nhận cảnh báo</option>
                </>
              ) : (
                <>
                  <option value="ADAPTIVE">Tự động thích ứng tối ưu</option>
                  <option value="RESTART_SERVICE">Khởi động lại dịch vụ hoặc tiến trình</option>
                  <option value="CLEAR_OS_CACHE">Giải phóng bộ nhớ đệm hệ điều hành</option>
                  <option value="ALERT_ONLY">Chỉ ghi nhận cảnh báo</option>
                </>
              )}
            </select>
            <small className="form-hint">
              {actionType === "BLOCK_IP_NFTABLES" && "Tạo luật chặn tại tường lửa nhằm ngắt toàn bộ gói tin từ địa chỉ IP nguồn tấn công."}
              {actionType === "ADAPTIVE" && "Hệ thống tự động chẩn đoán: Nếu do bộ nhớ đệm đĩa thì tự động giải phóng đệm không làm gián đoạn dịch vụ; nếu do tiến trình rò rỉ bộ nhớ thì tự động khởi động lại đúng tiến trình đó."}
              {actionType === "RESTART_SERVICE" && "Tự động gửi tín hiệu khởi động lại tiến trình gây quá tải khi vượt ngưỡng."}
              {actionType === "CLEAR_OS_CACHE" && "Đồng bộ và giải phóng bộ nhớ đệm của nhân hệ điều hành."}
              {actionType === "ALERT_ONLY" && "Chỉ lưu nhật ký sự cố và thông báo cho người quản trị, không can thiệp máy chủ."}
            </small>
          </div>

          {/* Duration only applicable for blocking */}
          {actionType === "BLOCK_IP_NFTABLES" && (
            <div className="form-group">
              <label htmlFor={`${id}-duration`}>Thời hạn khóa địa chỉ IP</label>
              <select
                id={`${id}-duration`}
                value={blockDurationMinutes}
                onChange={(e) => setBlockDurationMinutes(Number(e.target.value))}
                disabled={loading}
              >
                <option value={5}>5 phút</option>
                <option value={10}>10 phút</option>
                <option value={15}>15 phút</option>
                <option value={30}>30 phút</option>
                <option value={60}>1 giờ</option>
                <option value={0}>Vĩnh viễn đến khi gỡ thủ công</option>
              </select>
            </div>
          )}

          <div className="form-group">
            <label htmlFor={`${id}-cooldown`}>Thời gian nghỉ</label>
            <select
              id={`${id}-cooldown`}
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(Number(e.target.value))}
              disabled={loading}
            >
              <option value={30}>30 giây</option>
              <option value={60}>1 phút</option>
              <option value={120}>2 phút</option>
              <option value={300}>5 phút</option>
              <option value={600}>10 phút</option>
            </select>
            <small className="form-hint">
              Khoảng thời gian nghỉ tối thiểu trước khi cho phép kích hoạt lại để tránh lặp lệnh dồn dập.
            </small>
          </div>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            disabled={loading}
          >
            Hủy bỏ
          </button>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            <Check size={16} />
            {loading ? "Đang lưu..." : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
