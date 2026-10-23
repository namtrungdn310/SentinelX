import {
  Server,
  Cpu,
  MemoryStick,
  ArrowDownUp,
  TriangleAlert,
} from "lucide-react";
import type { Node } from "../types";
import { formatBytes, nodeHealth } from "../presentation";

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
  const cpu = online.filter((node) => node.latestCpu !== undefined);
  const mem = online.filter((node) => node.latestMemory !== undefined);
  const avgCpu = cpu.length
    ? cpu.reduce((sum, node) => sum + node.latestCpu!, 0) / cpu.length
    : null;
  const avgMem = mem.length
    ? mem.reduce((sum, node) => sum + node.latestMemory!, 0) / mem.length
    : null;
  const rx = online.reduce((sum, node) => sum + (node.latestRxBytes ?? 0), 0);
  const tx = online.reduce((sum, node) => sum + (node.latestTxBytes ?? 0), 0);
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
          <span>HOST TRỰC TUYẾN</span>
        </div>
        <div className="stat-value">
          {online.length}
          <span>/ {nodes.length}</span>
          <span className="stat-state">ONLINE</span>
        </div>
        <div className="stat-bottom">
          <span>{offline} offline</span>
          <span>{waiting} chờ đăng ký</span>
        </div>
      </article>
      <article className={`stat-card ${attention ? "stat-attention" : ""}`}>
        <div className="stat-top">
          <TriangleAlert size={14} />
          <span>HOST CẦN CHÚ Ý</span>
        </div>
        <div className="stat-value">
          {attention}
          <span className="stat-state">{attention ? "ATTENTION" : "OK"}</span>
        </div>
        <div className="stat-bottom">
          <span>{warning} vượt ngưỡng / degraded</span>
        </div>
      </article>
      <article className="stat-card stat-cpu">
        <div className="stat-top">
          <Cpu size={14} />
          <span>CPU TRUNG BÌNH</span>
        </div>
        <div className="stat-value">
          {avgCpu?.toFixed(1) ?? "—"}
          <span>%</span>
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
        </div>
      </article>
      <article className="stat-card stat-memory">
        <div className="stat-top">
          <MemoryStick size={14} />
          <span>RAM TRUNG BÌNH</span>
        </div>
        <div className="stat-value">
          {avgMem?.toFixed(1) ?? "—"}
          <span>%</span>
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
        </div>
      </article>
      <article className="stat-card stat-network">
        <div className="stat-top">
          <ArrowDownUp size={14} />
          <span>Dữ liệu mạng tích lũy</span>
        </div>
        <div className="stat-value network-value">
          {rx + tx ? formatBytes(rx + tx) : "—"}
        </div>
        <div className="stat-bottom">
          <span>RX {formatBytes(rx)}</span>
          <span>TX {formatBytes(tx)}</span>
        </div>
      </article>
    </section>
  );
}
