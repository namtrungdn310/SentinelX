import { useId, useState } from "react";
import { Check, Cpu, MemoryStick, Plus, Server, X } from "lucide-react";
import type { Node } from "../types";
import { formatPercent, healthLabels, nodeHealth, validMetric } from "../presentation";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  projectName: string;
  eligibleNodes: Node[];
  unavailableCount: number;
  busy?: boolean;
  onClose: () => void;
  onConfirmAdd: (items: Array<{ nodeId: string; port: number }>) => Promise<void>;
}

export function LBPoolPickerModal({
  isOpen,
  projectName,
  eligibleNodes,
  unavailableCount,
  busy = false,
  onClose,
  onConfirmAdd,
}: Props) {
  const id = useId();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [portByNodeId, setPortByNodeId] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const toggleSelect = (nodeId: string) => {
    setSelectedIds((prev) =>
      prev.includes(nodeId)
        ? prev.filter((item) => item !== nodeId)
        : [...prev, nodeId],
    );
  };

  const handleConfirm = async () => {
    if (!selectedIds.length || busy) return;
    setError(null);
    try {
      await onConfirmAdd(
        selectedIds.map((nodeId) => {
          const fallback =
            eligibleNodes.find((n) => n.id === nodeId)?.lb_backend_port ?? 8080;
          const rawPort = portByNodeId[nodeId] ?? fallback;
          return {
            nodeId,
            port: Math.min(65535, Math.max(1, Number(rawPort) || 8080)),
          };
        }),
      );
      setSelectedIds([]);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không thể thêm máy chủ vào Pool.",
      );
    }
  };

  return (
    <Modal
      onClose={() => {
        if (!busy) onClose();
      }}
      labelledBy={`${id}-title`}
      className="lb-picker-modal"
    >
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Server size={15} /> Chọn Backend Server · {projectName}
          </span>
          <h2 id={`${id}-title`}>Chọn máy chủ vào Load Balancer Pool</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Đóng chọn máy chủ"
          onClick={onClose}
          disabled={busy}
        >
          <X size={16} />
        </button>
      </div>

      <div className="modal-body">
        {error && (
          <div className="feedback-banner feedback-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        {eligibleNodes.length === 0 ? (
          <div className="lb-picker-modal-empty">
            <Server size={28} />
            <strong>Mọi máy chủ của dự án đã nằm trong LB Pool</strong>
            {unavailableCount > 0 && (
              <p>
                Hiện có {unavailableCount} máy chủ chưa kết nối hoặc đang mất kết nối.
              </p>
            )}
          </div>
        ) : (
          <div className="lb-metric-select-grid" role="group" aria-label="Danh sách máy chủ khả dụng">
            {eligibleNodes.map((node) => {
              const checked = selectedIds.includes(node.id);
              const health = nodeHealth(node);
              const port = portByNodeId[node.id] ?? node.lb_backend_port ?? 8080;
              const cpuVal = validMetric(node.latestCpu) ? node.latestCpu : null;
              const memVal = validMetric(node.latestMemory) ? node.latestMemory : null;

              return (
                <div
                  key={node.id}
                  className={`lb-node-metric-card ${checked ? "is-selected" : ""}`}
                >
                  <button
                    type="button"
                    className="lb-node-card-select-area"
                    aria-pressed={checked}
                    disabled={busy}
                    onClick={() => toggleSelect(node.id)}
                  >
                    <div className="lb-nmc-head">
                      <div className="lb-nmc-identity">
                        <strong>{node.hostname}</strong>
                        <span className="font-mono">{node.ip_address}</span>
                      </div>
                      <span
                        className={`lb-nmc-check ${checked ? "checked" : ""}`}
                        aria-hidden="true"
                      >
                        {checked && <Check size={13} />}
                      </span>
                    </div>

                    <div className="lb-nmc-metrics">
                      <div className="lb-nmc-metric">
                        <div className="lb-nmc-metric-label">
                          <Cpu size={12} />
                          <span>CPU</span>
                          <b className="font-mono">{formatPercent(cpuVal)}</b>
                        </div>
                        <div className="lb-nmc-bar">
                          <i
                            style={{ width: `${Math.min(100, cpuVal ?? 0)}%` }}
                            className={cpuVal !== null && cpuVal > 75 ? "warn" : "cpu"}
                          />
                        </div>
                      </div>
                      <div className="lb-nmc-metric">
                        <div className="lb-nmc-metric-label">
                          <MemoryStick size={12} />
                          <span>RAM</span>
                          <b className="font-mono">{formatPercent(memVal)}</b>
                        </div>
                        <div className="lb-nmc-bar">
                          <i
                            style={{ width: `${Math.min(100, memVal ?? 0)}%` }}
                            className={memVal !== null && memVal > 85 ? "warn" : "memory"}
                          />
                        </div>
                      </div>
                    </div>
                  </button>

                  <div className="lb-nmc-footer">
                    <span className={`status-badge ${health}`}>
                      <i />
                      {healthLabels[health]}
                    </span>
                    <label className="lb-nmc-port" htmlFor={`${id}-port-${node.id}`}>
                      <span>Cổng</span>
                      <input
                        id={`${id}-port-${node.id}`}
                        type="number"
                        className="form-input font-mono"
                        min={1}
                        max={65535}
                        value={port}
                        disabled={busy}
                        onChange={(e) => {
                          const val = Math.max(
                            1,
                            Math.min(65535, Number(e.target.value) || 8080),
                          );
                          setPortByNodeId((prev) => ({ ...prev, [node.id]: val }));
                        }}
                      />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="modal-actions modal-actions-spread">
        <span className="lb-picker-summary">
          {selectedIds.length > 0
            ? `Đã chọn ${selectedIds.length} máy chủ`
            : unavailableCount > 0
              ? `Ẩn ${unavailableCount} máy chưa kết nối / offline`
              : null}
        </span>
        <div className="lb-picker-modal-btns">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            disabled={busy}
          >
            Hủy
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || selectedIds.length === 0}
            onClick={() => void handleConfirm()}
          >
            <Plus size={14} />
            {busy
              ? "Đang thêm…"
              : selectedIds.length > 0
                ? `Đưa ${selectedIds.length} máy vào Pool`
                : "Đưa vào Pool"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
