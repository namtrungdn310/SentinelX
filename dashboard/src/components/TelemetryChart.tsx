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
          <span className="text-title" style={{ fontSize: '13px' }}>Time-Series Telemetry Explorer</span>
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
          <p className="text-body">Chọn một máy chủ trong Fleet để kiểm tra đồ thị thời gian thực</p>
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

  // Reverse samples if needed, display up to 30 latest points
  const displaySamples = [...samples].reverse().slice(-30);
  const count = displaySamples.length;

  // Chart Dimensions
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

  // Generate SVG path for CPU and Memory
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

  // Current stats
  const latestSample = displaySamples[displaySamples.length - 1];
  const hoveredSample = hoverIndex !== null && displaySamples[hoverIndex] ? displaySamples[hoverIndex] : null;

  const activeCpu = hoveredSample ? hoveredSample.cpu_percent : latestSample?.cpu_percent ?? selectedNode.latestCpu ?? 0;
  const activeMem = hoveredSample ? hoveredSample.memory_percent : latestSample?.memory_percent ?? selectedNode.latestMemory ?? 0;

  return (
    <div className="chart-panel">
      {/* Datadog Chart Header */}
      <div className="chart-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={14} style={{ color: 'var(--brand-cyan)' }} />
          <span className="text-title" style={{ fontSize: '13px' }}>
            {selectedNode.hostname}
          </span>
          <span className="host-ip">{selectedNode.ip_address}</span>
          <span className="host-tag role">1s stream</span>
        </div>

        {/* Metric Toggles */}
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
            <span className="legend-color-dot" style={{ backgroundColor: 'var(--brand-purple)' }} />
            <span>MEM: {activeMem.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* Interactive SVG Chart */}
      <div className="chart-canvas-container">
        {hoveredSample && (
          <div className="chart-tooltip-box">
            <span style={{ color: 'var(--text-muted)' }}>
              {new Date(hoveredSample.observed_at).toLocaleTimeString()}
            </span>
            <span style={{ color: 'var(--brand-cyan)' }}>CPU: {hoveredSample.cpu_percent.toFixed(1)}%</span>
            <span style={{ color: 'var(--brand-purple)' }}>MEM: {hoveredSample.memory_percent.toFixed(1)}%</span>
          </div>
        )}

        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="ddCpuGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="ddMemGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (25%, 50%, 75%, 100%) */}
          {[0, 25, 50, 75, 100].map((val) => {
            const y = getY(val);
            return (
              <g key={val}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={pad.left + graphW}
                  y2={y}
                  stroke="#1c263b"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
                <text
                  x={pad.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fill="#475569"
                  fontSize="9"
                  fontFamily="var(--font-mono)"
                >
                  {val}%
                </text>
              </g>
            );
          })}

          {/* Memory Area & Line */}
          {showMem && count > 0 && (
            <>
              <path d={memArea} fill="url(#ddMemGrad)" />
              <polyline
                points={memLine}
                fill="none"
                stroke="#a855f7"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {/* CPU Area & Line */}
          {showCpu && count > 0 && (
            <>
              <path d={cpuArea} fill="url(#ddCpuGrad)" />
              <polyline
                points={cpuLine}
                fill="none"
                stroke="#06b6d4"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {/* Hover Crosshair Detection */}
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

          {/* Active Hover Crosshair Line */}
          {hoverIndex !== null && (
            <line
              x1={getX(hoverIndex)}
              y1={pad.top}
              x2={getX(hoverIndex)}
              y2={pad.top + graphH}
              stroke="#38bdf8"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
          )}
        </svg>
      </div>
    </div>
  );
};
