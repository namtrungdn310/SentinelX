import type { Node, RealtimeMessage } from "./types";

export type EventCategory = "all" | "status" | "telemetry" | "security";

const eventLabels: Record<string, string> = {
  metric_update: "Cập nhật tài nguyên",
  node_status: "Thay đổi trạng thái",
  heartbeat: "Tín hiệu hoạt động",
  system_alert: "Cảnh báo hệ thống",
  detection_alert: "Bất thường phát hiện",
  node_enrolled: "Đăng ký máy chủ",
  incident_alert: "Phát hiện sự cố an ninh",
  incident_update: "Cập nhật sự cố an ninh",
  defense_action_created: "Kích hoạt lệnh chặn (nftables)",
  defense_action_updated: "Cập nhật lệnh phòng thủ",
  defense_action_reverted: "Gỡ bỏ khóa IP (Recovery)",
  recovery_completed: "Khôi phục hoàn tất",
};

const statusEvents = new Set([
  "node_status",
  "heartbeat",
  "system_alert",
  "detection_alert",
  "node_enrolled",
  "incident_alert",
  "incident_update",
  "defense_action_created",
  "defense_action_updated",
  "defense_action_reverted",
  "recovery_completed",
]);

const securityEvents = new Set([
  "detection_alert",
  "incident_alert",
  "incident_update",
  "defense_action_created",
  "defense_action_updated",
  "defense_action_reverted",
  "recovery_completed",
]);

export function eventLabel(event: string): string {
  return Object.hasOwn(eventLabels, event) ? eventLabels[event] : "Sự kiện khác";
}

export function detectionMessage(event: RealtimeMessage): string {
  const details = event.data.details;
  const severities: Record<string, string> = {
    LOW: "Thấp",
    MEDIUM: "Trung bình",
    HIGH: "Cao",
    CRITICAL: "Nghiêm trọng",
  };
  const rawSeverity = String(event.data.severity);
  const severity = Object.hasOwn(severities, rawSeverity) ? severities[rawSeverity] : "Cảnh báo";
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
    const attacker = event.data.attacker_ip ? ` từ IP ${event.data.attacker_ip}` : "";
    return summary ? `${summary}${attacker}` : `Phát hiện sự cố an ninh mới${attacker}`;
  }
  if (event.event === "incident_update") {
    const status = event.data.status ? ` → ${event.data.status}` : "";
    return `Cập nhật sự cố ${event.data.id ?? ""}${status}`;
  }
  if (event.event === "defense_action_created") {
    const target = event.data.target_ip ? `IP ${event.data.target_ip}` : "mục tiêu";
    const duration = event.data.duration_seconds
      ? ` trong ${Math.floor(Number(event.data.duration_seconds) / 60)} phút`
      : "";
    return `Tường lửa nftables: Khóa ${target} tại inet sentinelx (DROP)${duration}`;
  }
  if (event.event === "defense_action_reverted") {
    const target = event.data.target_ip ? `IP ${event.data.target_ip}` : "mục tiêu";
    return `Tường lửa nftables: Đã gỡ bỏ khóa ${target} khỏi kernel drop set`;
  }
  if (event.event === "recovery_completed") {
    return "Chu kỳ hạ nhiệt và hoàn tác phòng thủ hoàn tất an toàn";
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
  if (category === "security") return securityEvents.has(event);
  return statusEvents.has(event);
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
