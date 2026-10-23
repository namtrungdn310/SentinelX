import { ArrowUpRight, CheckCircle2, TriangleAlert } from "lucide-react";
import type { Node } from "../types";
import { healthLabels, nodeHealth } from "../presentation";

interface Props {
  nodes: Node[];
  onOpenDetail: (node: Node) => void;
}
export function AttentionPanel({ nodes, onOpenDetail }: Props) {
  const priority = { crit: 0, warn: 1, unenrolled: 2, ok: 3 };
  const attention = nodes
    .filter((node) => nodeHealth(node) !== "ok")
    .sort((a, b) => priority[nodeHealth(a)] - priority[nodeHealth(b)]);
  const reason = (node: Node) => {
    if (node.status === "offline") return "Agent mất kết nối";
    if (node.status === "unenrolled") return "Chưa hoàn tất enrollment";
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
    <section className="panel attention-panel" aria-label="Máy chủ cần chú ý">
      <div className="panel-heading">
        <h2>
          <TriangleAlert size={15} /> Máy chủ cần chú ý
        </h2>
        <span className="count-badge">{attention.length}</span>
      </div>
      {!attention.length ? (
        <div className="attention-empty">
          <CheckCircle2 size={18} />
          <span>Không có host cần chú ý trong phạm vi đang chọn.</span>
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
                <small>{reason(node)}</small>
              </span>
              <span className={`status-badge ${nodeHealth(node)}`}>
                {healthLabels[nodeHealth(node)]}
              </span>
              <ArrowUpRight size={14} />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
