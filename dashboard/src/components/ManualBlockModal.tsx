import { useId, useState } from "react";
import { Flame, ShieldAlert, X } from "lucide-react";
import type { Node, DefenseAction } from "../types";
import { createManualDefenseAction } from "../api";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  nodes: Node[];
  onActionCreated: (action: DefenseAction) => void;
  isDemoMode: boolean;
}

export function ManualBlockModal({
  isOpen,
  onClose,
  nodes,
  onActionCreated,
  isDemoMode,
}: Props) {
  const id = useId();
  const [nodeId, setNodeId] = useState(nodes[0]?.id || "");
  const [targetIp, setTargetIp] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetIp.trim()) {
      setError("Vui lòng nhập địa chỉ IP cần chặn");
      return;
    }
    if (!nodeId) {
      setError("Vui lòng chọn máy chủ áp dụng");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const durationSeconds = durationMinutes * 60;
      if (isDemoMode) {
        const mockAction: DefenseAction = {
          id: `def-man-${Date.now()}`,
          incident_id: null,
          policy_id: null,
          node_id: nodeId,
          action_type: "BLOCK_IP_NFTABLES",
          target_ip: targetIp.trim(),
          command_payload: { duration_seconds: durationSeconds, manual: true },
          status: "APPLIED",
          agent_ack_at: new Date().toISOString(),
          error_message: null,
          created_at: new Date().toISOString(),
        };
        onActionCreated(mockAction);
        onClose();
        return;
      }

      const res = await createManualDefenseAction({
        node_id: nodeId,
        action_type: "BLOCK_IP_NFTABLES",
        target_ip: targetIp.trim(),
        command_payload: {
          duration_seconds: durationSeconds,
          target: targetIp.trim(),
        },
      });
      onActionCreated(res);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi gửi lệnh chặn IP");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="manual-block-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Flame size={15} style={{ color: "var(--status-crit)" }} /> Tường lửa nftables
          </span>
          <h2 id={`${id}-title`}>Thực thi chặn IP thủ công</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng biểu mẫu chặn IP"
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
            <label htmlFor={`${id}-ip`}>IP cần chặn (IPv4 hoặc IPv6)</label>
            <input
              id={`${id}-ip`}
              type="text"
              className="font-mono"
              placeholder="ví dụ: 203.0.113.195 hoặc 2001:db8::1"
              value={targetIp}
              onChange={(e) => setTargetIp(e.target.value)}
              disabled={loading}
              data-autofocus
            />
            <small className="form-hint">
              Hệ thống sẽ từ chối nếu IP là loopback (127.0.0.1), IP máy chủ hoặc nằm trong danh sách an toàn.
            </small>
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-node`}>Máy chủ áp dụng</label>
            <select
              id={`${id}-node`}
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              disabled={loading}
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} · {n.ip_address}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-duration`}>Thời gian khóa tường lửa</label>
            <select
              id={`${id}-duration`}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              disabled={loading}
            >
              <option value={5}>5 phút</option>
              <option value={15}>15 phút</option>
              <option value={30}>30 phút</option>
              <option value={60}>1 giờ</option>
              <option value={1440}>24 giờ</option>
              <option value={0}>Vĩnh viễn đến khi gỡ thủ công</option>
            </select>
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
            <Flame size={16} />
            {loading ? "Đang gửi lệnh..." : "Kích hoạt lệnh chặn ngay"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

