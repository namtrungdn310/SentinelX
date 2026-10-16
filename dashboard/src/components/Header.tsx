import React from 'react';
import { Shield, Plus, RefreshCw, Sparkles, Search } from 'lucide-react';
import type { Project } from '../types';

interface HeaderProps {
  projects: Project[];
  selectedProject: string | null;
  onSelectProject: (id: string | null) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
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
  searchQuery,
  onSearchChange,
  timeRange,
  onTimeRangeChange,
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
        {/* Logo & Điều hướng phân cấp (Breadcrumbs) */}
        <div className="brand-section">
          <div className="brand-logo-badge">
            <Shield size={16} strokeWidth={2.5} />
          </div>
          <div className="brand-title">
            <span>SentinelX</span>
            <span className="slash">/</span>
            <span className="brand-breadcrumb">Bản Đồ &amp; Cụm Máy Chủ</span>
          </div>
        </div>

        {/* Thanh Tìm Kiếm Lọc Nhanh (Search Filter) */}
        <div className="header-search">
          <Search size={13} className="header-search-icon" />
          <input
            type="text"
            className="header-search-input"
            placeholder="Lọc host, IP hoặc thẻ (vd: host:edge, 10.0.1, hoạt động)..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <span className="header-search-badge">/</span>
        </div>

        {/* Các Thao Tác Phía Phải */}
        <div className="header-actions">
          {/* Hộp Chọn Mốc Thời Gian */}
          <div className="time-picker" title="Khoảng thời gian giám sát telemetry">
            {['Trực tiếp 5p', '15 phút', '1 giờ', '4 giờ'].map((t) => (
              <button
                key={t}
                className={`time-picker-btn ${timeRange === t ? 'active' : ''}`}
                onClick={() => onTimeRangeChange(t)}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Lựa Chọn Dự Án */}
          <div className="project-selector">
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

          {/* Trạng Thái Kết Nối WebSocket */}
          <div
            className={`live-badge ${isConnected || isDemoMode ? 'online' : 'offline'}`}
            title={
              isConnected
                ? 'Đã kết nối luồng WebSocket thời gian thực tới Controller'
                : isDemoMode
                ? 'Đang giả lập luồng telemetry tự động'
                : 'Mất kết nối WebSocket tới Controller'
            }
          >
            <span className={`pulse-dot ${isConnected || isDemoMode ? 'pulse' : ''}`} />
            <span>{isConnected ? 'TRỰC TIẾP' : isDemoMode ? 'DỮ LIỆU MẪU' : 'ĐANG KẾT NỐI LẠI'}</span>
            {(isConnected || isDemoMode) && (
              <span className="font-mono" style={{ fontSize: '10px', opacity: 0.8 }}>
                {isConnected ? latencyMs ?? 0 : 8}ms
              </span>
            )}
          </div>

          {/* Làm Mới Dữ Liệu */}
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '6px 9px' }}
            onClick={onRefresh}
            title="Làm mới lại dữ liệu từ máy chủ"
          >
            <RefreshCw size={13} className={isRefreshing ? 'pulse' : ''} />
          </button>

          {/* Nút Chuyển Chế Độ Mẫu */}
          <button
            className={`demo-mode-pill ${isDemoMode ? 'active' : ''}`}
            onClick={onToggleDemoMode}
            title={
              isDemoMode
                ? 'Dữ liệu mẫu đang bật. Bấm để chuyển sang kết nối Controller thực tế.'
                : 'Bấm để nạp dữ liệu mẫu trải nghiệm đầy đủ giao diện.'
            }
          >
            <Sparkles size={12} />
            <span>{isDemoMode ? 'Bản Mẫu' : 'Thực Tế'}</span>
          </button>

          {/* Nút Đăng Ký Thêm Máy Chủ */}
          <button
            className="btn btn-primary btn-sm"
            onClick={onOpenAddNode}
            style={{ fontWeight: 700 }}
          >
            <Plus size={13} strokeWidth={2.5} />
            <span>Thêm Máy Chủ</span>
          </button>
        </div>
      </div>
    </header>
  );
};
