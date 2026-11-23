import { useId, useState } from "react";
import { Check, ShieldAlert, Sliders, X } from "lucide-react";
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

function isNetworkEventType(eventType: string): boolean {
  return (
    eventType.includes("flood") ||
    eventType.includes("scan") ||
    eventType.includes("traffic")
  );
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
  const [serviceName, setServiceName] = useState(
    String(policy.target_params?.service_name ?? policy.target_params?.target ?? ""),
  );
  const [cooldownSeconds, setCooldownSeconds] = useState(policy.cooldown_seconds);
  const [blockDurationMinutes, setBlockDurationMinutes] = useState(() => {
    const rawMins = Math.floor(policy.block_duration_seconds / 60);
    return rawMins >= 1 && rawMins <= 1440 ? rawMins : 30;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNetworkDetector = isNetworkEventType(policy.event_type);
  const needsBlockDuration =
    actionType === "BLOCK_IP_NFTABLES" || (actionType === "ADAPTIVE" && isNetworkDetector);

  const handleActionTypeChange = (nextAction: string) => {
    setActionType(nextAction);
    if (
      (nextAction === "BLOCK_IP_NFTABLES" || (nextAction === "ADAPTIVE" && isNetworkDetector)) &&
      blockDurationMinutes <= 0
    ) {
      setBlockDurationMinutes(30);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const boundedDurationSeconds = needsBlockDuration
      ? Math.max(60, Math.min(86400, blockDurationMinutes * 60))
      : 0;
    const nextTargetParams: Record<string, unknown> = {
      ...(policy.target_params ?? {}),
    };
    if (actionType === "RESTART_SERVICE") {
      if (serviceName.trim()) {
        nextTargetParams.service_name = serviceName.trim();
      } else {
        delete nextTargetParams.service_name;
      }
    }

    const updatePayload = {
      name: policy.name,
      action_type: actionType,
      target_params: nextTargetParams,
      cooldown_seconds: cooldownSeconds,
      block_duration_seconds: boundedDurationSeconds,
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
              onChange={(e) => handleActionTypeChange(e.target.value)}
              disabled={loading}
            >
              {isNetworkDetector ? (
                <>
                  <option value="BLOCK_IP_NFTABLES">Khóa địa chỉ IP nguồn qua tường lửa</option>
                  <option value="ADAPTIVE">Tự động thích ứng</option>
                  <option value="ALERT_ONLY">Chỉ ghi nhận cảnh báo</option>
                </>
              ) : (
                <>
                  <option value="ADAPTIVE">Tự động thích ứng</option>
                  <option value="RESTART_SERVICE">Khởi động lại dịch vụ hoặc tiến trình</option>
                  <option value="CLEAR_OS_CACHE">Giải phóng bộ nhớ đệm hệ điều hành</option>
                  <option value="ALERT_ONLY">Chỉ ghi nhận cảnh báo</option>
                </>
              )}
            </select>
            <small className="field-hint">
              {actionType === "BLOCK_IP_NFTABLES" && "Tạo luật chặn tại tường lửa nftables nhằm ngắt gói tin từ IP nguồn tấn công (có thời hạn)."}
              {actionType === "ADAPTIVE" && "Hệ thống tự chọn phương án tối ưu theo ngữ cảnh bất thường (chặn IP nếu tấn công mạng, giải phóng đệm hoặc khởi động lại tiến trình nếu quá tải tài nguyên)."}
              {actionType === "RESTART_SERVICE" && "Tự động gửi lệnh khởi động lại dịch vụ gây quá tải khi vượt ngưỡng."}
              {actionType === "CLEAR_OS_CACHE" && "Đồng bộ và giải phóng bộ nhớ đệm của nhân hệ điều hành."}
              {actionType === "ALERT_ONLY" && "Chỉ lưu nhật ký sự cố và thông báo cho quản trị viên, không can thiệp máy chủ."}
            </small>
          </div>

          {actionType === "RESTART_SERVICE" && (
            <div className="form-group">
              <label htmlFor={`${id}-service`}>Tên dịch vụ dự phòng (tùy chọn)</label>
              <input
                id={`${id}-service`}
                type="text"
                className="font-mono"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="Để trống để tự nhận diện theo tiến trình quá tải (vd: nginx)"
                disabled={loading}
              />
            </div>
          )}

          {needsBlockDuration && (
            <div className="form-group">
              <label htmlFor={`${id}-duration`}>Thời gian chặn IP</label>
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
                <option value={360}>6 giờ</option>
                <option value={1440}>24 giờ (tối đa)</option>
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
            <small className="field-hint">
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
