import {
  Server,
  Cpu,
  MemoryStick,
  ArrowDownUp,
  TriangleAlert,
} from "lucide-react";
import type { Node } from "../types";
import { formatBytes, nodeHealth, validMetric } from "../presentation";

export function KPICards({
  nodes,
  isLoading,
}: {
  nodes: Node[];
  isLoading: boolean;
}) {
  const online = nodes.filter(
    (node) => node.status === "online" || node.status === "degraded",
  );
  const cpu = online.filter((node) => validMetric(node.latestCpu));
  const mem = online.filter((node) => validMetric(node.latestMemory));
  const avgCpu = cpu.length
    ? cpu.reduce((sum, node) => sum + node.latestCpu!, 0) / cpu.length
    : null;
  const avgMem = mem.length
    ? mem.reduce((sum, node) => sum + node.latestMemory!, 0) / mem.length
    : null;
  const rxNodes = online.filter((node) => validMetric(node.latestRxBytes));
  const txNodes = online.filter((node) => validMetric(node.latestTxBytes));
  const rx = rxNodes.reduce((sum, node) => sum + node.latestRxBytes!, 0);
  const tx = txNodes.reduce((sum, node) => sum + node.latestTxBytes!, 0);
  const warning = nodes.filter((node) => nodeHealth(node) === "warn").length;
  const offline = nodes.filter((node) => node.status === "offline").length;
  const waiting = nodes.filter((node) => node.status === "unenrolled").length;
  const attention = warning + offline + waiting;

  return (
    <section
      className="kpi-grid"
      aria-label="Chỉ số tổng quan"
      aria-busy={isLoading}
    >
      <article className="stat-card stat-online">
        <div className="stat-top">
          <Server size={14} />
          <span>Máy chủ trực tuyến</span>
        </div>
        <div className="stat-value">
          {online.length}
          <span>/ {nodes.length}</span>
        </div>
        <div className="stat-bottom">
          <span>{offline} mất kết nối</span>
          <span>{waiting} chờ đăng ký</span>
        </div>
      </article>
      <article className={`stat-card ${warning + offline > 0 ? "stat-attention" : ""}`}>
        <div className="stat-top">
          <TriangleAlert size={14} />
          <span>Cần xử lý</span>
        </div>
        <div className="stat-value">
          {attention}
        </div>
        <div className="stat-bottom">
          <span>{warning} cảnh báo{offline > 0 ? ` · ${offline} mất kết nối` : ""}</span>
          <span>{waiting} chờ đăng ký</span>
        </div>
      </article>
      <article className="stat-card stat-cpu">
        <div className="stat-top">
          <Cpu size={14} />
          <span>CPU trung bình</span>
        </div>
        <div className="stat-value">
          {avgCpu?.toFixed(1) ?? "—"}
          {avgCpu !== null && <span>%</span>}
        </div>
        <div className="stat-bottom">
          {cpu.length
            ? `${cpu.length} host có mẫu · ngưỡng 75%`
            : "Chưa có dữ liệu CPU"}
        </div>
        <div className="stat-track">
          <i
            className={avgCpu !== null && avgCpu > 75 ? "warn" : "cpu"}
            style={{ width: `${Math.min(100, avgCpu ?? 0)}%` }}
          />
          <span className="threshold-mark" style={{ left: "75%" }} />
        </div>
      </article>
      <article className="stat-card stat-memory">
        <div className="stat-top">
          <MemoryStick size={14} />
          <span>RAM trung bình</span>
        </div>
        <div className="stat-value">
          {avgMem?.toFixed(1) ?? "—"}
          {avgMem !== null && <span>%</span>}
        </div>
        <div className="stat-bottom">
          {mem.length
            ? `${mem.length} host có mẫu · ngưỡng 85%`
            : "Chưa có dữ liệu RAM"}
        </div>
        <div className="stat-track">
          <i
            className={avgMem !== null && avgMem > 85 ? "warn" : "memory"}
            style={{ width: `${Math.min(100, avgMem ?? 0)}%` }}
          />
          <span className="threshold-mark" style={{ left: "85%" }} />
        </div>
      </article>
      <article className="stat-card stat-network">
        <div className="stat-top">
          <ArrowDownUp size={14} />
          <span>Dữ liệu mạng tích lũy</span>
        </div>
        <div className="stat-value network-value">
          {rxNodes.length || txNodes.length ? formatBytes(rx + tx) : "—"}
        </div>
        <div className="stat-bottom">
          <span>RX {rxNodes.length ? formatBytes(rx) : "—"}</span>
          <span>TX {txNodes.length ? formatBytes(tx) : "—"}</span>
        </div>
        {(rxNodes.length !== online.length || txNodes.length !== online.length) && <small className="metric-coverage">Dữ liệu chưa đủ toàn phạm vi</small>}
      </article>
    </section>
  );
}
