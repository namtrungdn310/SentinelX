import { useId, useState } from "react";
import { Check, Plus, ShieldAlert, Sliders, X } from "lucide-react";
import type { DefensePolicy } from "../types";
import { createPolicy, updatePolicy } from "../api";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  policy: DefensePolicy | null;
  projectId?: string;
  onPolicyUpdated: (updated: DefensePolicy) => void;
  onPolicyCreated?: (created: DefensePolicy) => void;
  isDemoMode: boolean;
}

const DETECTOR_EVENT_OPTIONS = [
  {
    value: "syn_flood_detector",
    label: "SYN Flood (syn_flood_detector)",
    defaultName: "Chặn tấn công SYN Flood",
    defaultAction: "BLOCK_IP_NFTABLES",
  },
  {
    value: "port_scan_detector",
    label: "Port Scan (port_scan_detector)",
    defaultName: "Chặn IP quét cổng",
    defaultAction: "BLOCK_IP_NFTABLES",
  },
  {
    value: "traffic_spike_detector",
    label: "Traffic Spike / UDP Flood (traffic_spike_detector)",
    defaultName: "Chặn tấn công băng thông",
    defaultAction: "BLOCK_IP_NFTABLES",
  },
  {
    value: "cpu_threshold_detector",
    label: "Quá tải CPU (cpu_threshold_detector)",
    defaultName: "Ứng phó quá tải CPU",
    defaultAction: "ADAPTIVE",
  },
  {
    value: "memory_exhaustion_detector",
    label: "Cạn kiệt RAM (memory_exhaustion_detector)",
    defaultName: "Tự phục hồi cạn kiệt RAM",
    defaultAction: "ADAPTIVE",
  },
  {
    value: "disk_saturation_detector",
    label: "Đầy ổ đĩa (disk_saturation_detector)",
    defaultName: "Cảnh báo đầy ổ đĩa",
    defaultAction: "ALERT_ONLY",
  },
] as const;

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
  projectId,
  onPolicyUpdated,
  onPolicyCreated,
  isDemoMode,
}: Props) {
  if (!isOpen) return null;
  if (!policy && !projectId) return null;

  return (
    <PolicyFormModal
      key={policy ? policy.id : `create-${projectId}`}
      onClose={onClose}
      policy={policy}
      projectId={projectId}
      onPolicyUpdated={onPolicyUpdated}
      onPolicyCreated={onPolicyCreated}
      isDemoMode={isDemoMode}
    />
  );
}

function PolicyFormModal({
  onClose,
  policy,
  projectId,
  onPolicyUpdated,
  onPolicyCreated,
  isDemoMode,
}: {
  onClose: () => void;
  policy: DefensePolicy | null;
  projectId?: string;
  onPolicyUpdated: (updated: DefensePolicy) => void;
  onPolicyCreated?: (created: DefensePolicy) => void;
  isDemoMode: boolean;
}) {
  const id = useId();
  const isCreate = policy === null;

  const [eventType, setEventType] = useState(
    policy?.event_type ?? DETECTOR_EVENT_OPTIONS[0].value,
  );
  const [name, setName] = useState(
    policy?.name ?? DETECTOR_EVENT_OPTIONS[0].defaultName,
  );
  const [nameTouched, setNameTouched] = useState(!isCreate);
  const [actionType, setActionType] = useState(
    policy?.action_type ?? DETECTOR_EVENT_OPTIONS[0].defaultAction,
  );
  const [serviceName, setServiceName] = useState(
    String(policy?.target_params?.service_name ?? policy?.target_params?.target ?? ""),
  );
  const [cooldownSeconds, setCooldownSeconds] = useState(
    policy?.cooldown_seconds ?? 120,
  );
  const [blockDurationMinutes, setBlockDurationMinutes] = useState(() => {
    const rawMins = policy ? Math.floor(policy.block_duration_seconds / 60) : 30;
    return rawMins >= 1 && rawMins <= 1440 ? rawMins : 30;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNetworkDetector = isNetworkEventType(eventType);
  const needsBlockDuration =
    actionType === "BLOCK_IP_NFTABLES" || (actionType === "ADAPTIVE" && isNetworkDetector);

  const handleEventTypeChange = (nextEvent: string) => {
    setEventType(nextEvent);
    const meta = DETECTOR_EVENT_OPTIONS.find((opt) => opt.value === nextEvent);
    if (meta) {
      if (!nameTouched) setName(meta.defaultName);
      setActionType(meta.defaultAction);
      if (meta.defaultAction === "BLOCK_IP_NFTABLES" && blockDurationMinutes <= 0) {
        setBlockDurationMinutes(30);
      }
    }
  };

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
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Vui lòng nhập tên chính sách.");
      return;
    }

    setLoading(true);
    setError(null);

    const boundedDurationSeconds = needsBlockDuration
      ? Math.max(60, Math.min(86400, blockDurationMinutes * 60))
      : 0;
    const nextTargetParams: Record<string, unknown> = {
      ...(policy?.target_params ?? {}),
    };
    if (actionType === "RESTART_SERVICE") {
      if (serviceName.trim()) {
        nextTargetParams.service_name = serviceName.trim();
      } else {
        delete nextTargetParams.service_name;
      }
    }

    try {
      if (isCreate) {
        const createPayload = {
          name: trimmedName,
          event_type: eventType,
          action_type: actionType,
          target_params: nextTargetParams,
          cooldown_seconds: cooldownSeconds,
          block_duration_seconds: boundedDurationSeconds,
          is_auto_execute: actionType !== "ALERT_ONLY",
          is_active: true,
        };

        if (isDemoMode) {
          const created: DefensePolicy = {
            id: `pol-${Date.now()}`,
            project_id: projectId,
            ...createPayload,
            created_at: new Date().toISOString(),
          };
          onPolicyCreated?.(created);
          onClose();
          return;
        }

        if (!projectId) {
          throw new Error("Thiếu thông tin dự án để tạo chính sách");
        }
        const saved = await createPolicy(projectId, createPayload);
        onPolicyCreated?.(saved);
        onClose();
        return;
      }

      const updatePayload = {
        name: trimmedName,
        action_type: actionType,
        target_params: nextTargetParams,
        cooldown_seconds: cooldownSeconds,
        block_duration_seconds: boundedDurationSeconds,
        is_auto_execute: actionType !== "ALERT_ONLY",
      };

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
      setError(
        err instanceof Error
          ? err.message
          : isCreate
            ? "Lỗi tạo chính sách"
            : "Lỗi cập nhật chính sách",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="policy-edit-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Sliders size={15} style={{ color: "var(--brand-indigo)" }} />{" "}
            {isCreate ? "Thêm quy tắc tự động" : "Cấu hình phản ứng tự động"}
          </span>
          <h2 id={`${id}-title`}>{isCreate ? "Tạo chính sách bảo vệ mới" : policy.name}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng biểu mẫu chính sách"
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
            <label htmlFor={`${id}-name`}>Tên chính sách</label>
            <input
              id={`${id}-name`}
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameTouched(true);
              }}
              placeholder="Ví dụ: Chặn tấn công SYN Flood"
              maxLength={100}
              disabled={loading}
              data-autofocus
            />
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-event`}>Sự kiện kích hoạt (Detector)</label>
            {isCreate ? (
              <select
                id={`${id}-event`}
                value={eventType}
                onChange={(e) => handleEventTypeChange(e.target.value)}
                disabled={loading}
              >
                {DETECTOR_EVENT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <div style={{ padding: "8px 12px", background: "var(--bg-subtle)", borderRadius: "var(--radius-xs)" }}>
                <code className="font-mono text-muted" style={{ fontSize: 13 }}>{policy.event_type}</code>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-action`}>Hành động ứng phó</label>
            <select
              id={`${id}-action`}
              value={actionType}
              onChange={(e) => handleActionTypeChange(e.target.value)}
              disabled={loading}
            >
              {isNetworkDetector ? (
                <>
                  <option value="BLOCK_IP_NFTABLES">Khóa địa chỉ IP nguồn qua tường lửa</option>
                  <option value="ADAPTIVE">Tự động thích ứng tối ưu</option>
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
            <small className="field-hint">
              {actionType === "BLOCK_IP_NFTABLES" && "Tạo luật chặn tại tường lửa nftables nhằm ngắt gói tin từ IP nguồn tấn công (có thời hạn)."}
              {actionType === "ADAPTIVE" && "Hệ thống tự chọn phương án tối ưu theo ngữ cảnh bất thường (chặn IP nếu tấn công mạng, giải phóng cache hoặc khởi động lại dịch vụ nếu quá tải tài nguyên)."}
              {actionType === "RESTART_SERVICE" && "Tự động gửi lệnh khởi động lại dịch vụ gây quá tải khi vượt ngưỡng."}
              {actionType === "CLEAR_OS_CACHE" && "Đồng bộ và giải phóng bộ nhớ đệm hệ điều hành."}
              {actionType === "ALERT_ONLY" && "Chỉ lưu nhật ký sự cố và cảnh báo cho quản trị viên, không can thiệp máy chủ."}
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
              Khoảng thời gian nghỉ tối thiểu trước khi kích hoạt lại cùng quy tắc nhằm tránh lặp lệnh dồn dập.
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
            {isCreate ? <Plus size={16} /> : <Check size={16} />}
            {loading ? "Đang lưu..." : isCreate ? "Tạo chính sách" : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
