import React from 'react';
import { Server, Cpu, HardDrive, ArrowDownUp, CheckCircle2, AlertTriangle } from 'lucide-react';
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
      <div className="kpi-strip">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="kpi-strip-card skeleton" style={{ height: '76px' }} />
        ))}
      </div>
    );
  }

  const onlineNodes = nodes.filter((n) => n.status === 'online');
  const totalNodes = nodes.length;

  const warnNodes = onlineNodes.filter((n) => (n.latestCpu ?? 0) > 75 || (n.latestMemory ?? 0) > 85);
  const okNodes = onlineNodes.filter((n) => (n.latestCpu ?? 0) <= 75 && (n.latestMemory ?? 0) <= 85);
  const offlineNodes = nodes.filter((n) => n.status === 'offline' || n.status === 'unenrolled');

  // Tính toán số liệu trung bình toàn cụm
  const activeMetrics = onlineNodes.filter((n) => n.latestCpu !== undefined);
  const avgCpu = activeMetrics.length
    ? Math.round((activeMetrics.reduce((acc, n) => acc + (n.latestCpu || 0), 0) / activeMetrics.length) * 10) / 10
    : 0;

  const avgMem = activeMetrics.length
    ? Math.round((activeMetrics.reduce((acc, n) => acc + (n.latestMemory || 0), 0) / activeMetrics.length) * 10) / 10
    : 0;

  const totalRx = nodes.reduce((acc, n) => acc + (n.latestRxBytes || 0), 0);
  const totalTx = nodes.reduce((acc, n) => acc + (n.latestTxBytes || 0), 0);

  const cpuStatusClass = avgCpu > 80 ? 'crit' : avgCpu > 60 ? 'warn' : 'ok';
  const memStatusClass = avgMem > 85 ? 'crit' : avgMem > 70 ? 'warn' : 'purple';

  return (
    <div className="kpi-strip">
      {/* 1. Trạng Thái Máy Chủ */}
      <div className="kpi-strip-card">
        <div className="kpi-strip-header">
          <span className="kpi-strip-title">Trạng Thái Máy Chủ</span>
          <Server size={14} style={{ color: 'var(--text-muted)' }} />
        </div>
        <div className="kpi-strip-value-row">
          <span className="kpi-strip-value">{onlineNodes.length}</span>
          <span className="kpi-strip-unit">/ {totalNodes} Máy Chủ Hoạt Động</span>
        </div>
        <div className="micro-meter" style={{ display: 'flex' }}>
          <div
            className="micro-meter-fill ok"
            style={{ width: `${totalNodes ? (okNodes.length / totalNodes) * 100 : 0}%` }}
          />
          <div
            className="micro-meter-fill warn"
            style={{ width: `${totalNodes ? (warnNodes.length / totalNodes) * 100 : 0}%` }}
          />
          <div
            className="micro-meter-fill crit"
            style={{ width: `${totalNodes ? (offlineNodes.length / totalNodes) * 100 : 0}%` }}
          />
        </div>
        <div className="kpi-strip-subtext">
          <span style={{ color: 'var(--status-ok)', display: 'flex', alignItems: 'center', gap: '3px' }}>
            <CheckCircle2 size={11} /> {okNodes.length} Bình thường
          </span>
          {warnNodes.length > 0 && (
            <span style={{ color: 'var(--status-warn)', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <AlertTriangle size={11} /> {warnNodes.length} Cảnh báo
            </span>
          )}
          {offlineNodes.length > 0 && (
            <span style={{ color: 'var(--text-muted)' }}>
              {offlineNodes.length} Chưa kết nối
            </span>
          )}
        </div>
      </div>

      {/* 2. Mức Tiêu Thụ CPU */}
      <div className="kpi-strip-card">
        <div className="kpi-strip-header">
          <span className="kpi-strip-title">Tải CPU Trung Bình</span>
          <Cpu size={14} style={{ color: 'var(--text-muted)' }} />
        </div>
        <div className="kpi-strip-value-row">
          <span className="kpi-strip-value">{avgCpu.toFixed(1)}%</span>
          <span className="kpi-strip-unit">Toàn Cụm</span>
        </div>
        <div className="micro-meter">
          <div
            className={`micro-meter-fill ${cpuStatusClass}`}
            style={{ width: `${Math.min(100, avgCpu)}%` }}
          />
        </div>
        <div className="kpi-strip-subtext">
          <span>Ngưỡng an toàn: &lt; 75.0%</span>
          <span className="font-mono">{activeMetrics.length} máy chủ đo đạc</span>
        </div>
      </div>

      {/* 3. Mức Chiếm Dụng Bộ Nhớ RAM */}
      <div className="kpi-strip-card">
        <div className="kpi-strip-header">
          <span className="kpi-strip-title">Bộ Nhớ RAM Chiếm Dụng</span>
          <HardDrive size={14} style={{ color: 'var(--text-muted)' }} />
        </div>
        <div className="kpi-strip-value-row">
          <span className="kpi-strip-value">{avgMem.toFixed(1)}%</span>
          <span className="kpi-strip-unit">Đã Phân Bổ</span>
        </div>
        <div className="micro-meter">
          <div
            className={`micro-meter-fill ${memStatusClass}`}
            style={{ width: `${Math.min(100, avgMem)}%` }}
          />
        </div>
        <div className="kpi-strip-subtext">
          <span>Khả dụng: {(100 - avgMem).toFixed(1)}%</span>
          <span className="font-mono">{onlineNodes.length} trực tuyến</span>
        </div>
      </div>

      {/* 4. Lưu Lượng Băng Thông Mạng */}
      <div className="kpi-strip-card">
        <div className="kpi-strip-header">
          <span className="kpi-strip-title">Băng Thông Mạng (I/O)</span>
          <ArrowDownUp size={14} style={{ color: 'var(--brand-cyan)' }} />
        </div>
        <div className="kpi-strip-value-row">
          <span className="kpi-strip-value">{formatBytes(totalRx + totalTx)}</span>
          <span className="kpi-strip-unit">Tổng Lưu Lượng</span>
        </div>
        <div className="micro-meter">
          <div className="micro-meter-fill cyan" style={{ width: '65%' }} />
        </div>
        <div className="kpi-strip-subtext">
          <span className="font-mono">↓ Nhận: {formatBytes(totalRx)}</span>
          <span className="font-mono">↑ Gửi: {formatBytes(totalTx)}</span>
        </div>
      </div>
    </div>
  );
};
