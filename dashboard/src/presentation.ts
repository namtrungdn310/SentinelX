import type { Node } from "./types";
export type Health = "ok" | "warn" | "crit" | "unenrolled";
export function nodeHealth(node: Node): Health {
  if (node.status === "unenrolled") return "unenrolled";
  if (node.status === "offline") return "crit";
  if (
    node.status === "degraded" ||
    (node.latestCpu ?? 0) > 75 ||
    (node.latestMemory ?? 0) > 85
  )
    return "warn";
  return "ok";
}
export const healthLabels: Record<Health, string> = {
  ok: "Ổn định",
  warn: "Cần chú ý",
  crit: "Mất kết nối",
  unenrolled: "Chờ đăng ký",
};
export function nodeRole(hostname: string): string {
  const name = hostname.toLowerCase();
  if (/ingress|gateway|lb/.test(name)) return "Gateway";
  if (/db|pg|primary/.test(name)) return "Database";
  if (/api|backend/.test(name)) return "API server";
  return "Worker";
}
export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const index = Math.min(3, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(1)} ${["B", "KB", "MB", "GB"][index]}`;
}
