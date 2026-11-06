import type { Node, RealtimeMessage } from "./types";

export type EventCategory = "all" | "status" | "telemetry";

const eventLabels: Record<string, string> = {
  metric_update: "Cập nhật tài nguyên",
  node_status: "Thay đổi trạng thái",
  heartbeat: "Tín hiệu hoạt động",
  system_alert: "Cảnh báo hệ thống",
  detection_alert: "Bất thường tài nguyên",
  node_enrolled: "Đăng ký máy chủ",
};

const statusEvents = new Set([
  "node_status",
  "heartbeat",
  "system_alert",
  "detection_alert",
  "node_enrolled",
]);

export function eventLabel(event: string): string {
  return Object.hasOwn(eventLabels, event) ? eventLabels[event] : "Sự kiện khác";
}

export function detectionMessage(event: RealtimeMessage): string {
  const details = event.data.details;
  const severities: Record<string, string> = {
    LOW: "Thấp", MEDIUM: "Trung bình", HIGH: "Cao", CRITICAL: "Nghiêm trọng",
  };
  const rawSeverity = String(event.data.severity);
  const severity = Object.hasOwn(severities, rawSeverity) ? severities[rawSeverity] : "Cảnh báo";
  if (!details || typeof details !== "object" || Array.isArray(details)) return severity;
  const value = details as Record<string, unknown>;
  const names: Record<string, string> = {
    cpu_percent: "CPU", memory_percent: "RAM", disk_percent: "Ổ đĩa",
  };
  const rawMetric = String(value.metric_name);
  const metric = Object.hasOwn(names, rawMetric) ? names[rawMetric] : "Tài nguyên";
  const current = value.current_value;
  const threshold = value.threshold_value;
  if (typeof current !== "number" || typeof threshold !== "number") return `${severity} · ${metric}`;
  const count = typeof value.consecutive_samples === "number" ? value.consecutive_samples : 1;
  return `${severity} · ${metric} ${current}% ≥ ${threshold}% · ${count} mẫu liên tiếp`;
}

/** Stable IDs unite REST history and WebSocket replay without duplicate alerts. */
export function mergeEvents(...sources: RealtimeMessage[][]): RealtimeMessage[] {
  const items = new Map<string, RealtimeMessage>();
  for (const event of sources.flat()) {
    const key = event.event === "detection_alert" && typeof event.data.id === "string"
      ? `detection:${event.data.id}`
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
  return category === "telemetry"
    ? event === "metric_update"
    : statusEvents.has(event);
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
