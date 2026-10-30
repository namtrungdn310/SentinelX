import type { Node, RealtimeMessage } from "./types";

export type EventCategory = "all" | "status" | "telemetry";

const eventLabels: Record<string, string> = {
  metric_update: "Cập nhật tài nguyên",
  node_status: "Thay đổi trạng thái",
  heartbeat: "Tín hiệu hoạt động",
  system_alert: "Cảnh báo hệ thống",
  node_enrolled: "Đăng ký máy chủ",
};

const statusEvents = new Set([
  "node_status",
  "heartbeat",
  "system_alert",
  "node_enrolled",
]);

export function eventLabel(event: string): string {
  return Object.hasOwn(eventLabels, event) ? eventLabels[event] : "Sự kiện khác";
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
