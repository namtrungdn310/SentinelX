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
        {/* Brand & Breadcrumbs (Datadog style) */}
        <div className="brand-section">
          <div className="brand-logo-badge">
            <Shield size={16} strokeWidth={2.5} />
          </div>
          <div className="brand-title">
            <span>SentinelX</span>
            <span className="slash">/</span>
            <span className="brand-breadcrumb">Host Map & Fleet</span>
          </div>
        </div>

        {/* Universal Search Filter (Datadog tag filter) */}
        <div className="header-search">
          <Search size={13} className="header-search-icon" />
          <input
            type="text"
            className="header-search-input"
            placeholder="Lọc host, IP hoặc tag (vd: host:edge, 10.0.1, online)..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <span className="header-search-badge">/</span>
        </div>

        {/* Right Actions */}
        <div className="header-actions">
          {/* Timeframe Picker */}
          <div className="time-picker" title="Khoảng thời gian giám sát telemetry">
            {['LIVE 5m', '15m', '1h', '4h'].map((t) => (
              <button
                key={t}
                className={`time-picker-btn ${timeRange === t ? 'active' : ''}`}
                onClick={() => onTimeRangeChange(t)}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Project Selector */}
          <div className="project-selector">
            <select
              className="project-select-dropdown"
              value={selectedProject || ''}
              onChange={(e) => onSelectProject(e.target.value ? e.target.value : null)}
            >
              <option value="">Tất cả Projects ({projects.length})</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Live WebSocket Status */}
          <div
            className={`live-badge ${isConnected || isDemoMode ? 'online' : 'offline'}`}
            title={
              isConnected
                ? 'Kết nối WebSocket realtime Controller'
                : isDemoMode
                ? 'Đang giả lập luồng telemetry Datadog'
                : 'Mất kết nối WebSocket tới Controller'
            }
          >
            <span className={`pulse-dot ${isConnected || isDemoMode ? 'pulse' : ''}`} />
            <span>{isConnected ? 'LIVE' : isDemoMode ? 'SIMULATED' : 'RECONNECTING'}</span>
            {(isConnected || isDemoMode) && (
              <span className="font-mono" style={{ fontSize: '10px', opacity: 0.8 }}>
                {isConnected ? latencyMs ?? 0 : 8}ms
              </span>
            )}
          </div>

          {/* Refresh Action */}
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '5px 8px' }}
            onClick={onRefresh}
            title="Đồng bộ lại dữ liệu"
          >
            <RefreshCw size={13} className={isRefreshing ? 'pulse' : ''} />
          </button>

          {/* Demo Mode Toggle */}
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
            <span>{isDemoMode ? 'Demo Data' : 'Live Core'}</span>
          </button>

          {/* Add / Enroll Host Button */}
          <button
            className="btn btn-primary btn-sm"
            onClick={onOpenAddNode}
            style={{ fontWeight: 600 }}
          >
            <Plus size={13} strokeWidth={2.5} />
            <span>Enroll Host</span>
          </button>
        </div>
      </div>
    </header>
  );
};
