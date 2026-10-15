import { Shield, Plus, RefreshCw, Sparkles } from 'lucide-react';
import type { Project } from '../types';

interface HeaderProps {
  projects: Project[];
  selectedProject: string | null;
  onSelectProject: (id: string | null) => void;
  isConnected: boolean;
  latencyMs: number | null;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
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
  isDemoMode,
  onToggleDemoMode,
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
          {/* Demo Mode Toggle */}
          <button
            className={`demo-mode-pill ${isDemoMode ? 'active' : ''}`}
            onClick={onToggleDemoMode}
            title={
              isDemoMode
                ? 'Đang bật dữ liệu mẫu. Bấm để chuyển sang kết nối Controller thực tế.'
                : 'Bấm để nạp dữ liệu mẫu trải nghiệm đầy đủ giao diện.'
            }
          >
            <Sparkles size={13} />
            <span>{isDemoMode ? 'Dữ liệu mẫu: BẬT' : 'Dữ liệu mẫu: TẮT'}</span>
          </button>

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
            className={`live-badge ${isConnected || isDemoMode ? 'online' : 'offline'}`}
            title={
              isConnected
                ? 'Kết nối WebSocket realtime hoạt động'
                : isDemoMode
                ? 'Đang mô phỏng luồng telemetry thời gian thực'
                : 'Mất kết nối WebSocket tới Controller'
            }
          >
            <span className={`pulse-dot ${isConnected || isDemoMode ? 'pulse' : ''}`} />
            <span>
              {isConnected
                ? 'Realtime Live'
                : isDemoMode
                ? 'Realtime (Mô phỏng)'
                : 'Đang kết nối lại'}
            </span>
            {(isConnected || isDemoMode) && (
              <span className="font-mono" style={{ fontSize: '11px', opacity: 0.8 }}>
                ({isConnected ? latencyMs ?? 0 : 8}ms)
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

