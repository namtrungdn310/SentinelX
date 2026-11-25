import { useId, useState } from "react";
import { Activity, KeyRound, Server, X } from "lucide-react";
import type { Node } from "../types";
import { createEnrollmentToken } from "../api";
import { getDefaultAgentControllerUrl } from "../agentInstall";
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
import { AgentInstallSection } from "./AgentInstallSection";
import { Modal } from "./Modal";
import { useAgentBundleInfo } from "./useAgentBundleInfo";

interface Props {
  node: Node | null;
  isOpen: boolean;
  onClose: () => void;
  onInspectMetrics?: (node: Node) => void;
}
export function NodeDetailModal({
  node,
  isOpen,
  onClose,
  onInspectMetrics,
}: Props) {
  const id = useId();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [controllerUrl, setControllerUrl] = useState(getDefaultAgentControllerUrl);
  const { bundleInfo, bundleLoading } = useAgentBundleInfo(Boolean(isOpen && node));

  if (!isOpen || !node) return null;
  const close = () => {
    if (!loading) onClose();
  };
  const generate = async () => {
    try {
      setLoading(true);
      setError(null);
      setToken(await createEnrollmentToken(node.id, 24));
    } catch {
      setError("Không cấp được token. Kiểm tra kết nối Controller và thử lại.");
    } finally {
      setLoading(false);
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
            {validMetric(node.latestCpu) && getNodeHardware(node).cpuCores !== undefined && (
              <small>{formatCpuUsage(node.latestCpu, getNodeHardware(node).cpuCores)}</small>
            )}
          </div>
          <div>
            <span>Bộ nhớ RAM</span>
            <strong className="font-mono">{formatPercent(node.latestMemory)}</strong>
            {validMetric(node.latestMemory) && getNodeHardware(node).totalMemoryBytes !== undefined && (
              <small>{formatMemoryUsage(node.latestMemory, getNodeHardware(node).totalMemoryBytes)}</small>
            )}
          </div>
          <div>
            <span>Dung lượng ổ đĩa</span>
            <strong className="font-mono">{formatPercent(node.latestDisk)}</strong>
            {validMetric(node.latestDisk) ? (
              getNodeHardware(node).totalDiskBytes !== undefined && (
                <small>{formatDiskUsage(node.latestDisk, getNodeHardware(node).totalDiskBytes)}</small>
              )
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
              disabled={loading}
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
            <AgentInstallSection
              nodeId={node.id}
              token={token}
              controllerUrl={controllerUrl}
              onControllerUrlChange={setControllerUrl}
              bundleInfo={bundleInfo}
              bundleLoading={bundleLoading}
            />
          )}
        </div>
      </div>
      <div className="modal-actions">
        {onInspectMetrics && (
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => onInspectMetrics(node)}
            disabled={loading}
          >
            <Activity size={15} />
            Xem mẫu dữ liệu
          </button>
        )}
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
