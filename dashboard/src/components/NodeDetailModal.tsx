import { useId, useState } from "react";
import { Check, Copy, KeyRound, Server, X } from "lucide-react";
import type { Node } from "../types";
import { createEnrollmentToken } from "../api";
import {
  formatCpuUsage,
  formatDiskUsage,
  formatMemoryUsage,
  getNodeHardware,
  healthLabels,
  nodeHealth,
  formatPercent,
  validMetric,
} from "../presentation";
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
            <Server size={15} /> Chi tiết máy chủ
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
      <div className="modal-body">
        <div className="host-detail-summary">
          <span className={`status-badge ${nodeHealth(node)}`}>
            <i />
            {healthLabels[nodeHealth(node)]}
          </span>
        </div>
        <dl className="detail-properties">
          <div>
            <dt>Mã máy chủ</dt>
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
        </dl>
        <div className="detail-resource-grid">
          <div>
            <span>CPU</span>
            <strong className="font-mono">{formatPercent(node.latestCpu)}</strong>
            {validMetric(node.latestCpu) && (
              <small>{formatCpuUsage(node.latestCpu, getNodeHardware(node).cpuCores)}</small>
            )}
          </div>
          <div>
            <span>Bộ nhớ RAM</span>
            <strong className="font-mono">{formatPercent(node.latestMemory)}</strong>
            {validMetric(node.latestMemory) && (
              <small>{formatMemoryUsage(node.latestMemory, getNodeHardware(node).totalMemoryBytes)}</small>
            )}
          </div>
          <div>
            <span>Dung lượng ổ đĩa</span>
            <strong className="font-mono">{formatPercent(node.latestDisk)}</strong>
            {validMetric(node.latestDisk) ? (
              <small>{formatDiskUsage(node.latestDisk, getNodeHardware(node).totalDiskBytes)}</small>
            ) : (
              <small>Không có dữ liệu ổ đĩa</small>
            )}
          </div>
        </div>
        <div className="token-section">
          <div className="token-section-header">
            <h3>
              <KeyRound size={16} /> Token đăng ký Agent
            </h3>
            <button
              type="button"
              className="btn btn-primary"
              onClick={generate}
              disabled={loading || isDemoMode}
              title={isDemoMode ? "Cần kết nối Controller để tạo token" : undefined}
            >
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
                type="button"
                className="btn btn-outline"
                aria-label="Sao chép token đăng ký"
                onClick={copy}
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Đã sao chép" : "Sao chép token"}
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="modal-actions">
        <button
          type="button"
          className="btn btn-outline"
          onClick={close}
          disabled={loading}
        >
          Đóng chi tiết
        </button>
      </div>
    </Modal>
  );
}
