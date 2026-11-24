import {
  Server,
  Cpu,
  MemoryStick,
  ArrowDownUp,
  ShieldAlert,
  ArrowLeftRight,
  ChevronRight,
} from "lucide-react";
import type { Incident, Node, Project } from "../types";
import { formatBytes, getNodeHardware, validMetric } from "../presentation";

export function KPICards({
  nodes,
  incidents = [],
  activeProject = null,
  isLoading,
  onOpenLoadBalancer,
}: {
  nodes: Node[];
  incidents?: Incident[];
  activeProject?: Project | null;
  isLoading: boolean;
  onOpenLoadBalancer?: () => void;
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
  const totalCpuCores = cpu.reduce((sum, node) => sum + getNodeHardware(node).cpuCores, 0);
  const usedCpuCores = cpu.reduce(
    (sum, node) => sum + (node.latestCpu! / 100) * getNodeHardware(node).cpuCores,
    0,
  );
  const totalMemBytes = mem.reduce((sum, node) => sum + getNodeHardware(node).totalMemoryBytes, 0);
  const usedMemBytes = mem.reduce(
    (sum, node) => sum + (node.latestMemory! / 100) * getNodeHardware(node).totalMemoryBytes,
    0,
  );
  const rxNodes = online.filter((node) => validMetric(node.latestRxBytes));
  const txNodes = online.filter((node) => validMetric(node.latestTxBytes));
  const rx = rxNodes.reduce((sum, node) => sum + node.latestRxBytes!, 0);
  const tx = txNodes.reduce((sum, node) => sum + node.latestTxBytes!, 0);
  const offline = nodes.filter((node) => node.status === "offline").length;
  const waiting = nodes.filter((node) => node.status === "unenrolled").length;
  const activeIncidents = incidents.filter(
    (item) => item.status === "DETECTED" || item.status === "MITIGATING",
  );
  const criticalIncidents = activeIncidents.filter((item) => item.severity === "CRITICAL").length;
  const highIncidents = activeIncidents.filter((item) => item.severity === "HIGH").length;
  const lb = activeProject?.load_balancer;
  const showLbCard = Boolean(lb?.enabled);
  const lbNodes = nodes.filter((node) => node.lb_role === "lb_backend");
  const lbBackends = lbNodes.length;
  const lbReadyBackends = lbNodes.filter(
    (node) => node.status === "online" || node.status === "degraded",
  ).length;
  const lbAvailabilityPct = lbBackends > 0 ? (lbReadyBackends / lbBackends) * 100 : 0;
  const lbEndpointLabel = lb?.lb_url
    ? lb.lb_url.replace(/^https?:\/\//, "").replace(/\/$/, "")
    : "LB Hệ thống";
  const lbPortMatch = lbEndpointLabel.match(/:(\d+)$/);
  const lbCompactTarget = lbPortMatch ? `:${lbPortMatch[1]}` : lbEndpointLabel;

  return (
    <section
      className={`kpi-grid ${showLbCard ? "kpi-grid-6" : "kpi-grid-5"}`}
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
      <article className={`stat-card ${activeIncidents.length > 0 ? "stat-attention" : ""}`}>
        <div className="stat-top">
          <ShieldAlert size={14} />
          <span>Sự cố đang mở</span>
        </div>
        <div className="stat-value">
          {activeIncidents.length}
        </div>
        <div className="stat-bottom">
          <span>{criticalIncidents} khẩn cấp</span>
          <span>{highIncidents} cao</span>
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
          <span>
            {cpu.length
              ? `${usedCpuCores.toFixed(1)} / ${totalCpuCores} vCPU`
              : "Chưa có dữ liệu CPU"}
          </span>
          <span>{cpu.length ? "> 75%" : ""}</span>
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
          <span>
            {mem.length
              ? `${formatBytes(usedMemBytes)} / ${formatBytes(totalMemBytes)}`
              : "Chưa có dữ liệu RAM"}
          </span>
          <span>{mem.length ? "> 85%" : ""}</span>
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
          <span>Mạng · mẫu gần nhất</span>
        </div>
        <div className="stat-value network-value">
          {rxNodes.length || txNodes.length ? formatBytes(rx + tx) : "—"}
        </div>
        <div className="stat-bottom">
          <span>RX {rxNodes.length ? formatBytes(rx) : "—"}</span>
          <span>TX {txNodes.length ? formatBytes(tx) : "—"}</span>
        </div>
      </article>
      {showLbCard && lb && (
        <article
          className={`stat-card stat-lb ${
            lbBackends > 0 && lbReadyBackends < lbBackends ? "stat-attention" : ""
          } ${onOpenLoadBalancer ? "stat-card-interactive" : ""}`}
          title={`Mở luồng chia tải (${lbEndpointLabel})`}
          onClick={onOpenLoadBalancer}
          role={onOpenLoadBalancer ? "button" : undefined}
          tabIndex={onOpenLoadBalancer ? 0 : undefined}
          onKeyDown={
            onOpenLoadBalancer
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpenLoadBalancer();
                  }
                }
              : undefined
          }
        >
          <div className="stat-top">
            <ArrowLeftRight size={14} />
            <span>Cân bằng tải</span>
          </div>
          <div className="stat-value">
            {lbReadyBackends}
            <span>/ {lbBackends}</span>
          </div>
          <div className="stat-bottom">
            <span>
              {lb.algorithm === "least_in_flight"
                ? "Least In-Flight"
                : "Round Robin"}
            </span>
            <span className="font-mono stat-lb-endpoint">
              {lbCompactTarget}
              {onOpenLoadBalancer && <ChevronRight size={12} />}
            </span>
          </div>
          <div className="stat-track">
            <i
              className={
                lbBackends === 0 || lbReadyBackends < lbBackends ? "warn" : "lb"
              }
              style={{ width: `${lbAvailabilityPct}%` }}
            />
          </div>
        </article>
      )}
    </section>
  );
}
