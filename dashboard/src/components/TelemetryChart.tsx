import { useEffect, useRef, useState } from "react";
import { mergeSamples, timeTicks } from "../telemetry";
import { formatPercent } from "../presentation";
import { Activity, ChevronRight, Server } from "lucide-react";
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
  const containerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipWidth, setTooltipWidth] = useState(260);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const [showCpu, setShowCpu] = useState(true);
  const [showMem, setShowMem] = useState(true);
  const [activeTime, setActiveTime] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);
  const data = mergeSamples([], samples);
  const count = data.length;
  const height = width < 600 ? 240 : 300;
  const pad = { top: 22, right: 16, bottom: 32, left: 52 };
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
  const activeIndex = activeTime === null ? count - 1 : data.findIndex((sample) => sample.observed_at === activeTime);
  const hoverIndex = activeTime === null || activeIndex < 0 ? null : activeIndex;
  const setHoverIndex = (index: number | null) => setActiveTime(index === null ? null : data[index]?.observed_at ?? null);
  const active = data[activeIndex];
  const latest = data.at(-1);
  const cpu = latest?.cpu_percent ?? selectedNode?.latestCpu;
  const memory = latest?.memory_percent ?? selectedNode?.latestMemory;
  const tooltipVisible = hoverIndex !== null && Boolean(active);
  useEffect(() => {
    const element = tooltipRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setTooltipWidth(entry.borderBoxSize[0]?.inlineSize ?? entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, [tooltipVisible]);
  const tooltipLeft = hoverIndex === null ? 8 : Math.max(8, Math.min(width - tooltipWidth - 8,
    x(hoverIndex) + 14 + tooltipWidth <= width - 8 ? x(hoverIndex) + 14 : x(hoverIndex) - tooltipWidth - 14));

  return (
    <section ref={containerRef} className="chart-panel" aria-label="Biểu đồ tài nguyên">
      <div className="chart-panel-header">
        <span className="chart-reading-label">Giá trị mới nhất{latest && ` · ${clock(latest.observed_at)}`}</span>
        <div className="chart-legends">
          <button
            className={`legend-pill ${showCpu ? "" : "series-hidden"}`}
            aria-pressed={showCpu}
            onClick={() => setShowCpu(!showCpu)}
          >
            <span className="legend-color-dot cpu" />
            CPU <b>{formatPercent(cpu)}</b>
          </button>
          <button
            className={`legend-pill ${showMem ? "" : "series-hidden"}`}
            aria-pressed={showMem}
            onClick={() => setShowMem(!showMem)}
          >
            <span className="legend-color-dot memory" />
            RAM <b>{formatPercent(memory)}</b>
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
            <div ref={tooltipRef} className="chart-tooltip-box" style={{ left: tooltipLeft }}>
              <time dateTime={active.observed_at}>{clock(active.observed_at)}</time>
              {showCpu && <span>CPU <b>{active.cpu_percent.toFixed(1)}%</b></span>}
              {showMem && <span>RAM <b>{active.memory_percent.toFixed(1)}%</b></span>}
            </div>
          )}
          <svg
            className="telemetry-svg"
            viewBox={`0 0 ${width} ${height}`}
            style={{ height }}
            role="img"
            tabIndex={0}
            aria-label={`${count} mẫu tài nguyên của ${selectedNode.hostname}. CPU ${formatPercent(cpu)}, RAM ${formatPercent(memory)} mới nhất. Dùng phím mũi tên để xem từng mẫu.`}
            onMouseLeave={() => setHoverIndex(null)}
            onKeyDown={(event) => {
              if (
                ["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(
                  event.key,
                )
              )
                event.preventDefault();
              if (event.key === "ArrowLeft")
                setHoverIndex(Math.max(0, (hoverIndex ?? count) - 1));
              if (event.key === "ArrowRight")
                setHoverIndex(Math.min(count - 1, (hoverIndex ?? -1) + 1));
              if (event.key === "Home") setHoverIndex(0);
              if (event.key === "End") setHoverIndex(count - 1);
              if (event.key === "Escape") setHoverIndex(null);
            }}
            onBlur={() => setHoverIndex(null)}
          >
            <title>CPU và RAM theo thời gian</title>
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
                <polyline
                  points={points("cpu_percent")}
                  fill="none"
                  stroke="var(--chart-cpu)"
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                />
              </>
            )}
            {timeTicks(firstTime, firstTime + duration, graphWidth).map((time, index, ticks) => (
              <text key={time} x={duration ? pad.left + (time - firstTime) / duration * graphWidth : x(0)}
                y={height - 7} className="chart-axis" textAnchor={ticks.length === 1 ? "middle" : index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}>
                {clock(new Date(time).toISOString())}
              </text>
            ))}
            {count === 1 && <g>
              {showCpu && <circle cx={x(0)} cy={y(data[0].cpu_percent)} r={4} fill="var(--chart-cpu)" />}
              {showMem && <circle cx={x(0)} cy={y(data[0].memory_percent)} r={4} fill="var(--chart-memory)" />}
            </g>}
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
          <span className="sr-only" role="status">
            {hoverIndex !== null && active ? `Đang xem ${clock(active.observed_at)}.${showCpu ? ` CPU ${formatPercent(active.cpu_percent)}.` : ""}${showMem ? ` RAM ${formatPercent(active.memory_percent)}.` : ""}` : ""}
          </span>
        </div>
      )}
      <div className="chart-foot">
        <span>
          {count} mẫu · CPU / RAM (%) {count > 0 && `· Mẫu mới nhất ${clock(data[count - 1].observed_at)}`}
        </span>
        <button
          className="text-button"
          aria-expanded={showTable}
          onClick={() => setShowTable(!showTable)}
          disabled={!count}
        >
          {showTable ? "Ẩn dữ liệu" : "Xem dữ liệu"}
          <ChevronRight size={13} />
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
