import { useEffect, useId, useMemo, useState } from "react";
import { CheckCircle2, Flame, ShieldAlert, X } from "lucide-react";
import type { DefenseAction, IPWhitelist, Node } from "../types";
import { createManualDefenseAction, fetchWhitelist } from "../api";
import { MOCK_WHITELIST } from "../mockData";
import { validateManualBlockIp } from "../presentation";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  nodes: Node[];
  existingActions?: DefenseAction[];
  onActionCreated: (action: DefenseAction) => void;
  isDemoMode: boolean;
}

export function ManualBlockModal({
  isOpen,
  onClose,
  nodes,
  existingActions = [],
  onActionCreated,
  isDemoMode,
}: Props) {
  const id = useId();
  const [nodeId, setNodeId] = useState(nodes[0]?.id || "");
  const [targetIp, setTargetIp] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveWhitelist, setLiveWhitelist] = useState<IPWhitelist[]>([]);

  const effectiveNodeId = nodes.some((n) => n.id === nodeId) ? nodeId : nodes[0]?.id || "";
  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === effectiveNodeId),
    [nodes, effectiveNodeId],
  );
  const projectId = selectedNode?.project_id ?? nodes[0]?.project_id ?? null;

  useEffect(() => {
    if (!isOpen || isDemoMode || !projectId) return;
    let cancelled = false;
    void fetchWhitelist(projectId)
      .then((items) => {
        if (!cancelled) setLiveWhitelist(items);
      })
      .catch(() => {
        if (!cancelled) setLiveWhitelist([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, isDemoMode, projectId]);

  const effectiveWhitelist = useMemo(() => {
    if (isDemoMode) {
      return projectId
        ? MOCK_WHITELIST.filter((w) => w.project_id === projectId)
        : MOCK_WHITELIST;
    }
    return liveWhitelist;
  }, [isDemoMode, projectId, liveWhitelist]);

  const ipCheck = useMemo(
    () => validateManualBlockIp(targetIp, selectedNode, effectiveWhitelist, existingActions),
    [targetIp, selectedNode, effectiveWhitelist, existingActions],
  );

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectiveNodeId) {
      setError("Vui lòng chọn máy chủ áp dụng");
      return;
    }
    if (!ipCheck.valid) {
      setError(ipCheck.message);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const durationSeconds = Math.max(60, Math.min(86400, durationMinutes * 60));
      if (isDemoMode) {
        const nowIso = new Date().toISOString();
        const mockAction: DefenseAction = {
          id: `def-man-${Date.now()}`,
          incident_id: null,
          policy_id: null,
          node_id: effectiveNodeId,
          action_type: "BLOCK_IP_NFTABLES",
          target_ip: targetIp.trim(),
          command_payload: { duration_seconds: durationSeconds, manual: true },
          status: "APPLIED",
          agent_ack_at: nowIso,
          error_message: null,
          created_at: nowIso,
          applied_at: nowIso,
          effective_until: new Date(Date.now() + durationSeconds * 1000).toISOString(),
        };
        onActionCreated(mockAction);
        onClose();
        return;
      }

      const res = await createManualDefenseAction({
        node_id: effectiveNodeId,
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
              onChange={(e) => {
                setTargetIp(e.target.value);
                if (error) setError(null);
              }}
              aria-invalid={ipCheck.status === "invalid"}
              disabled={loading}
              data-autofocus
            />
            {ipCheck.status === "empty" ? (
              <small className="field-hint">{ipCheck.message}</small>
            ) : (
              <div
                className={`ip-check-feedback ${
                  ipCheck.valid ? "is-valid" : "is-invalid"
                }`}
                role={ipCheck.valid ? "status" : "alert"}
              >
                {ipCheck.valid ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
                <span>{ipCheck.message}</span>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-node`}>Máy chủ áp dụng</label>
            <select
              id={`${id}-node`}
              value={effectiveNodeId}
              onChange={(e) => setNodeId(e.target.value)}
              disabled={loading || nodes.length === 0}
            >
              {nodes.length === 0 && <option value="">Không có máy chủ trong dự án</option>}
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} · {n.ip_address}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-duration`}>Thời gian chặn IP</label>
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
              <option value={360}>6 giờ</option>
              <option value={1440}>24 giờ (tối đa)</option>
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
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !effectiveNodeId || !ipCheck.valid}
          >
            <Flame size={16} />
            {loading ? "Đang gửi lệnh..." : "Kích hoạt lệnh chặn ngay"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

