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
      {/* Header */}
      <div className="log-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal size={14} style={{ color: 'var(--brand-purple)' }} />
          <span
            className="facet-status-indicator"
            style={{ backgroundColor: isConnected ? 'var(--status-ok)' : 'var(--status-muted)' }}
            title={isConnected ? 'Connected' : 'Disconnected'}
          />
          <span className="text-title" style={{ fontSize: '13px' }}>
            Live Event Stream (Tail -f)
          </span>
          <span className="facet-badge-count">{filteredEvents.length} events</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Pause / Resume Button */}
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '2px 6px', fontSize: '11px', height: '24px' }}
            onClick={() => setIsPaused(!isPaused)}
            title={isPaused ? 'Tiếp tục dòng sự kiện' : 'Tạm dừng cuộn'}
          >
            {isPaused ? <Play size={11} /> : <Pause size={11} />}
            <span>{isPaused ? 'Resume' : 'Pause'}</span>
          </button>
        </div>
      </div>

      {/* Mini Filter */}
      <div style={{ padding: '4px 10px', background: 'var(--bg-canvas)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Search size={11} style={{ color: 'var(--text-muted)' }} />
        <input
          type="text"
          placeholder="Filter event tail (e.g. metric, node, warn)..."
          value={logFilter}
          onChange={(e) => setLogFilter(e.target.value)}
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            width: '100%',
          }}
        />
      </div>

      {/* Terminal Console Output */}
      <div className="log-stream-body">
        {filteredEvents.length === 0 ? (
          <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
            Đang chờ gói tin telemetry WebSocket từ Controller...
          </div>
        ) : (
          filteredEvents.slice(0, 30).map((evt, idx) => {
            const time = new Date(evt.timestamp).toLocaleTimeString();
            const nodeId = evt.data.node_id ? String(evt.data.node_id).substring(0, 10) : 'sys';
            const sampleCount = evt.data.samples && Array.isArray(evt.data.samples) ? evt.data.samples.length : 1;
            const isMetric = evt.event === 'metric_update';

            return (
              <div key={idx} className="log-row">
                <span className="log-timestamp">{time}</span>
                <span className={`log-level ${isMetric ? 'metric' : 'info'}`}>
                  {isMetric ? 'METRIC' : evt.event.toUpperCase()}
                </span>
                <span className="log-host">[{nodeId}]</span>
                <span className="log-msg">
                  {isMetric
                    ? `Ingested batch: ${sampleCount} samples (cpu/mem/disk/net)`
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
