import React, { useState } from 'react';
import { Server, LayoutGrid, List } from 'lucide-react';
import type { Node } from '../types';

interface NodeMatrixProps {
  nodes: Node[];
  selectedNodeId: string | null;
  onSelectNode: (node: Node) => void;
  isLoading: boolean;
  onOpenDetail?: (node: Node) => void;
}

type ViewMode = 'grid' | 'table';

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Chưa kết nối';
  const diffSec = Math.floor((Date.now() - new Date(dateString).getTime()) / 1000);
  if (diffSec < 5) return 'Vừa xong';
  if (diffSec < 60) return `${diffSec}s trước`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m trước`;
  return `${Math.floor(diffSec / 3600)}h trước`;
}

function getNodeRole(hostname: string): { label: string; type: 'lb' | 'worker' | 'db' | 'edge' } {
  const h = hostname.toLowerCase();
  if (h.includes('ingress') || h.includes('lb') || h.includes('gateway')) return { label: 'role:ingress-lb', type: 'lb' };
  if (h.includes('db') || h.includes('pg') || h.includes('primary')) return { label: 'role:database-pg', type: 'db' };
  if (h.includes('api')) return { label: 'role:api-service', type: 'edge' };
  return { label: 'role:worker-node', type: 'worker' };
}

export const NodeMatrix: React.FC<NodeMatrixProps> = ({
  nodes,
  selectedNodeId,
  onSelectNode,
  isLoading,
  onOpenDetail,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

  if (isLoading) {
    return (
      <div className="matrix-card">
        <div className="matrix-card-header">
          <span className="text-title">Host Fleet Map & Health Matrix</span>
        </div>
        <div className="host-grid">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="host-tile skeleton" style={{ height: '90px' }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="matrix-card">
      <div className="matrix-card-header">
        <div className="matrix-card-title-group">
          <Server size={15} style={{ color: 'var(--brand-purple)' }} />
          <h2 className="text-title" style={{ fontSize: '13px' }}>
            Infrastructure Host Fleet
          </h2>
          <span className="facet-badge-count">{nodes.length} hosts</span>
        </div>

        <div className="matrix-controls">
          {/* View Mode Switcher */}
          <div className="view-mode-toggle">
            <button
              className={`view-mode-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="Xem dạng Host Map Grid"
            >
              <LayoutGrid size={13} />
            </button>
            <button
              className={`view-mode-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
              title="Xem dạng SRE Data Table"
            >
              <List size={13} />
            </button>
          </div>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Không tìm thấy máy chủ nào phù hợp với bộ lọc hiện tại.
        </div>
      ) : viewMode === 'grid' ? (
        /* Host Map Grid Mode (Datadog style) */
        <div className="host-grid">
          {nodes.map((node) => {
            const isSelected = node.id === selectedNodeId;
            const role = getNodeRole(node.hostname);
            const cpu = node.latestCpu ?? 0;
            const mem = node.latestMemory ?? 0;
            const cpuClass = cpu > 80 ? 'crit' : cpu > 60 ? 'warn' : 'ok';
            const memClass = mem > 85 ? 'crit' : mem > 70 ? 'warn' : 'purple';

            return (
              <div
                key={node.id}
                className={`host-tile ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectNode(node)}
                onDoubleClick={() => onOpenDetail?.(node)}
                title="Nhấn để xem telemetry, nhấp đúp để mở chi tiết node"
              >
                <div className="host-tile-header">
                  <div className="host-identity">
                    <span className={`facet-status-indicator ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`} />
                    <span className="host-name" title={node.hostname}>{node.hostname}</span>
                  </div>
                  <span className={`status-badge ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`}>
                    {node.status === 'online' ? 'OK' : node.status}
                  </span>
                </div>

                {/* Host Tags */}
                <div className="host-tags-row">
                  <span className="host-ip">{node.ip_address}</span>
                  <span className="host-tag role">{role.label}</span>
                  <span className="host-tag env">env:prod</span>
                </div>

                {/* Micro Metric Gauges */}
                {node.status === 'online' ? (
                  <div className="host-metric-row">
                    <div className="metric-bar-item">
                      <span className="metric-bar-label">CPU</span>
                      <span className="metric-bar-value" style={{ color: cpu > 80 ? 'var(--status-crit)' : 'inherit' }}>
                        {cpu.toFixed(1)}%
                      </span>
                    </div>
                    <div className="micro-meter">
                      <div className={`micro-meter-fill ${cpuClass}`} style={{ width: `${Math.min(100, cpu)}%` }} />
                    </div>

                    <div className="metric-bar-item" style={{ marginTop: '3px' }}>
                      <span className="metric-bar-label">MEM</span>
                      <span className="metric-bar-value">{mem.toFixed(1)}%</span>
                    </div>
                    <div className="micro-meter">
                      <div className={`micro-meter-fill ${memClass}`} style={{ width: `${Math.min(100, mem)}%` }} />
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '6px 0' }}>
                    Chưa có số liệu telemetry tức thời
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        /* Host List Table Mode (Datadog SRE Table) */
        <div className="table-container">
          <table className="datadog-table">
            <thead>
              <tr>
                <th style={{ width: '90px' }}>Status</th>
                <th>Host & IP</th>
                <th>Service Role</th>
                <th style={{ width: '160px' }}>CPU Utilization</th>
                <th style={{ width: '160px' }}>Memory</th>
                <th>Network I/O</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => {
                const isSelected = node.id === selectedNodeId;
                const role = getNodeRole(node.hostname);
                const cpu = node.latestCpu ?? 0;
                const mem = node.latestMemory ?? 0;
                const cpuClass = cpu > 80 ? 'crit' : cpu > 60 ? 'warn' : 'ok';
                const memClass = mem > 85 ? 'crit' : mem > 70 ? 'warn' : 'purple';

                return (
                  <tr
                    key={node.id}
                    className={isSelected ? 'selected' : ''}
                    onClick={() => onSelectNode(node)}
                    onDoubleClick={() => onOpenDetail?.(node)}
                    title="Nhấn để xem telemetry, nhấp đúp để mở chi tiết node"
                  >
                    <td>
                      <span className={`status-badge ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`}>
                        {node.status === 'online' ? 'OK' : node.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                        {node.hostname}
                      </div>
                      <div className="host-ip">{node.ip_address}</div>
                    </td>
                    <td>
                      <span className="host-tag role">{role.label}</span>
                    </td>
                    <td>
                      {node.status === 'online' ? (
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                            <span className="font-mono">{cpu.toFixed(1)}%</span>
                          </div>
                          <div className="micro-meter">
                            <div className={`micro-meter-fill ${cpuClass}`} style={{ width: `${Math.min(100, cpu)}%` }} />
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>-</span>
                      )}
                    </td>
                    <td>
                      {node.status === 'online' ? (
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                            <span className="font-mono">{mem.toFixed(1)}%</span>
                          </div>
                          <div className="micro-meter">
                            <div className={`micro-meter-fill ${memClass}`} style={{ width: `${Math.min(100, mem)}%` }} />
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>-</span>
                      )}
                    </td>
                    <td>
                      <div className="font-mono" style={{ fontSize: '11px' }}>
                        ↓ {node.latestRxBytes ? `${(node.latestRxBytes / 1000000).toFixed(1)} MB/s` : '0 B/s'}
                      </div>
                    </td>
                    <td>
                      <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {formatRelativeTime(node.last_seen)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
