import React, { useState } from 'react';
import { Activity, Server } from 'lucide-react';
import type { MetricSample, Node } from '../types';

interface TelemetryChartProps {
  selectedNode: Node | null;
  samples: MetricSample[];
  isLoading: boolean;
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  selectedNode,
  samples,
  isLoading,
}) => {
  const [showCpu, setShowCpu] = useState(true);
  const [showMem, setShowMem] = useState(true);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!selectedNode) {
    return (
      <div className="chart-panel">
        <div className="chart-panel-header">
          <span className="text-title" style={{ fontSize: '13px' }}>Đồ Thị Phân Tích Chuỗi Thời Gian</span>
        </div>
        <div
          style={{
            height: '240px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            gap: '8px',
          }}
        >
          <Server size={28} style={{ opacity: 0.3 }} />
          <p className="text-body">Chọn một máy chủ trong cụm để kiểm tra đồ thị thời gian thực</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="chart-panel">
        <div className="chart-panel-header">
          <span className="text-title" style={{ fontSize: '13px' }}>Đang nạp telemetry: {selectedNode.hostname}</span>
        </div>
        <div className="skeleton" style={{ height: '240px', margin: '12px' }} />
      </div>
    );
  }

  const displaySamples = [...samples].reverse().slice(-30);
  const count = displaySamples.length;

  const width = 640;
  const height = 200;
  const pad = { top: 20, right: 20, bottom: 25, left: 35 };
  const graphW = width - pad.left - pad.right;
  const graphH = height - pad.top - pad.bottom;

  const getX = (i: number) => {
    if (count <= 1) return pad.left + graphW / 2;
    return pad.left + (i / (count - 1)) * graphW;
  };

  const getY = (val: number) => {
    const clamped = Math.max(0, Math.min(100, val));
    return pad.top + graphH - (clamped / 100) * graphH;
  };

  const cpuLine = displaySamples.map((s, i) => `${getX(i)},${getY(s.cpu_percent)}`).join(' ');
  const memLine = displaySamples.map((s, i) => `${getX(i)},${getY(s.memory_percent)}`).join(' ');

  const cpuArea = count > 0
    ? `M ${getX(0)},${getY(displaySamples[0].cpu_percent)} ` +
      displaySamples.map((s, i) => `L ${getX(i)},${getY(s.cpu_percent)}`).join(' ') +
      ` L ${getX(count - 1)},${pad.top + graphH} L ${getX(0)},${pad.top + graphH} Z`
    : '';

  const memArea = count > 0
    ? `M ${getX(0)},${getY(displaySamples[0].memory_percent)} ` +
      displaySamples.map((s, i) => `L ${getX(i)},${getY(s.memory_percent)}`).join(' ') +
      ` L ${getX(count - 1)},${pad.top + graphH} L ${getX(0)},${pad.top + graphH} Z`
    : '';

  const latestSample = displaySamples[displaySamples.length - 1];
  const hoveredSample = hoverIndex !== null && displaySamples[hoverIndex] ? displaySamples[hoverIndex] : null;

  const activeCpu = hoveredSample ? hoveredSample.cpu_percent : latestSample?.cpu_percent ?? selectedNode.latestCpu ?? 0;
  const activeMem = hoveredSample ? hoveredSample.memory_percent : latestSample?.memory_percent ?? selectedNode.latestMemory ?? 0;

  return (
    <div className="chart-panel">
      {/* Tiêu Đề Đồ Thị */}
      <div className="chart-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={14} style={{ color: 'var(--brand-cyan)' }} />
          <span className="text-title" style={{ fontSize: '13px' }}>
            {selectedNode.hostname}
          </span>
          <span className="host-ip">{selectedNode.ip_address}</span>
          <span className="host-tag role">chu kỳ 1s</span>
        </div>

        {/* Nút Bật/Tắt Đường Đo */}
        <div className="chart-legends">
          <div
            className="legend-pill"
            onClick={() => setShowCpu(!showCpu)}
            style={{ opacity: showCpu ? 1 : 0.4 }}
          >
            <span className="legend-color-dot" style={{ backgroundColor: 'var(--brand-cyan)' }} />
            <span>CPU: {activeCpu.toFixed(1)}%</span>
          </div>

          <div
            className="legend-pill"
            onClick={() => setShowMem(!showMem)}
            style={{ opacity: showMem ? 1 : 0.4 }}
          >
            <span className="legend-color-dot" style={{ backgroundColor: 'var(--brand-indigo)' }} />
            <span>RAM: {activeMem.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* SVG Biểu Đồ Thời Gian Thực */}
      <div className="chart-canvas-container">
        {hoveredSample && (
          <div className="chart-tooltip-box">
            <span style={{ color: 'var(--text-muted)' }}>
              {new Date(hoveredSample.observed_at).toLocaleTimeString()}
            </span>
            <span style={{ color: '#38bdf8' }}>CPU: {hoveredSample.cpu_percent.toFixed(1)}%</span>
            <span style={{ color: '#a5b4fc' }}>RAM: {hoveredSample.memory_percent.toFixed(1)}%</span>
          </div>
        )}

        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="warmCpuGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0284c7" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#0284c7" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="warmMemGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Đường Kẻ Lưới Mức Độ (25%, 50%, 75%, 100%) */}
          {[0, 25, 50, 75, 100].map((val) => {
            const y = getY(val);
            return (
              <g key={val}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={pad.left + graphW}
                  y2={y}
                  stroke="var(--border-subtle)"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
                <text
                  x={pad.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fill="var(--text-muted)"
                  fontSize="9"
                  fontFamily="var(--font-mono)"
                >
                  {val}%
                </text>
              </g>
            );
          })}

          {/* Vùng & Đường Bộ Nhớ RAM */}
          {showMem && count > 0 && (
            <>
              <path d={memArea} fill="url(#warmMemGrad)" />
              <polyline
                points={memLine}
                fill="none"
                stroke="#6366f1"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {/* Vùng & Đường CPU */}
          {showCpu && count > 0 && (
            <>
              <path d={cpuArea} fill="url(#warmCpuGrad)" />
              <polyline
                points={cpuLine}
                fill="none"
                stroke="#0284c7"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {/* Vùng Cảm Ứng Di Chuột (Crosshair Sensor) */}
          {displaySamples.map((_s, i) => {
            const x = getX(i);
            return (
              <rect
                key={i}
                x={x - (graphW / count) / 2}
                y={pad.top}
                width={graphW / count}
                height={graphH}
                fill="transparent"
                style={{ cursor: 'crosshair' }}
                onMouseEnter={() => setHoverIndex(i)}
              />
            );
          })}

          {/* Đường Kẻ Thước Ngắm Khi Di Chuột */}
          {hoverIndex !== null && (
            <line
              x1={getX(hoverIndex)}
              y1={pad.top}
              x2={getX(hoverIndex)}
              y2={pad.top + graphH}
              stroke="var(--brand-indigo)"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
          )}
        </svg>
      </div>
    </div>
  );
};
