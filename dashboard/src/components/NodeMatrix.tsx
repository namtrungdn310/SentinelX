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
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
  return `${Math.floor(diffSec / 3600)} giờ trước`;
}

function getNodeRole(hostname: string): { label: string; type: 'lb' | 'worker' | 'db' | 'edge' } {
  const h = hostname.toLowerCase();
  if (h.includes('ingress') || h.includes('lb') || h.includes('gateway')) return { label: 'vai-trò:cổng-vào-lb', type: 'lb' };
  if (h.includes('db') || h.includes('pg') || h.includes('primary')) return { label: 'vai-trò:csdl-postgres', type: 'db' };
  if (h.includes('api')) return { label: 'vai-trò:dịch-vụ-api', type: 'edge' };
  return { label: 'vai-trò:máy-chủ-worker', type: 'worker' };
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
          <span className="text-title">Bản Đồ Hạ Tầng &amp; Ma Trận Máy Chủ</span>
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
          <Server size={15} style={{ color: 'var(--brand-indigo)' }} />
          <h2 className="text-title" style={{ fontSize: '13px' }}>
            Hạ Tầng Cụm Máy Chủ (Host Fleet)
          </h2>
          <span className="facet-badge-count">{nodes.length} máy chủ</span>
        </div>

        <div className="matrix-controls">
          {/* Chuyển Đổi Dạng Xem (Lưới Ô vs Bảng SRE) */}
          <div className="view-mode-toggle">
            <button
              className={`view-mode-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="Xem dạng Lưới ô máy chủ (Host Map)"
            >
              <LayoutGrid size={13} />
            </button>
            <button
              className={`view-mode-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
              title="Xem dạng Bảng chi tiết (SRE Table)"
            >
              <List size={13} />
            </button>
          </div>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Không tìm thấy máy chủ nào phù hợp với bộ lọc hiện tại.
        </div>
      ) : viewMode === 'grid' ? (
        /* Dạng Lưới Ô Máy Chủ (Host Map Grid) */
        <div className="host-grid">
          {nodes.map((node) => {
            const isSelected = node.id === selectedNodeId;
            const role = getNodeRole(node.hostname);
            const cpu = node.latestCpu ?? 0;
            const mem = node.latestMemory ?? 0;
            const cpuClass = cpu > 80 ? 'crit' : cpu > 60 ? 'warn' : 'ok';
            const memClass = mem > 85 ? 'crit' : mem > 70 ? 'warn' : 'purple';

            const statusLabel =
              node.status === 'online'
                ? 'HOẠT ĐỘNG'
                : node.status === 'degraded'
                ? 'CẢNH BÁO'
                : node.status === 'offline'
                ? 'MẤT KẾT NỐI'
                : 'CHƯA ĐĂNG KÝ';

            return (
              <div
                key={node.id}
                className={`host-tile ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectNode(node)}
                onDoubleClick={() => onOpenDetail?.(node)}
                title="Bấm để xem đồ thị telemetry, nhấp đúp để mở thông số chi tiết"
              >
                <div className="host-tile-header">
                  <div className="host-identity">
                    <span className={`facet-status-indicator ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`} />
                    <span className="host-name" title={node.hostname}>{node.hostname}</span>
                  </div>
                  <span className={`status-badge ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`}>
                    {statusLabel}
                  </span>
                </div>

                {/* Thẻ Phân Loại */}
                <div className="host-tags-row">
                  <span className="host-ip">{node.ip_address}</span>
                  <span className="host-tag role">{role.label}</span>
                  <span className="host-tag env">mt:production</span>
                </div>

                {/* Vạch Đo Chỉ Số Tức Thời */}
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
                      <span className="metric-bar-label">RAM</span>
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
        /* Dạng Bảng Dữ Liệu SRE (Detailed SRE Table) */
        <div className="table-container">
          <table className="datadog-table">
            <thead>
              <tr>
                <th style={{ width: '110px' }}>Trạng Thái</th>
                <th>Máy Chủ &amp; Địa Chỉ IP</th>
                <th>Vai Trò Hạ Tầng</th>
                <th style={{ width: '160px' }}>Mức Tải CPU</th>
                <th style={{ width: '160px' }}>Bộ Nhớ RAM</th>
                <th>Lưu Lượng I/O</th>
                <th>Lần Cuối Báo Cáo</th>
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

                const statusLabel =
                  node.status === 'online'
                    ? 'HOẠT ĐỘNG'
                    : node.status === 'degraded'
                    ? 'CẢNH BÁO'
                    : node.status === 'offline'
                    ? 'MẤT KẾT NỐI'
                    : 'CHƯA ĐĂNG KÝ';

                return (
                  <tr
                    key={node.id}
                    className={isSelected ? 'selected' : ''}
                    onClick={() => onSelectNode(node)}
                    onDoubleClick={() => onOpenDetail?.(node)}
                    title="Bấm để xem telemetry, nhấp đúp để mở chi tiết máy chủ"
                  >
                    <td>
                      <span className={`status-badge ${node.status === 'online' ? 'ok' : node.status === 'degraded' ? 'warn' : 'crit'}`}>
                        {statusLabel}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
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
