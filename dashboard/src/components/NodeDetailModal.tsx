import { useId, useState } from "react";
import { Check, Copy, KeyRound, Server, X } from "lucide-react";
import type { Node } from "../types";
import { createEnrollmentToken } from "../api";
import { healthLabels, nodeHealth, nodeRole } from "../presentation";
import { Modal } from "./Modal";

interface Props {
  node: Node | null;
  isOpen: boolean;
  onClose: () => void;
  isDemoMode: boolean;
}
export function NodeDetailModal({ node, isOpen, onClose, isDemoMode }: Props) {
  const id = useId();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!isOpen || !node) return null;
  const close = () => {
    if (!loading) onClose();
  };
  const generate = async () => {
    try {
      setLoading(true);
      setError(null);
      setCopied(false);
      setToken(await createEnrollmentToken(node.id, 24));
    } catch {
      setError("Không cấp được token. Kiểm tra kết nối Controller và thử lại.");
    } finally {
      setLoading(false);
    }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(token!);
      setCopied(true);
    } catch {
      setError(
        "Không truy cập được clipboard. Chọn token và sao chép thủ công.",
      );
    }
  };
  return (
    <Modal onClose={close} labelledBy={`${id}-title`}>
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Server size={15} /> HOST DETAILS
          </span>
          <h2 id={`${id}-title`}>{node.hostname}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng chi tiết máy chủ"
          onClick={close}
          disabled={loading}
        >
          <X size={19} />
        </button>
      </div>
      <div className="host-detail-summary">
        <span className={`status-badge ${nodeHealth(node)}`}>
          <i />
          {healthLabels[nodeHealth(node)]}
        </span>
        <span>{nodeRole(node.hostname)}</span>
      </div>
      <dl className="detail-properties">
        <div>
          <dt>Node ID</dt>
          <dd className="font-mono">{node.id}</dd>
        </div>
        <div>
          <dt>Địa chỉ IP</dt>
          <dd className="font-mono">{node.ip_address}</dd>
        </div>
        <div>
          <dt>Phản hồi gần nhất</dt>
          <dd>
            {node.last_seen
              ? new Date(node.last_seen).toLocaleString("vi-VN")
              : "Chưa có phản hồi"}
          </dd>
        </div>
        <div>
          <dt>CPU / RAM</dt>
          <dd className="font-mono">
            {node.latestCpu?.toFixed(1) ?? "—"}% /{" "}
            {node.latestMemory?.toFixed(1) ?? "—"}%
          </dd>
        </div>
        <div>
          <dt>Ổ đĩa</dt>
          <dd className="font-mono">{node.latestDisk?.toFixed(1) ?? "—"}%</dd>
        </div>
      </dl>
      <div className="token-section">
        <h3>
          <KeyRound size={16} /> Enrollment token
        </h3>
        <p className="text-body">
          {isDemoMode
            ? "Máy chủ mẫu không cấp token thật. Kết nối Controller để đăng ký Agent."
            : "Cấp token mới để kích hoạt Agent trên máy Linux. Token có hiệu lực 24 giờ."}
        </p>
        <button
          className="btn btn-outline"
          onClick={generate}
          disabled={loading || isDemoMode}
        >
          <KeyRound size={14} />
          {loading ? "Đang cấp token…" : token ? "Cấp lại token" : "Tạo token"}
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {token && (
        <div className="token-result">
          <div className="code-box">{token}</div>
          <button
            className="btn btn-outline"
            aria-label="Sao chép enrollment token"
            onClick={copy}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Đã sao chép" : "Sao chép token"}
          </button>
        </div>
      )}
      <div className="modal-actions">
        <button className="btn btn-primary" onClick={close} disabled={loading}>
          Đóng chi tiết
        </button>
      </div>
    </Modal>
  );
}
