import { ChevronRight, CheckCircle2, ListChecks } from "lucide-react";
import type { Node } from "../types";
import { nodeHealthLabel, nodeHealth } from "../presentation";

interface Props {
  nodes: Node[];
  onOpenDetail: (node: Node) => void;
}
export function AttentionPanel({ nodes, onOpenDetail }: Props) {
  const priority = { crit: 0, warn: 1, unenrolled: 2, unknown: 3, ok: 4 };
  const attention = nodes
    .filter((node) => ["crit", "warn", "unenrolled"].includes(nodeHealth(node)))
    .sort((a, b) => priority[nodeHealth(a)] - priority[nodeHealth(b)] || a.hostname.localeCompare(b.hostname));
  const reason = (node: Node) => {
    if (node.status === "offline") return "Agent mất kết nối";
    if (node.status === "unenrolled") return "Chưa hoàn tất đăng ký Agent";
    const metrics = [
      (node.latestCpu ?? 0) > 75
        ? `CPU ${node.latestCpu!.toFixed(1)}% > 75%`
        : "",
      (node.latestMemory ?? 0) > 85
        ? `RAM ${node.latestMemory!.toFixed(1)}% > 85%`
        : "",
    ].filter(Boolean);
    return metrics.join(" · ") || "Agent báo trạng thái degraded";
  };
  return (
    <section className="panel attention-panel" aria-label="Máy chủ cần xử lý">
      <div className="panel-heading">
        <h2>
          <ListChecks size={16} /> Máy chủ cần xử lý
        </h2>
        <span className="count-badge">{attention.length}</span>
      </div>
      {!attention.length ? (
        <div className="attention-empty">
          <CheckCircle2 size={18} />
          <span>{nodes.length ? "Không có máy chủ cần xử lý trong phạm vi đang chọn." : "Không có máy chủ phù hợp với phạm vi hiện tại."}</span>
        </div>
      ) : (
        <div className="attention-list">
          {attention.map((node) => (
            <button
              className="attention-item"
              key={node.id}
              onClick={() => onOpenDetail(node)}
            >
              <span className={`health-dot ${nodeHealth(node)}`} />
              <span className="attention-content">
                <strong>{node.hostname}</strong>
                <small>{node.ip_address}</small>
              </span>
              <span className="attention-reason">
                <span className={`status-badge ${nodeHealth(node)}`}>
                {nodeHealthLabel(node)}
                </span>
                <span>{reason(node)}</span>
              </span>
              <span className="attention-action">Kiểm tra <ChevronRight size={14} /></span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
