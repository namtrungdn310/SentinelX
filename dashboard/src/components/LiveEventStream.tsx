import React, { useState } from 'react';
import { Terminal, Pause, Play, Search } from 'lucide-react';
import type { RealtimeMessage } from '../types';

interface LiveEventStreamProps {
  events: RealtimeMessage[];
  isConnected: boolean;
}

export const LiveEventStream: React.FC<LiveEventStreamProps> = ({ events, isConnected }) => {
  const [isPaused, setIsPaused] = useState(false);
  const [logFilter, setLogFilter] = useState('');

  const filteredEvents = events.filter((evt) => {
    if (!logFilter) return true;
    const q = logFilter.toLowerCase();
    return (
      evt.event.toLowerCase().includes(q) ||
      (evt.data.node_id && String(evt.data.node_id).toLowerCase().includes(q)) ||
      JSON.stringify(evt.data).toLowerCase().includes(q)
    );
  });

  return (
    <div className="log-panel">
      {/* Tiêu Đề Bảng Nhật Ký */}
      <div className="log-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal size={14} style={{ color: '#a5b4fc' }} />
          <span
            className="facet-status-indicator"
            style={{ backgroundColor: isConnected ? 'var(--status-ok)' : 'var(--status-muted)' }}
            title={isConnected ? 'Đang kết nối' : 'Mất kết nối'}
          />
          <span className="text-title" style={{ fontSize: '13px', color: '#f8fafc' }}>
            Nhật Ký Sự Kiện Trực Tiếp (Tail -f)
          </span>
          <span className="facet-badge-count" style={{ background: '#0f172a', color: '#94a3b8', borderColor: '#334155' }}>
            {filteredEvents.length} sự kiện
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Nút Tạm Dừng / Tiếp Tục */}
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '2px 8px', fontSize: '11px', height: '24px', background: '#334155', color: '#f8fafc', borderColor: '#475569' }}
            onClick={() => setIsPaused(!isPaused)}
            title={isPaused ? 'Tiếp tục nhận luồng sự kiện' : 'Tạm dừng cuộn'}
          >
            {isPaused ? <Play size={11} /> : <Pause size={11} />}
            <span>{isPaused ? 'Tiếp tục' : 'Tạm dừng'}</span>
          </button>
        </div>
      </div>

      {/* Ô Lọc Nhật Ký */}
      <div style={{ padding: '5px 12px', background: '#0a0f1d', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: '7px' }}>
        <Search size={11} style={{ color: '#64748b' }} />
        <input
          type="text"
          placeholder="Lọc sự kiện (vd: metric, node, warn, health)..."
          value={logFilter}
          onChange={(e) => setLogFilter(e.target.value)}
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#f8fafc',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            width: '100%',
          }}
        />
      </div>

      {/* Dòng Chảy Sự Kiện (Console Output) */}
      <div className="log-stream-body">
        {filteredEvents.length === 0 ? (
          <div style={{ padding: '30px 0', textAlign: 'center', color: '#64748b' }}>
            Đang chờ gói tin telemetry WebSocket từ Controller...
          </div>
        ) : (
          filteredEvents.slice(0, 30).map((evt, idx) => {
            const time = new Date(evt.timestamp).toLocaleTimeString();
            const nodeId = evt.data.node_id ? String(evt.data.node_id).substring(0, 10) : 'hệ-thống';
            const sampleCount = evt.data.samples && Array.isArray(evt.data.samples) ? evt.data.samples.length : 1;
            const isMetric = evt.event === 'metric_update';

            const levelLabel = isMetric ? 'CHỈ SỐ' : evt.event.toUpperCase();

            return (
              <div key={idx} className="log-row">
                <span className="log-timestamp">{time}</span>
                <span className={`log-level ${isMetric ? 'metric' : 'info'}`}>
                  {levelLabel}
                </span>
                <span className="log-host">[{nodeId}]</span>
                <span className="log-msg">
                  {isMetric
                    ? `Đã nhận gói: ${sampleCount} mẫu đo (cpu/ram/disk/mạng)`
                    : JSON.stringify(evt.data).substring(0, 80)}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
