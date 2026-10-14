import { useState } from 'react';
import { Server, Clock, ChevronRight } from 'lucide-react';
import type { Node } from '../types';

interface NodeMatrixProps {
  nodes: Node[];
  selectedNodeId: string | null;
  onSelectNode: (node: Node) => void;
  isLoading: boolean;
}

type FilterType = 'all' | 'online' | 'offline' | 'unenrolled';

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Chưa kết nối';
  const diffSec = Math.floor((Date.now() - new Date(dateString).getTime()) / 1000);
  if (diffSec < 5) return 'Vừa xong';
  if (diffSec < 60) return `${diffSec}s trước`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
  return `${Math.floor(diffSec / 3600)} giờ trước`;
}

export const NodeMatrix: React.FC<NodeMatrixProps> = ({
  nodes,
  selectedNodeId,
  onSelectNode,
  isLoading,
}) => {
  const [filter, setFilter] = useState<FilterType>('all');

  const onlineCount = nodes.filter((n) => n.status === 'online').length;
  const offlineCount = nodes.filter((n) => n.status === 'offline').length;
  const unenrolledCount = nodes.filter((n) => n.status === 'unenrolled').length;

  const filteredNodes = nodes.filter((n) => {
    if (filter === 'online') return n.status === 'online';
    if (filter === 'offline') return n.status === 'offline';
    if (filter === 'unenrolled') return n.status === 'unenrolled';
    return true;
  });

  return (
    <section className="node-matrix-section">
      {/* Header and Filter Tabs */}
      <div className="section-header">
        <div>
          <h2 className="text-title">Ma Trận Máy Chủ (Node Health Matrix)</h2>
          <p className="text-body" style={{ fontSize: '12px' }}>
            Giám sát trạng thái hoạt động và tiêu hao tài nguyên tức thời
          </p>
        </div>

        {/* Filter Controls */}
        <div className="filter-tabs">
          <button
            className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Tất cả ({nodes.length})
          </button>
          <button
            className={`filter-tab ${filter === 'online' ? 'active' : ''}`}
            onClick={() => setFilter('online')}
          >
            Trực tuyến ({onlineCount})
          </button>
          <button
            className={`filter-tab ${filter === 'unenrolled' ? 'active' : ''}`}
            onClick={() => setFilter('unenrolled')}
          >
            Chưa kích hoạt ({unenrolledCount})
          </button>
          {offlineCount > 0 && (
            <button
              className={`filter-tab ${filter === 'offline' ? 'active' : ''}`}
              onClick={() => setFilter('offline')}
            >
              Mất kết nối ({offlineCount})
            </button>
          )}
        </div>
      </div>

      {/* Grid Content */}
      {isLoading ? (
        <div className="nodes-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} className="node-card skeleton-box skeleton" style={{ height: '140px' }} />
          ))}
        </div>
      ) : filteredNodes.length === 0 ? (
        <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Server size={32} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
          <p className="text-body">Không có máy chủ nào phù hợp với bộ lọc.</p>
        </div>
      ) : (
        <div className="nodes-grid">
          {filteredNodes.map((node) => {
            const isSelected = selectedNodeId === node.id;
            const cpu = node.latestCpu !== undefined ? node.latestCpu : 0;
            const mem = node.latestMemory !== undefined ? node.latestMemory : 0;

            return (
              <div
                key={node.id}
                className={`node-card ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectNode(node)}
              >
                {/* Card Title & Status Badge */}
                <div className="node-card-header">
                  <div>
                    <h3 className="node-card-title">{node.hostname}</h3>
                    <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {node.ip_address}
                    </span>
                  </div>

                  <span className={`status-badge ${node.status}`}>
                    {node.status === 'online' && 'Trực tuyến'}
                    {node.status === 'unenrolled' && 'Chưa đăng ký'}
                    {node.status === 'offline' && 'Mất kết nối'}
                    {node.status === 'degraded' && 'Quá tải'}
                  </span>
                </div>

                {/* Resource Meters */}
                {node.status === 'online' ? (
                  <div className="node-metrics-bars">
                    {/* CPU */}
                    <div className="metric-bar-item">
                      <div className="metric-bar-labels">
                        <span className="text-label" style={{ fontSize: '10px' }}>CPU</span>
                        <span className="font-mono" style={{ fontWeight: 600 }}>{cpu}%</span>
                      </div>
                      <div className="mini-meter" style={{ marginTop: 0 }}>
                        <div
                          className="mini-meter-fill"
                          style={{
                            width: `${cpu}%`,
                            backgroundColor: cpu > 80 ? 'var(--status-critical)' : cpu > 60 ? 'var(--status-warning)' : 'var(--status-online)',
                          }}
                        />
                      </div>
                    </div>

                    {/* RAM */}
                    <div className="metric-bar-item">
                      <div className="metric-bar-labels">
                        <span className="text-label" style={{ fontSize: '10px' }}>RAM</span>
                        <span className="font-mono" style={{ fontWeight: 600 }}>{mem}%</span>
                      </div>
                      <div className="mini-meter" style={{ marginTop: 0 }}>
                        <div
                          className="mini-meter-fill"
                          style={{
                            width: `${mem}%`,
                            backgroundColor: mem > 85 ? 'var(--status-critical)' : 'var(--primary)',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '8px 0', fontSize: '11px', color: 'var(--text-muted)' }}>
                    {node.status === 'unenrolled'
                      ? 'Cần cấp Token để Agent kết nối lần đầu'
                      : 'Không nhận được nhịp tim (heartbeat)'}
                  </div>
                )}

                {/* Footer Time & Arrow */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginTop: '12px',
                    paddingTop: '8px',
                    borderTop: '1px solid var(--border-subtle)',
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} />
                    {formatRelativeTime(node.last_seen)}
                  </span>
                  <ChevronRight size={14} style={{ color: isSelected ? 'var(--primary)' : 'inherit' }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
