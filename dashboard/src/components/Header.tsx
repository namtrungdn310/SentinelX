import { Shield, Plus, RefreshCw } from 'lucide-react';
import type { Project } from '../types';

interface HeaderProps {
  projects: Project[];
  selectedProject: string | null;
  onSelectProject: (id: string | null) => void;
  isConnected: boolean;
  latencyMs: number | null;
  onOpenAddNode: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  projects,
  selectedProject,
  onSelectProject,
  isConnected,
  latencyMs,
  onOpenAddNode,
  onRefresh,
  isRefreshing,
}) => {
  return (
    <header className="header-bar">
      <div className="header-inner">
        {/* Brand */}
        <div className="brand-section">
          <div className="brand-logo-badge">
            <Shield size={18} strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="brand-title">SentinelX</h1>
            <p className="brand-subtitle">Quản trị & Giám sát Hạ tầng Linux</p>
          </div>
        </div>

        {/* Center / Right Actions */}
        <div className="header-actions">
          {/* Project Picker */}
          <div className="project-selector">
            <span className="text-label" style={{ fontSize: '10px' }}>Dự án:</span>
            <select
              className="project-select-dropdown"
              value={selectedProject || ''}
              onChange={(e) => onSelectProject(e.target.value ? e.target.value : null)}
            >
              <option value="">Tất cả dự án ({projects.length})</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* WebSocket Pulse Status */}
          <div
            className={`live-badge ${isConnected ? 'online' : 'offline'}`}
            title={isConnected ? 'Kết nối WebSocket realtime hoạt động' : 'Mất kết nối WebSocket'}
          >
            <span className={`pulse-dot ${isConnected ? 'pulse' : ''}`} />
            <span>{isConnected ? 'Realtime Live' : 'Đang kết nối lại'}</span>
            {isConnected && latencyMs !== null && (
              <span className="font-mono" style={{ fontSize: '11px', opacity: 0.8 }}>
                ({latencyMs}ms)
              </span>
            )}
          </div>

          {/* Refresh Button */}
          <button
            className="btn btn-outline btn-sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Làm mới dữ liệu từ Controller"
          >
            <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
            <span>Làm mới</span>
          </button>

          {/* Add Node Button */}
          <button className="btn btn-primary btn-sm" onClick={onOpenAddNode}>
            <Plus size={15} />
            <span>Thêm Node mới</span>
          </button>
        </div>
      </div>
    </header>
  );
};
