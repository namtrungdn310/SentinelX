import { useState } from "react";
import { ArrowUpRight, Pause, Play, Search, Terminal } from "lucide-react";
import type { Node, RealtimeMessage } from "../types";

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
  const visible = (pausedEvents ?? events).filter((event) => {
    const hostname =
      nodes.find((node) => node.id === event.data.node_id)?.hostname ?? "";
    return [event.event, hostname, JSON.stringify(event.data)].some((value) =>
      value.toLowerCase().includes(filter.toLowerCase()),
    );
  });
  return (
    <section className="panel event-panel" aria-label="Nhật ký sự kiện">
      <div className="panel-heading">
        <h2>
          <Terminal size={15} />{" "}
          {preview ? "Sự kiện gần nhất" : "Sự kiện hệ thống"}{" "}
          <span className="count-badge">{visible.length}</span>
        </h2>
        {preview ? (
          <button className="text-button" onClick={onOpenAll}>
            Mở nhật ký <ArrowUpRight size={14} />
          </button>
        ) : (
          <div className="event-heading-actions">
            <label className="event-search">
              <Search size={14} />
              <span className="sr-only">Lọc sự kiện</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Lọc event, hostname…"
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
              {pausedEvents ? <Play size={13} /> : <Pause size={13} />}
              {pausedEvents ? "Tiếp tục" : "Tạm dừng"}
            </button>
          </div>
        )}
      </div>
      <div className="event-columns" aria-hidden="true">
        <span>THỜI GIAN</span>
        <span>EVENT</span>
        <span>HOST</span>
        <span>NỘI DUNG</span>
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
              : preview
                ? "Chưa có sự kiện trạng thái trong bộ đệm hiện tại."
                : "Chờ sự kiện từ máy chủ trong phạm vi đang chọn."}
          </div>
        ) : (
          visible.slice(0, preview ? 5 : 40).map((event, index) => {
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
                      ? `Trạng thái: ${event.data.status}`
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
                  {event.event}
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
          className={`health-dot ${pausedEvents ? "warn" : isConnected ? "ok" : "crit"}`}
        />
        {pausedEvents
          ? "Đang tạm dừng · giữ nguyên dữ liệu hiển thị"
          : isDemoMode
            ? "Dữ liệu mô phỏng"
            : isConnected
              ? "WebSocket đã kết nối"
              : "Đang chờ kết nối Controller"}
        <span>
          {preview
            ? `${Math.min(5, visible.length)} / ${visible.length}`
            : visible.length}{" "}
          sự kiện
        </span>
      </div>
    </section>
  );
}
