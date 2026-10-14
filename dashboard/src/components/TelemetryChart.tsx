import { Activity } from 'lucide-react';
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
  if (!selectedNode) {
    return (
      <div className="telemetry-chart-card">
        <div className="chart-header">
          <h3 className="text-title">Đồ Thị Tài Nguyên Thời Gian Thực</h3>
        </div>
        <div
          style={{
            height: '220px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            backgroundColor: 'var(--bg-subtle)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <Activity size={28} style={{ opacity: 0.5, marginBottom: '8px' }} />
          <p className="text-body">Chọn một máy chủ trong Ma Trận để xem đồ thị CPU & RAM trực tiếp</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="telemetry-chart-card">
        <div className="chart-header">
          <h3 className="text-title">Đang tải số liệu node: {selectedNode.hostname}</h3>
        </div>
        <div className="skeleton skeleton-box" style={{ height: '220px' }} />
      </div>
    );
  }

  // Reverse samples if ordered desc, so oldest is on the left, newest on the right
  const displaySamples = [...samples].reverse().slice(-30);

  // Chart Dimensions
  const width = 600;
  const height = 180;
  const padding = { top: 20, right: 20, bottom: 25, left: 35 };
  const graphWidth = width - padding.left - padding.right;
  const graphHeight = height - padding.top - padding.bottom;

  const pointsCount = displaySamples.length;

  const getX = (index: number) => {
    if (pointsCount <= 1) return padding.left + graphWidth / 2;
    return padding.left + (index / (pointsCount - 1)) * graphWidth;
  };

  const getY = (val: number) => {
    const clamped = Math.max(0, Math.min(100, val));
    return padding.top + graphHeight - (clamped / 100) * graphHeight;
  };

  // Generate SVG path for CPU and Memory
  const cpuPoints = displaySamples.map((s, i) => `${getX(i)},${getY(s.cpu_percent)}`).join(' ');
  const memPoints = displaySamples.map((s, i) => `${getX(i)},${getY(s.memory_percent)}`).join(' ');

  const cpuArea = displaySamples.length > 0
    ? `M ${getX(0)},${getY(displaySamples[0].cpu_percent)} ` +
      displaySamples.map((s, i) => `L ${getX(i)},${getY(s.cpu_percent)}`).join(' ') +
      ` L ${getX(displaySamples.length - 1)},${padding.top + graphHeight} L ${getX(0)},${padding.top + graphHeight} Z`
    : '';

  const latestSample = displaySamples[displaySamples.length - 1];

  return (
    <div className="telemetry-chart-card">
      <div className="chart-header">
        <div>
          <h3 className="text-title">
            Đồ Thị Trực Tiếp: <span style={{ color: 'var(--primary)' }}>{selectedNode.hostname}</span>
          </h3>
          <p className="text-body font-mono" style={{ fontSize: '11px' }}>
            IP: {selectedNode.ip_address} • Cập nhật mỗi giây qua WebSocket
          </p>
        </div>

        <div className="chart-legend">
          <div className="legend-item">
            <span className="legend-color-dot" style={{ backgroundColor: '#059669' }} />
            <span>CPU: <strong>{latestSample ? latestSample.cpu_percent : 0}%</strong></span>
          </div>
          <div className="legend-item">
            <span className="legend-color-dot" style={{ backgroundColor: '#4f46e5' }} />
            <span>RAM: <strong>{latestSample ? latestSample.memory_percent : 0}%</strong></span>
          </div>
        </div>
      </div>

      <div className="svg-chart-container">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (0%, 25%, 50%, 75%, 100%) */}
          {[0, 25, 50, 75, 100].map((val) => {
            const y = getY(val);
            return (
              <g key={val}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="var(--border-subtle)"
                  strokeDasharray={val === 0 || val === 100 ? '0' : '3 3'}
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="var(--text-muted)"
                  fontFamily="var(--font-mono)"
                >
                  {val}%
                </text>
              </g>
            );
          })}

          {/* CPU Area Fill */}
          {cpuArea && <path d={cpuArea} fill="url(#cpuGradient)" />}

          {/* RAM Line (Indigo) */}
          {memPoints && (
            <polyline
              fill="none"
              stroke="#4f46e5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={memPoints}
            />
          )}

          {/* CPU Line (Emerald) */}
          {cpuPoints && (
            <polyline
              fill="none"
              stroke="#059669"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={cpuPoints}
            />
          )}

          {/* Latest Point Indicator */}
          {latestSample && (
            <g>
              <circle
                cx={getX(displaySamples.length - 1)}
                cy={getY(latestSample.cpu_percent)}
                r="4"
                fill="#059669"
                stroke="#ffffff"
                strokeWidth="2"
              />
              <circle
                cx={getX(displaySamples.length - 1)}
                cy={getY(latestSample.memory_percent)}
                r="4"
                fill="#4f46e5"
                stroke="#ffffff"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>
      </div>
    </div>
  );
};
