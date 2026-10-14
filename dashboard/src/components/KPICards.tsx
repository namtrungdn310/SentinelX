import { Server, Cpu, HardDrive, ArrowUpRight } from 'lucide-react';
import type { Node } from '../types';

interface KPICardsProps {
  nodes: Node[];
  isLoading: boolean;
}

function formatBytes(bytes: number | undefined): string {
  if (!bytes || bytes === 0) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export const KPICards: React.FC<KPICardsProps> = ({ nodes, isLoading }) => {
  if (isLoading) {
    return (
      <div className="kpi-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="kpi-card skeleton-box skeleton" />
        ))}
      </div>
    );
  }

  const onlineNodes = nodes.filter((n) => n.status === 'online');
  const totalNodes = nodes.length;

  // Calculate average CPU and RAM from online nodes having metrics
  const activeMetrics = onlineNodes.filter((n) => n.latestCpu !== undefined);
  const avgCpu = activeMetrics.length
    ? Math.round(activeMetrics.reduce((acc, n) => acc + (n.latestCpu || 0), 0) / activeMetrics.length)
    : 0;

  const avgMem = activeMetrics.length
    ? Math.round(activeMetrics.reduce((acc, n) => acc + (n.latestMemory || 0), 0) / activeMetrics.length)
    : 0;

  const totalRx = nodes.reduce((acc, n) => acc + (n.latestRxBytes || 0), 0);
  const totalTx = nodes.reduce((acc, n) => acc + (n.latestTxBytes || 0), 0);

  return (
    <div className="kpi-grid">
      {/* 1. Monitored Nodes */}
      <div className="kpi-card">
        <div className="kpi-header">
          <span className="text-label">Máy chủ Giám sát</span>
          <div
            className="kpi-icon-container"
            style={{ backgroundColor: '#eef2ff', color: '#4f46e5' }}
          >
            <Server size={18} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{onlineNodes.length}</span>
          <span className="kpi-subtext">/ {totalNodes} node đang hoạt động</span>
        </div>
        <div className="mini-meter">
          <div
            className="mini-meter-fill"
            style={{
              width: `${totalNodes > 0 ? (onlineNodes.length / totalNodes) * 100 : 0}%`,
              backgroundColor: '#059669',
            }}
          />
        </div>
      </div>

      {/* 2. Avg CPU */}
      <div className="kpi-card">
        <div className="kpi-header">
          <span className="text-label">CPU Trung bình</span>
          <div
            className="kpi-icon-container"
            style={{ backgroundColor: '#ecfdf5', color: '#059669' }}
          >
            <Cpu size={18} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{avgCpu}%</span>
          <span className="kpi-subtext">{activeMetrics.length} node có số liệu</span>
        </div>
        <div className="mini-meter">
          <div
            className="mini-meter-fill"
            style={{
              width: `${Math.min(100, avgCpu)}%`,
              backgroundColor: avgCpu > 80 ? '#e11d48' : avgCpu > 60 ? '#d97706' : '#059669',
            }}
          />
        </div>
      </div>

      {/* 3. Avg Memory */}
      <div className="kpi-card">
        <div className="kpi-header">
          <span className="text-label">Bộ nhớ RAM</span>
          <div
            className="kpi-icon-container"
            style={{ backgroundColor: '#fffbeb', color: '#d97706' }}
          >
            <HardDrive size={18} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{avgMem}%</span>
          <span className="kpi-subtext">Mức tải toàn hệ thống</span>
        </div>
        <div className="mini-meter">
          <div
            className="mini-meter-fill"
            style={{
              width: `${Math.min(100, avgMem)}%`,
              backgroundColor: avgMem > 85 ? '#e11d48' : avgMem > 70 ? '#d97706' : '#4f46e5',
            }}
          />
        </div>
      </div>

      {/* 4. Network Throughput */}
      <div className="kpi-card">
        <div className="kpi-header">
          <span className="text-label">Lưu lượng Mạng</span>
          <div
            className="kpi-icon-container"
            style={{ backgroundColor: '#f1f5f9', color: '#475569' }}
          >
            <ArrowUpRight size={18} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value" style={{ fontSize: '20px' }}>
            {formatBytes(totalRx + totalTx)}
          </span>
        </div>
        <div className="kpi-subtext font-mono" style={{ marginTop: '4px' }}>
          RX: {formatBytes(totalRx)} • TX: {formatBytes(totalTx)}
        </div>
      </div>
    </div>
  );
};
