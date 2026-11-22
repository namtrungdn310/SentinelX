import { useState, useRef } from "react";
import { ChevronRight, Search, Terminal } from "lucide-react";
import type { Node, RealtimeMessage } from "../types";
import { formatRealtimeMessage, eventLabel, filterEvents, type EventCategory } from "../events";

const categories: { value: EventCategory; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "alert", label: "Cảnh báo" },
  { value: "security", label: "Thao tác" },
  { value: "status", label: "Trạng thái kết nối" },
  { value: "telemetry", label: "Mẫu dữ liệu" },
];

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
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState<EventCategory>("all");
  const listRef = useRef<HTMLDivElement>(null);

  const handleControlsWheel = (e: React.WheelEvent) => {
    if (!preview && listRef.current) {
      listRef.current.scrollTop += e.deltaY;
    }
  };

  const visible = filterEvents(events, nodes, category, filter);
  const limit = preview ? 5 : 40;
  const stateTone = isConnected || isDemoMode ? "ok" : "crit";
  return (
    <section className={`panel event-panel ${preview ? "event-preview" : "event-full"}`} aria-label="Nhật ký sự kiện">
      <div className="event-controls" onWheel={handleControlsWheel}>
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
            <label className="event-search">
              <Search size={14} aria-hidden="true" />
              <span className="sr-only">Lọc sự kiện</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Lọc sự kiện hoặc tên máy chủ…"
              />
            </label>
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
            {visible.length} / {events.length} sự kiện trong bộ đệm
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
        ref={listRef}
        className="event-list"
        role="log"
        aria-live="polite"
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
            const isSecurityCrit =
              event.event === "incident_alert" || event.event === "defense_action_created";
            const isSecuritySuccess =
              event.event === "defense_action_reverted" || event.event === "recovery_completed";
            const warning =
              event.event === "system_alert" ||
              event.event === "detection_alert" ||
              event.event === "incident_update";

            const eventTypeClass = isSecurityCrit
              ? "crit"
              : isSecuritySuccess
                ? "ok"
                : warning
                  ? "warn"
                  : metric
                    ? "metric"
                    : "info";

            const hostname =
              nodes.find((node) => node.id === event.data.node_id)?.hostname ??
              String(event.data.hostname ?? event.data.node_id ?? "Controller");

            const message = metric
              ? `Nhận ${event.data.samples?.length ?? 0} mẫu CPU, RAM, ổ đĩa và mạng`
              : formatRealtimeMessage(event);

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
                <span className={`event-type ${eventTypeClass}`}>
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
        {isDemoMode
          ? "Bộ đệm phiên · Mô phỏng"
          : isConnected
            ? "Lịch sử gần đây và sự kiện trực tiếp · Đã kết nối"
            : "Đang chờ kết nối Controller"}
        <span>
          {Math.min(limit, visible.length)} / {visible.length}{" "}
          sự kiện
        </span>
      </div>
    </section>
  );
}
