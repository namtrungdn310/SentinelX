import { useState } from "react";
import { ChevronRight, Pause, Play, Search, Terminal } from "lucide-react";
import type { Node, RealtimeMessage } from "../types";
import { eventLabel, filterEvents, type EventCategory } from "../events";

const categories: { value: EventCategory; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "status", label: "Trạng thái & cảnh báo" },
  { value: "telemetry", label: "Telemetry" },
];

const statusLabels: Record<string, string> = {
  healthy: "Ổn định",
  online: "Trực tuyến",
  offline: "Mất kết nối",
  degraded: "Suy giảm",
  unenrolled: "Chờ đăng ký",
};

interface Props {
  events: RealtimeMessage[];
  nodes: Node[];
  isConnected: boolean;
  isDemoMode: boolean;
  preview?: boolean;
  onOpenAll?: () => void;
}
export function LiveEventStream({
  events,
  nodes,
  isConnected,
  isDemoMode,
  preview = false,
  onOpenAll,
}: Props) {
  const [pausedEvents, setPausedEvents] = useState<RealtimeMessage[] | null>(
    null,
  );
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState<EventCategory>("all");
  const buffer = pausedEvents ?? events;
  const visible = filterEvents(buffer, nodes, category, filter);
  const limit = preview ? 5 : 40;
  const streamState = pausedEvents
    ? "Đã tạm dừng"
    : isDemoMode
      ? "Đang cập nhật · mô phỏng"
      : isConnected
        ? "Đang cập nhật"
    : "Đang chờ kết nối";
  const stateTone = pausedEvents ? "warn" : isConnected || isDemoMode ? "ok" : "crit";
  return (
    <section className={`panel event-panel ${preview ? "event-preview" : "event-full"}`} aria-label="Nhật ký sự kiện">
      <div className="event-controls">
      <div className="panel-heading">
        <h2>
          <Terminal size={15} aria-hidden="true" />{" "}
          {preview ? "Sự kiện gần nhất" : "Sự kiện hệ thống"}{" "}
          <span className="count-badge">{visible.length}</span>
        </h2>
        {preview ? (
          <button className="text-button" onClick={onOpenAll}>
            Mở nhật ký <ChevronRight size={14} aria-hidden="true" />
          </button>
        ) : (
          <div className="event-heading-actions">
            <span className="event-stream-state" role="status" aria-atomic="true">
              <span className={`health-dot ${stateTone}`} aria-hidden="true" />
              {streamState}
            </span>
            <label className="event-search">
              <Search size={14} aria-hidden="true" />
              <span className="sr-only">Lọc sự kiện</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Lọc sự kiện hoặc hostname…"
              />
            </label>
            <button
              className="btn btn-outline btn-sm"
              aria-label={
                pausedEvents ? "Tiếp tục nhật ký" : "Tạm dừng nhật ký"
              }
              aria-pressed={Boolean(pausedEvents)}
              onClick={() => setPausedEvents(pausedEvents ? null : [...events])}
            >
              {pausedEvents ? <Play size={13} aria-hidden="true" /> : <Pause size={13} aria-hidden="true" />}
              {pausedEvents ? "Tiếp tục" : "Tạm dừng"}
            </button>
          </div>
        )}
      </div>
      {!preview && (
        <div className="event-toolbar">
          <div className="event-filter-group segmented" role="group" aria-label="Nhóm sự kiện">
            {categories.map((item) => (
              <button
                key={item.value}
                type="button"
                className={category === item.value ? "active" : ""}
                aria-pressed={category === item.value}
                onClick={() => setCategory(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="event-filter-summary">
            {visible.length} / {buffer.length} sự kiện trong bộ đệm
          </span>
        </div>
      )}
      <div className="event-columns" aria-hidden="true">
        <span>Thời gian</span>
        <span>Sự kiện</span>
        <span>Máy chủ</span>
        <span>Nội dung</span>
      </div>
      </div>
      <div
        className="event-list"
        role="log"
        aria-live={pausedEvents ? "off" : "polite"}
        aria-relevant="additions"
      >
        {!visible.length ? (
          <div className="event-empty">
            {filter
              ? "Không có sự kiện khớp từ khóa."
              : category !== "all"
                ? "Chưa có sự kiện thuộc nhóm này trong bộ đệm hiện tại. Chọn Tất cả để xem các sự kiện khác."
                : preview
                  ? "Chưa có sự kiện trạng thái trong bộ đệm hiện tại."
                  : "Chờ sự kiện từ máy chủ trong phạm vi đang chọn."}
          </div>
        ) : (
          visible.slice(0, limit).map((event, index) => {
            const metric = event.event === "metric_update";
            const warning = event.event === "system_alert";
            const hostname =
              nodes.find((node) => node.id === event.data.node_id)?.hostname ??
              String(event.data.hostname ?? event.data.node_id ?? "Controller");
            const message = metric
              ? `Nhận ${event.data.samples?.length ?? 0} mẫu CPU, RAM, ổ đĩa và mạng`
              : String(
                  event.data.message ??
                    (event.data.status
                      ? `Trạng thái: ${Object.hasOwn(statusLabels, String(event.data.status)) ? statusLabels[String(event.data.status)] : event.data.status}`
                      : "Đã nhận sự kiện từ Controller"),
                );
            return (
              <article
                className="event-item"
                key={`${event.timestamp}-${event.event}-${index}`}
              >
                <time dateTime={event.timestamp}>
                  {new Date(event.timestamp).toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </time>
                <span
                  className={`event-type ${warning ? "warn" : metric ? "metric" : "info"}`}
                >
                  <span className="event-type-label">{eventLabel(event.event)}</span>
                  <code className="event-type-code">{event.event}</code>
                </span>
                <code>{hostname}</code>
                <span className="event-message">{message}</span>
              </article>
            );
          })
        )}
      </div>
      <div className="event-foot">
        <span
          className={`health-dot ${stateTone}`}
          aria-hidden="true"
        />
        {pausedEvents
          ? "Đang tạm dừng · giữ nguyên dữ liệu hiển thị"
          : isDemoMode
            ? "Bộ đệm phiên · mô phỏng"
            : isConnected
              ? "Bộ đệm phiên · đã kết nối"
              : "Đang chờ kết nối Controller"}
        <span>
          {Math.min(limit, visible.length)} / {visible.length}{" "}
          sự kiện
        </span>
      </div>
    </section>
  );
}
