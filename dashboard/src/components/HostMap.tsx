import { ArrowUpRight, Server } from "lucide-react";
import type { Node } from "../types";
import { healthLabels, nodeHealth } from "../presentation";

interface Props {
  nodes: Node[];
  selectedNode: Node | null;
  onSelectNode: (node: Node) => void;
  onViewHosts: () => void;
}
export function HostMap({
  nodes,
  selectedNode,
  onSelectNode,
  onViewHosts,
}: Props) {
  const counts = { ok: 0, warn: 0, crit: 0, unenrolled: 0 };
  nodes.forEach((node) => counts[nodeHealth(node)]++);
  return (
    <section
      className="panel host-map-panel"
      aria-label="Trạng thái cụm máy chủ"
    >
      <div className="panel-heading">
        <h2>
          <Server size={15} /> Trạng thái cụm
        </h2>
        <span className="count-badge">{nodes.length} hosts</span>
      </div>
      <div
        className="health-distribution"
        role="img"
        aria-label={Object.entries(counts)
          .map(
            ([health, count]) =>
              `${healthLabels[health as keyof typeof counts]}: ${count}`,
          )
          .join(", ")}
      >
        {Object.entries(counts)
          .filter(([, count]) => count > 0)
          .map(([health, count]) => (
            <span key={health} className={health} style={{ flex: count }} />
          ))}
      </div>
      <div className="map-legend">
        {Object.entries(counts).map(([health, count]) => (
          <span key={health}>
            <i className={`health-dot ${health}`} />
            {healthLabels[health as keyof typeof counts]}
            <b>{count}</b>
          </span>
        ))}
      </div>
      <div className="host-map-grid">
        {nodes.map((node) => (
          <button
            key={node.id}
            className={`map-host ${nodeHealth(node)} ${selectedNode?.id === node.id ? "selected" : ""}`}
            aria-label={`${node.hostname}: ${healthLabels[nodeHealth(node)]}`}
            aria-pressed={selectedNode?.id === node.id}
            onClick={() => onSelectNode(node)}
          >
            <span className="map-host-name">
              <i className={`health-dot ${nodeHealth(node)}`} />
              {node.hostname}
            </span>
            <span className="map-host-values">
              <span>
                CPU <b>{node.latestCpu?.toFixed(1) ?? "—"}%</b>
              </span>
              <span>
                RAM <b>{node.latestMemory?.toFixed(1) ?? "—"}%</b>
              </span>
            </span>
          </button>
        ))}
        {!nodes.length && (
          <div className="panel-empty">Không có máy chủ phù hợp.</div>
        )}
      </div>
      <button className="map-footer" onClick={onViewHosts}>
        Xem danh sách máy chủ <ArrowUpRight size={14} />
      </button>
    </section>
  );
}
