import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Node, Project } from "../types";
import { healthLabels, nodeHealth, validMetric } from "../presentation";
import type { Health } from "../presentation";
import { AttentionPanel } from "./AttentionPanel";

interface Props {
  nodes: Node[];
  projects: Project[];
  selectedProjectId: string | null;
  onStatusSelect: (status: Health) => void;
  onProjectSelect: (projectId: string) => void;
  onInspectNode: (node: Node) => void;
  onOpenDetail: (node: Node) => void;
  onViewHosts: () => void;
}

function average(nodes: Node[], key: "latestCpu" | "latestMemory"): string {
  const reporting = nodes.filter(
    (node) =>
      (node.status === "online" || node.status === "degraded") &&
      validMetric(node[key]),
  );
  return reporting.length
    ? `${(reporting.reduce((sum, node) => sum + node[key]!, 0) / reporting.length).toFixed(1)}%`
    : "—";
}

export function InfrastructureOverview({
  nodes,
  projects,
  selectedProjectId,
  onStatusSelect,
  onProjectSelect,
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
  const healthPercentage = nodes.length
    ? Math.round((counts.ok / nodes.length) * 100)
    : null;
  const ranked = nodes
    .filter(
      (node) =>
        (node.status === "online" || node.status === "degraded") &&
        validMetric(node[resource]),
    )
    .sort((a, b) => b[resource]! - a[resource]!)
    .slice(0, 5);
  const scopedProjects = projects.filter(
    (project) => !selectedProjectId || project.id === selectedProjectId,
  );
  return (
    <div className="infrastructure-overview" aria-label="Tổng quan toàn cụm">
      <div className="overview-grid">
        <section
          className="panel fleet-health-panel"
          aria-label="Tỷ lệ máy chủ ổn định"
        >
          <div className="panel-heading">
            <h2>
              Tỷ lệ máy chủ ổn định
            </h2>
            <button className="text-button" onClick={onViewHosts}>Xem máy chủ <ChevronRight size={14} /></button>
          </div>
          <div className="fleet-health-body">
          <div className="fleet-health-summary">
            <strong>
              {healthPercentage === null ? "—" : `${healthPercentage}%`}
            </strong>
            <span>
              máy chủ ổn định
              <small>
                {counts.ok} / {nodes.length} máy chủ trong phạm vi
              </small>
            </span>
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
      </div>
      <div className="overview-grid">
        <section
          className="panel project-summary-panel"
          aria-label="Tổng hợp theo dự án"
        >
          <div className="panel-heading">
            <h2>
              Tổng hợp theo dự án
            </h2>
            <span className="count-badge">{scopedProjects.length}</span>
          </div>
          {!scopedProjects.length ? (
            <div className="panel-empty">Chưa có dự án trong workspace.</div>
          ) : (
            <div className="table-scroll">
              <table className="host-table project-summary-table">
                <thead>
                  <tr>
                    <th>Dự án</th>
                    <th>Trực tuyến / tổng</th>
                    <th>Cần xử lý</th>
                    <th>CPU trung bình</th>
                    <th>RAM trung bình</th>
                  </tr>
                </thead>
                <tbody>
                  {scopedProjects.map((project) => {
                    const members = nodes.filter(
                      (node) => node.project_id === project.id,
                    );
                    const online = members.filter(
                      (node) =>
                        node.status === "online" || node.status === "degraded",
                    ).length;
                    const attention = members.filter(
                      (node) => ["warn", "crit", "unenrolled"].includes(nodeHealth(node)),
                    ).length;
                    return (
                      <tr key={project.id}>
                        <td>
                          <button
                            className="project-drilldown"
                            onClick={() => onProjectSelect(project.id)}
                          >
                            {project.name}
                            <ChevronRight size={13} />
                          </button>
                        </td>
                        <td className="font-mono">
                          {online} / {members.length}
                        </td>
                        <td>
                          <span
                            className={`project-attention ${members.some((node) => ["warn", "crit"].includes(nodeHealth(node))) ? "has-attention" : ""}`}
                          >
                            {attention}
                          </span>
                        </td>
                        <td className="font-mono">
                          {average(members, "latestCpu")}
                        </td>
                        <td className="font-mono">
                          {average(members, "latestMemory")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
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
