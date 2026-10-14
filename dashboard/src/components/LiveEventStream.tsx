import { Radio, Bell } from 'lucide-react';
import type { RealtimeMessage } from '../types';

interface LiveEventStreamProps {
  events: RealtimeMessage[];
  isConnected: boolean;
}

export const LiveEventStream: React.FC<LiveEventStreamProps> = ({ events, isConnected }) => {
  return (
    <div className="event-stream-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Radio size={16} style={{ color: isConnected ? 'var(--status-online)' : 'var(--text-muted)' }} />
          <h3 className="text-title" style={{ fontSize: '14px' }}>Dòng Sự Kiện Trực Tiếp</h3>
        </div>
        <span className="text-label" style={{ fontSize: '10px' }}>
          {events.length} sự kiện
        </span>
      </div>

      <p className="text-body" style={{ fontSize: '11px', marginTop: '4px' }}>
        Nhật ký gói tin WebSocket Controller phát thanh thời gian thực
      </p>

      <div className="event-list">
        {events.length === 0 ? (
          <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Bell size={20} style={{ margin: '0 auto 6px', opacity: 0.4 }} />
            <span style={{ fontSize: '12px' }}>Đang chờ gói tin realtime từ Agent...</span>
          </div>
        ) : (
          events.slice(0, 15).map((evt, idx) => {
            const time = new Date(evt.timestamp).toLocaleTimeString();
            const nodeId = evt.data.node_id ? String(evt.data.node_id).substring(0, 8) : 'sys';
            const sampleCount = evt.data.samples && Array.isArray(evt.data.samples) ? evt.data.samples.length : 1;

            return (
              <div key={idx} className="event-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: evt.event === 'metric_update' ? 'var(--status-online)' : 'var(--primary)',
                    }}
                  />
                  <span className="font-mono" style={{ fontWeight: 600, fontSize: '11px' }}>
                    {evt.event}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    node:{nodeId} (+{sampleCount})
                  </span>
                </div>
                <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                  {time}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
