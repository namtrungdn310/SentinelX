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
}

const MEMORY_ACTION_OPTIONS = new Set(["ADAPTIVE", "CLEAR_OS_CACHE", "RESTART_SERVICE"]);
const RESOURCE_ACTION_OPTIONS = new Set(["ALERT_ONLY", "RESTART_SERVICE"]);

function isNetworkEventType(eventType: string): boolean {
  return (
    eventType.includes("flood") ||
    eventType.includes("scan") ||
    eventType.includes("traffic")
  );
}

function isMemoryEventType(eventType: string): boolean {
  return eventType.includes("memory");
}

function resolveInitialAction(policy: DefensePolicy): string {
  if (isNetworkEventType(policy.event_type)) {
    return "BLOCK_IP_NFTABLES";
  }
  if (isMemoryEventType(policy.event_type)) {
    return MEMORY_ACTION_OPTIONS.has(policy.action_type) ? policy.action_type : "ADAPTIVE";
  }
  return RESOURCE_ACTION_OPTIONS.has(policy.action_type) ? policy.action_type : "ALERT_ONLY";
}

export function EditPolicyModal({
  isOpen,
  onClose,
  policy,
  onPolicyUpdated,
}: Props) {
  if (!isOpen || !policy) return null;

  return (
    <EditPolicyModalForm
      key={policy.id}
      onClose={onClose}
      policy={policy}
      onPolicyUpdated={onPolicyUpdated}
    />
  );
}

function EditPolicyModalForm({
  onClose,
  policy,
  onPolicyUpdated,
}: {
  onClose: () => void;
  policy: DefensePolicy;
  onPolicyUpdated: (updated: DefensePolicy) => void;
}) {
  const id = useId();
  const isMemoryPolicy = isMemoryEventType(policy.event_type);
  const isResourceOtherPolicy = !isNetworkEventType(policy.event_type) && !isMemoryPolicy;
  const hasMultipleActions = isMemoryPolicy || isResourceOtherPolicy;

  const [actionType, setActionType] = useState(() => resolveInitialAction(policy));
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

  const needsBlockDuration = actionType === "BLOCK_IP_NFTABLES";
  const blockDurationOptions = Array.from(
    new Set([5, 10, 15, 30, 60, 360, 1440, blockDurationMinutes]),
  ).sort((a, b) => a - b);
  const cooldownOptions = Array.from(
    new Set([30, 60, 120, 300, 600, cooldownSeconds]),
  ).sort((a, b) => a - b);

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
    } else {
      delete nextTargetParams.service_name;
      delete nextTargetParams.target;
    }

    const updatePayload = {
      name: policy.name,
      action_type: actionType,
      target_params: nextTargetParams,
      cooldown_seconds: cooldownSeconds,
      block_duration_seconds: boundedDurationSeconds,
      is_auto_execute: true,
    };

    try {
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

          {hasMultipleActions && (
            <div className="form-group">
              <label htmlFor={`${id}-action`}>Hành động</label>
              <select
                id={`${id}-action`}
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
                disabled={loading}
              >
                {isMemoryPolicy ? (
                  <>
                    <option value="ADAPTIVE">Tự động thích ứng</option>
                    <option value="CLEAR_OS_CACHE">Giải phóng bộ nhớ đệm hệ điều hành</option>
                    <option value="RESTART_SERVICE">Khởi động lại dịch vụ</option>
                  </>
                ) : (
                  <>
                    <option value="ALERT_ONLY">Chỉ ghi nhận cảnh báo</option>
                    <option value="RESTART_SERVICE">Khởi động lại dịch vụ</option>
                  </>
                )}
              </select>
              <small className="field-hint">
                {actionType === "ADAPTIVE" &&
                  "Hệ thống tự kiểm tra: nếu có dịch vụ ứng dụng chiếm >= 40% lượng RAM đang sử dụng sẽ tự động khởi động lại dịch vụ đó; ngược lại (tải phân tán, dịch vụ lõi hoặc bộ nhớ đệm) sẽ giải phóng bộ nhớ đệm an toàn."}
                {actionType === "CLEAR_OS_CACHE" &&
                  "Chạy sync và giải phóng bộ nhớ đệm hệ điều hành (Page Cache, dentries, inodes) mà không làm gián đoạn dịch vụ."}
                {actionType === "ALERT_ONLY" &&
                  "Chỉ ghi nhận cảnh báo và mở sự cố trên Dashboard mà không tự động can thiệp máy chủ."}
                {actionType === "RESTART_SERVICE" &&
                  "Khởi động lại dịch vụ chiếm >= 40% tài nguyên quá tải qua systemd (hoặc dịch vụ dự phòng bên dưới); từ chối tự restart dịch vụ lõi hệ thống."}
              </small>
            </div>
          )}

          {actionType === "RESTART_SERVICE" && (
            <div className="form-group">
              <label htmlFor={`${id}-service`}>Tên dịch vụ dự phòng (tùy chọn)</label>
              <input
                id={`${id}-service`}
                type="text"
                className="font-mono"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="Để trống để tự xác định dịch vụ tương ứng (vd: nginx)"
                disabled={loading}
              />
              {!isMemoryPolicy && (
                <small className="field-hint">
                  Ưu tiên dịch vụ chiếm &gt;= 40% tải CPU đang quá tải; nếu tải phân tán hoặc là dịch vụ lõi sẽ tự động từ chối restart.
                </small>
              )}
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
                {blockDurationOptions.map((mins) => (
                  <option key={mins} value={mins}>
                    {mins >= 60 && mins % 60 === 0
                      ? mins === 1440
                        ? "24 giờ (tối đa)"
                        : `${mins / 60} giờ`
                      : `${mins} phút`}
                  </option>
                ))}
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
              {cooldownOptions.map((sec) => (
                <option key={sec} value={sec}>
                  {sec >= 60 && sec % 60 === 0
                    ? `${sec / 60} phút`
                    : `${sec} giây`}
                </option>
              ))}
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
