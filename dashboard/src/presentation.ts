import type { Node } from "./types";
export type Health = "ok" | "warn" | "crit" | "unenrolled" | "unknown";
export const validMetric = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
export const formatPercent = (value: unknown): string =>
  validMetric(value) ? `${value.toFixed(1)}%` : "—";
export function nodeHealth(node: Node): Health {
  if (node.status === "unenrolled") return "unenrolled";
  if (node.status === "offline") return "crit";
  if (
    node.status === "degraded" ||
    (validMetric(node.latestCpu) && node.latestCpu > 75) ||
    (validMetric(node.latestMemory) && node.latestMemory > 85)
  )
    return "warn";
  return validMetric(node.latestCpu) && validMetric(node.latestMemory) ? "ok" : "unknown";
}
export const healthLabels: Record<Health, string> = {
  ok: "Ổn định",
  warn: "Cảnh báo",
  crit: "Mất kết nối",
  unenrolled: "Chờ đăng ký",
  unknown: "Chưa có mẫu",
};
// A degraded Agent is not necessarily over a resource threshold.
export function nodeHealthLabel(node: Node): string {
  const health = nodeHealth(node);
  if (health !== "warn") return healthLabels[health];
  return (validMetric(node.latestCpu) && node.latestCpu > 75) ||
    (validMetric(node.latestMemory) && node.latestMemory > 85)
    ? "Vượt ngưỡng"
    : "Suy giảm";
}
export function nodeRole(hostname: string): string {
  const name = hostname.toLowerCase();
  if (/ingress|gateway|lb/.test(name)) return "Gateway";
  if (/db|pg|primary/.test(name)) return "Database";
  if (/api|backend/.test(name)) return "API server";
  return "Worker";
}
export function formatBytes(bytes: number): string {
  if (!validMetric(bytes)) return "—";
  if (bytes <= 0) return "0 B";
  const index = Math.min(3, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(1)} ${["B", "KB", "MB", "GB"][index]}`;
}

export function getNodeHardware(node: Partial<Node>): {
  cpuCores: number;
  totalMemoryBytes: number;
  totalDiskBytes: number;
} {
  const name = (node.hostname || "").toLowerCase();
  let defaultCores = 4;
  let defaultMemGb = 2; // Default 2 GB RAM (matching user reference)
  let defaultDiskGb = 80;

  if (/ingress|gateway|edge/.test(name)) {
    defaultCores = 2;
    defaultMemGb = 2;
    defaultDiskGb = 50;
  } else if (/db|pg|primary|postgres/.test(name)) {
    defaultCores = 8;
    defaultMemGb = 8;
    defaultDiskGb = 200;
  } else if (/worker|celery/.test(name)) {
    defaultCores = 4;
    defaultMemGb = 2;
    defaultDiskGb = 100;
  } else if (/storage|nas|backup/.test(name)) {
    defaultCores = 2;
    defaultMemGb = 4;
    defaultDiskGb = 500;
  }

  return {
    cpuCores: node.cpuCores ?? defaultCores,
    totalMemoryBytes: node.totalMemoryBytes ?? defaultMemGb * 1024 * 1024 * 1024,
    totalDiskBytes: node.totalDiskBytes ?? defaultDiskGb * 1024 * 1024 * 1024,
  };
}

export function formatMemoryUsage(percent?: number, totalBytes?: number): string {
  if (!validMetric(percent)) return "—";
  const total = totalBytes ?? 2 * 1024 * 1024 * 1024;
  const usedBytes = (percent / 100) * total;
  return `${formatBytes(usedBytes)} / ${formatBytes(total)}`;
}

export function formatCpuUsage(percent?: number, cores?: number): string {
  if (!validMetric(percent)) return "—";
  const totalCores = cores ?? 4;
  const usedCores = ((percent / 100) * totalCores).toFixed(1);
  return `${usedCores} / ${totalCores} vCPU`;
}

export function formatDiskUsage(percent?: number, totalBytes?: number): string {
  if (!validMetric(percent)) return "—";
  const total = totalBytes ?? 100 * 1024 * 1024 * 1024;
  const usedBytes = (percent / 100) * total;
  return `${formatBytes(usedBytes)} / ${formatBytes(total)}`;
}
