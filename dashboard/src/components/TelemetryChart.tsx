import { useId, useState } from "react";
import { Activity, ArrowUpRight, Server } from "lucide-react";
import type { MetricSample, Node } from "../types";

interface Props {
  selectedNode: Node | null;
  samples: MetricSample[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
}
const clock = (date: string) =>
  new Date(date).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

export function TelemetryChart({
  selectedNode,
  samples,
  isLoading,
  error,
  onRetry,
}: Props) {
  const id = useId().replace(/:/g, "");
  const [showCpu, setShowCpu] = useState(true);
  const [showMem, setShowMem] = useState(true);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const data = [...samples].sort(
    (a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at),
  );
  const count = data.length;
  const width = 720;
  const height = 260;
  const pad = { top: 22, right: 20, bottom: 38, left: 64 };
  const graphWidth = width - pad.left - pad.right;
  const graphHeight = height - pad.top - pad.bottom;
  const firstTime = count ? Date.parse(data[0].observed_at) : 0;
  const duration =
    count > 1 ? Date.parse(data[count - 1].observed_at) - firstTime : 0;
  const x = (index: number) =>
    pad.left +
    (duration
      ? (Date.parse(data[index].observed_at) - firstTime) / duration
      : 0.5) *
      graphWidth;
  const y = (value: number) =>
    pad.top + (1 - Math.max(0, Math.min(100, value)) / 100) * graphHeight;
  const points = (key: "cpu_percent" | "memory_percent") =>
    data.map((sample, index) => `${x(index)},${y(sample[key])}`).join(" ");
  const area = (key: "cpu_percent" | "memory_percent") =>
    count
      ? `M ${x(0)},${y(0)} L ${points(key)} L ${x(count - 1)},${y(0)} Z`
      : "";
  const activeIndex =
    hoverIndex === null ? count - 1 : Math.min(hoverIndex, count - 1);
  const active = data[activeIndex];
  const cpu = active?.cpu_percent ?? selectedNode?.latestCpu;
  const memory = active?.memory_percent ?? selectedNode?.latestMemory;

  return (
    <section className="chart-panel" aria-label="Biểu đồ tài nguyên">
      <div className="chart-panel-header">
        <div className="chart-node-identity">
          <strong>{selectedNode?.hostname ?? "Tài nguyên máy chủ"}</strong>
          <small>
            {selectedNode?.ip_address ?? "Chọn một host để bắt đầu"}
          </small>
        </div>
        <div className="chart-legends">
          <button
            className={`legend-pill ${showCpu ? "" : "series-hidden"}`}
            aria-pressed={showCpu}
            onClick={() => setShowCpu(!showCpu)}
          >
            <span className="legend-color-dot cpu" />
            CPU <b>{cpu?.toFixed(1) ?? "—"}%</b>
          </button>
          <button
            className={`legend-pill ${showMem ? "" : "series-hidden"}`}
            aria-pressed={showMem}
            onClick={() => setShowMem(!showMem)}
          >
            <span className="legend-color-dot memory" />
            RAM <b>{memory?.toFixed(1) ?? "—"}%</b>
          </button>
        </div>
      </div>
      {!selectedNode ? (
        <div className="panel-empty">
          <Server size={28} />
          <p>Chọn máy chủ trên bản đồ hoặc trong danh sách.</p>
        </div>
      ) : isLoading ? (
        <div className="chart-loading" role="status">
          <Activity size={20} />
          <span>Đang tải lịch sử tài nguyên…</span>
        </div>
      ) : error ? (
        <div className="panel-empty">
          <p role="alert">{error}</p>
          <button className="btn btn-outline" onClick={onRetry}>
            Thử lại
          </button>
        </div>
      ) : !count ? (
        <div className="panel-empty">
          <Activity size={28} />
          <strong>Chưa có mẫu telemetry</strong>
          <p>Biểu đồ sẽ xuất hiện khi Agent gửi dữ liệu.</p>
        </div>
      ) : (
        <div className="chart-canvas-container">
          {hoverIndex !== null && active && (
            <div className="chart-tooltip-box">
              <span>{clock(active.observed_at)}</span>
              <span>CPU {active.cpu_percent.toFixed(1)}%</span>
              <span>RAM {active.memory_percent.toFixed(1)}%</span>
            </div>
          )}
          <svg
            className="telemetry-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            tabIndex={0}
            aria-label={`${count} mẫu tài nguyên của ${selectedNode.hostname}. CPU ${cpu?.toFixed(1)}%, RAM ${memory?.toFixed(1)}%. Dùng phím mũi tên để xem từng mẫu.`}
            onMouseLeave={() => setHoverIndex(null)}
            onKeyDown={(event) => {
              if (
                ["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(
                  event.key,
                )
              )
                event.preventDefault();
              if (event.key === "ArrowLeft")
                setHoverIndex((index) => Math.max(0, (index ?? count) - 1));
              if (event.key === "ArrowRight")
                setHoverIndex((index) =>
                  Math.min(count - 1, (index ?? -1) + 1),
                );
              if (event.key === "Home") setHoverIndex(0);
              if (event.key === "End") setHoverIndex(count - 1);
              if (event.key === "Escape") setHoverIndex(null);
            }}
            onBlur={() => setHoverIndex(null)}
          >
            <title>CPU và RAM theo thời gian</title>
            <defs>
              <linearGradient id={`${id}-cpu`} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="var(--chart-cpu)"
                  stopOpacity=".16"
                />
                <stop
                  offset="100%"
                  stopColor="var(--chart-cpu)"
                  stopOpacity="0"
                />
              </linearGradient>
              <linearGradient id={`${id}-mem`} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="var(--chart-memory)"
                  stopOpacity=".10"
                />
                <stop
                  offset="100%"
                  stopColor="var(--chart-memory)"
                  stopOpacity="0"
                />
              </linearGradient>
            </defs>
            {[0, 25, 50, 75, 100].map((value) => (
              <g key={value}>
                <line
                  x1={pad.left}
                  x2={width - pad.right}
                  y1={y(value)}
                  y2={y(value)}
                  stroke="var(--border-subtle)"
                  strokeDasharray="3 4"
                />
                <text
                  x={pad.left - 10}
                  y={y(value) + 4}
                  textAnchor="end"
                  className="chart-axis"
                >
                  {value}%
                </text>
              </g>
            ))}
            {showMem && (
              <>
                <path d={area("memory_percent")} fill={`url(#${id}-mem)`} />
                <polyline
                  points={points("memory_percent")}
                  fill="none"
                  stroke="var(--chart-memory)"
                  strokeWidth="2.5"
                  strokeDasharray="6 3"
                  strokeLinejoin="round"
                />
              </>
            )}
            {showCpu && (
              <>
                <path d={area("cpu_percent")} fill={`url(#${id}-cpu)`} />
                <polyline
                  points={points("cpu_percent")}
                  fill="none"
                  stroke="var(--chart-cpu)"
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                />
              </>
            )}
            {[...new Set([0, Math.floor((count - 1) / 2), count - 1])].map(
              (index) => (
                <text
                  key={index}
                  x={x(index)}
                  y={height - 7}
                  className="chart-axis"
                  textAnchor={
                    index === 0
                      ? "start"
                      : index === count - 1
                        ? "end"
                        : "middle"
                  }
                >
                  {clock(data[index].observed_at)}
                </text>
              ),
            )}
            {data.map((sample, index) => (
              <rect
                key={`${sample.observed_at}-${index}`}
                x={index ? (x(index - 1) + x(index)) / 2 : pad.left}
                y={pad.top}
                width={Math.max(
                  1,
                  (index < count - 1
                    ? (x(index) + x(index + 1)) / 2
                    : width - pad.right) -
                    (index ? (x(index - 1) + x(index)) / 2 : pad.left),
                )}
                height={graphHeight}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(index)}
                onClick={() => setHoverIndex(index)}
              />
            ))}
            {hoverIndex !== null && active && (
              <g pointerEvents="none">
                <line
                  x1={x(activeIndex)}
                  x2={x(activeIndex)}
                  y1={pad.top}
                  y2={y(0)}
                  stroke="var(--brand-indigo)"
                  strokeDasharray="3 3"
                />
                {showCpu && (
                  <circle
                    cx={x(activeIndex)}
                    cy={y(active.cpu_percent)}
                    r="4"
                    fill="var(--chart-cpu)"
                    stroke="white"
                    strokeWidth="2"
                  />
                )}
                {showMem && (
                  <circle
                    cx={x(activeIndex)}
                    cy={y(active.memory_percent)}
                    r="4"
                    fill="var(--chart-memory)"
                    stroke="white"
                    strokeWidth="2"
                  />
                )}
              </g>
            )}
          </svg>
        </div>
      )}
      <div className="chart-foot">
        <span>
          <span className={`health-dot ${count ? "ok" : "unenrolled"}`} />{" "}
          {count} mẫu · CPU / RAM (%)
        </span>
        <button
          className="text-button"
          aria-expanded={showTable}
          onClick={() => setShowTable(!showTable)}
          disabled={!count}
        >
          {showTable ? "Ẩn dữ liệu" : "Xem dữ liệu"}
          <ArrowUpRight size={13} />
        </button>
      </div>
      {showTable && count > 0 && (
        <div className="chart-data-table table-scroll">
          <table className="host-table">
            <caption className="sr-only">
              Giá trị tài nguyên theo thời gian
            </caption>
            <thead>
              <tr>
                <th>Thời gian</th>
                <th>CPU (%)</th>
                <th>RAM (%)</th>
              </tr>
            </thead>
            <tbody>
              {data.map((sample, index) => (
                <tr key={index}>
                  <td>{clock(sample.observed_at)}</td>
                  <td>{sample.cpu_percent.toFixed(1)}</td>
                  <td>{sample.memory_percent.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
