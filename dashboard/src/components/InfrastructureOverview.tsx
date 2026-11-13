import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Node, Project } from "../types";
import { healthLabels, nodeHealth, validMetric } from "../presentation";
import type { Health } from "../presentation";
import { AttentionPanel } from "./AttentionPanel";

interface Props {
  nodes: Node[];
  projects?: Project[];
  selectedProjectId?: string | null;
  onStatusSelect: (status: Health) => void;
  onProjectSelect?: (projectId: string) => void;
  onInspectNode: (node: Node) => void;
  onOpenDetail: (node: Node) => void;
  onViewHosts: () => void;
}

export function InfrastructureOverview({
  nodes,
  onStatusSelect,
  onInspectNode,
  onOpenDetail,
  onViewHosts,
}: Props) {
  const [resource, setResource] = useState<"latestCpu" | "latestMemory">(
    "latestCpu",
  );
  const counts: Record<Health, number> = {
    ok: 0,
    warn: 0,
    crit: 0,
    unenrolled: 0,
    unknown: 0,
  };
  nodes.forEach((node) => counts[nodeHealth(node)]++);
  const ranked = nodes
    .filter(
      (node) =>
        (node.status === "online" || node.status === "degraded") &&
        validMetric(node[resource]),
    )
    .sort((a, b) => b[resource]! - a[resource]!)
    .slice(0, 5);
  return (
    <div className="infrastructure-overview" aria-label="Tổng quan toàn cụm">
      <div className="overview-grid">
        <section
          className="panel fleet-health-panel"
          aria-label="Máy chủ ổn định"
        >
          <div className="panel-heading">
            <h2>
              Máy chủ ổn định
            </h2>
            <button className="text-button" onClick={onViewHosts}>Xem máy chủ <ChevronRight size={14} /></button>
          </div>
          <div className="fleet-health-body">
          <div className="fleet-health-summary">
            <strong>
              {counts.ok}
              <span className="fleet-total-slash">/ {nodes.length}</span>
            </strong>
            <span>máy chủ ổn định</span>
          </div>
          <div className="fleet-health-distribution">
          <div
            className="health-distribution"
            role="img"
            aria-label={Object.entries(counts)
              .map(
                ([health, count]) =>
                  `${healthLabels[health as Health]}: ${count}`,
              )
              .join(", ")}
          >
            {Object.entries(counts)
              .filter(([, count]) => count > 0)
              .map(([health, count]) => (
                <span className={health} key={health} style={{ flex: count }} />
              ))}
          </div>
          <div className="fleet-health-breakdown">
            {Object.entries(counts).map(([health, count]) => (
              <button
                key={health}
                onClick={() => onStatusSelect(health as Health)}
                aria-label={`Xem ${count} máy chủ ${healthLabels[health as Health].toLowerCase()}`}
              >
                <i className={`health-dot ${health}`} />
                <span>{healthLabels[health as Health]}</span>
                <b>{count}</b>
                <ChevronRight size={13} />
              </button>
            ))}
          </div>
          </div>
          </div>
        </section>
        <AttentionPanel nodes={nodes} onOpenDetail={onOpenDetail} />
        <section
          className="panel resource-ranking-panel"
          aria-label="Máy chủ sử dụng tài nguyên nhiều nhất"
        >
          <div className="panel-heading">
            <h2>
              Máy chủ sử dụng tài nguyên nhiều nhất
            </h2>
            <div className="segmented">
              <button
                className={resource === "latestCpu" ? "active" : ""}
                aria-pressed={resource === "latestCpu"}
                onClick={() => setResource("latestCpu")}
              >
                CPU
              </button>
              <button
                className={resource === "latestMemory" ? "active" : ""}
                aria-pressed={resource === "latestMemory"}
                onClick={() => setResource("latestMemory")}
              >
                RAM
              </button>
            </div>
          </div>
          {!ranked.length ? (
            <div className="panel-empty">
              Chưa có mẫu tài nguyên từ host trực tuyến.
            </div>
          ) : (
            <div className="resource-ranking">
              {ranked.map((node, index) => (
                <button
                  className="ranked-host"
                  key={node.id}
                  onClick={() => onInspectNode(node)}
                  aria-label={`Phân tích telemetry ${node.hostname}`}
                >
                  <span className="rank-number">{index + 1}</span>
                  <span className="ranked-host-data">
                    <strong>{node.hostname}</strong>
                    <small>{node.ip_address}</small>
                  </span>
                    <span className="micro-meter ranking-meter">
                      <i
                        className={
                          node[resource]! > (resource === "latestCpu" ? 75 : 85)
                            ? "warning"
                            : resource === "latestMemory"
                              ? "memory"
                              : ""
                        }
                        style={{
                          width: `${Math.max(0, Math.min(100, node[resource]!))}%`,
                        }}
                      />
                      <span className="threshold-mark" style={{ left: resource === "latestCpu" ? "75%" : "85%" }} />
                    </span>
                  <b>{node[resource]!.toFixed(1)}%</b>
                  <span className={`ranking-state ${node[resource]! > (resource === "latestCpu" ? 75 : 85) ? "warning" : ""}`}>
                    {node[resource]! > (resource === "latestCpu" ? 75 : 85) ? "Vượt ngưỡng" : "Trong ngưỡng"}
                  </span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          )}
          <div className="panel-foot">
            <span>Tối đa 5 máy chủ · mẫu gần nhất · Vạch ngưỡng {resource === "latestCpu" ? "75%" : "85%"}</span>
            <span>Chọn host để phân tích</span>
          </div>
        </section>
      </div>
    </div>
  );
}
