import type { Node, RealtimeMessage } from "./types";
import { severityLabel } from "./presentation";

export type EventCategory =
  | "all"
  | "alert"
  | "security"
  | "status"
  | "telemetry";

const eventLabels: Record<string, string> = {
  metric_update: "Cập nhật tài nguyên",
  node_status: "Thay đổi trạng thái",
  heartbeat: "Tín hiệu hoạt động",
  system_alert: "Cảnh báo hệ thống",
  detection_alert: "Bất thường tài nguyên",
  node_enrolled: "Đăng ký máy chủ",
  incident_alert: "Phát hiện sự cố an ninh",
  incident_update: "Cập nhật sự cố an ninh",
  defense_action_created: "Khóa IP qua tường lửa",
  defense_action_updated: "Cập nhật lệnh tường lửa",
  defense_action_reverted: "Gỡ bỏ khóa IP",
  recovery_completed: "Khôi phục hoàn tất",
};

const alertEvents = new Set([
  "incident_alert",
  "incident_update",
  "detection_alert",
  "system_alert",
]);

const securityEvents = new Set([
  "defense_action_created",
  "defense_action_updated",
  "defense_action_reverted",
  "recovery_completed",
]);

const statusEvents = new Set([
  "node_status",
  "heartbeat",
  "node_enrolled",
]);

export function eventLabel(event: string): string {
  return Object.hasOwn(eventLabels, event) ? eventLabels[event] : "Sự kiện khác";
}

export function detectionMessage(event: RealtimeMessage): string {
  const details = event.data.details;
  const severity = severityLabel(String(event.data.severity), "Cảnh báo");
  if (!details || typeof details !== "object" || Array.isArray(details)) return severity;
  const value = details as Record<string, unknown>;
  const names: Record<string, string> = {
    cpu_percent: "CPU",
    memory_percent: "RAM",
    disk_percent: "Ổ đĩa",
  };
  const rawMetric = String(value.metric_name);
  const metric = Object.hasOwn(names, rawMetric) ? names[rawMetric] : "Tài nguyên";
  const current = value.current_value;
  const threshold = value.threshold_value;
  if (typeof current !== "number" || typeof threshold !== "number") return `${severity} · ${metric}`;
  const count = typeof value.consecutive_samples === "number" ? value.consecutive_samples : 1;
  return `${severity} · ${metric} ${current}% ≥ ${threshold}% · ${count} mẫu liên tiếp`;
}

export function formatRealtimeMessage(event: RealtimeMessage): string {
  if (event.event === "detection_alert") return detectionMessage(event);
  if (event.event === "incident_alert") {
    const summary = event.data.summary || event.data.title;
    if (summary) {
      const cleanSummary = String(summary).trim();
      if (event.data.attacker_ip && !cleanSummary.includes(String(event.data.attacker_ip))) {
        return `${cleanSummary} · IP: ${event.data.attacker_ip}`;
      }
      return cleanSummary;
    }
    const attacker = event.data.attacker_ip ? ` · IP: ${event.data.attacker_ip}` : "";
    return `Phát hiện sự cố an ninh${attacker}`;
  }
  if (event.event === "incident_update") {
    const status = event.data.status ? ` → ${event.data.status}` : "";
    return `Cập nhật sự cố ${event.data.id ?? ""}${status}`;
  }
  if (event.event === "defense_action_created") {
    const target = event.data.target_ip ? `địa chỉ IP ${event.data.target_ip}` : "mục tiêu";
    const duration = event.data.duration_seconds
      ? ` trong ${Math.floor(Number(event.data.duration_seconds) / 60)} phút`
      : "";
    return `Tường lửa: Khóa ${target} trên máy chủ${duration}`;
  }
  if (event.event === "defense_action_reverted") {
    const target = event.data.target_ip ? `địa chỉ IP ${event.data.target_ip}` : "mục tiêu";
    return `Tường lửa: Đã gỡ bỏ khóa ${target} trên máy chủ`;
  }
  if (event.event === "recovery_completed") {
    return "Đã hoàn tất khôi phục và gỡ chặn tường lửa an toàn";
  }
  return String(event.data.message ?? "Đã nhận sự kiện từ Controller");
}

/** Stable IDs unite REST history and WebSocket replay without duplicate alerts. */
export function mergeEvents(...sources: RealtimeMessage[][]): RealtimeMessage[] {
  const items = new Map<string, RealtimeMessage>();
  for (const event of sources.flat()) {
    const id = typeof event.data.id === "string" ? event.data.id : null;
    const key = id
      ? `${event.event}:${id}`
      : `${event.event}:${event.timestamp}:${String(event.data.node_id ?? "")}`;
    items.set(key, event);
  }
  return [...items.values()].sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp)).slice(0, 50);
}

export function eventMatchesCategory(
  event: string,
  category: EventCategory,
): boolean {
  if (category === "all") return true;
  if (category === "telemetry") return event === "metric_update";
  if (category === "alert") return alertEvents.has(event);
  if (category === "security") return securityEvents.has(event);
  if (category === "status") return statusEvents.has(event);
  return false;
}

/** Filter the scoped session buffer without changing order or hiding unknown events in All. */
export function filterEvents(
  events: RealtimeMessage[],
  nodes: Node[],
  category: EventCategory,
  query: string,
): RealtimeMessage[] {
  const normalized = query.trim().toLocaleLowerCase("vi-VN");
  const hostnames = new Map(nodes.map((node) => [node.id, node.hostname]));
  return events.filter((event) => {
    if (!eventMatchesCategory(event.event, category)) return false;
    if (!normalized) return true;
    return [
      event.event,
      eventLabel(event.event),
      hostnames.get(event.data.node_id ?? "") ?? "",
      JSON.stringify(event.data),
    ].some((value) => value.toLocaleLowerCase("vi-VN").includes(normalized));
  });
}
