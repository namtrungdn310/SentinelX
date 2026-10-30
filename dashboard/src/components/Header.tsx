import { useRef, useEffect } from "react";
import {
  Search,
  ChevronRight,
  Radio,
  RefreshCw,
  FlaskConical,
} from "lucide-react";
import type { Project } from "../types";
interface HeaderProps {
  projects: Project[];
  selectedProject: string | null;
  onSelectProject: (id: string | null) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onSearchSubmit?: () => void;
  isConnected: boolean;
  latencyMs: number | null;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}
export function Header(props: HeaderProps) {
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        event.key === "/" &&
        !["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName) &&
        !target.isContentEditable
      ) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <header className="topbar">
      <div className="workspace-crumb">
        <span className="workspace-avatar">S</span>
        <span>Dự án</span>
        <ChevronRight size={14} />
        <select
          aria-label="Dự án"
          value={props.selectedProject ?? ""}
          onChange={(e) => props.onSelectProject(e.target.value || null)}
        >
          <option value="">Tất cả dự án</option>
          {props.projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>
      <div className="global-search">
        <Search size={16} />
        <input
          ref={searchRef}
          aria-label="Tìm máy chủ"
          aria-description="Tìm hostname hoặc IP. Nhấn Enter để mở danh sách kết quả."
          placeholder="Tìm hostname hoặc địa chỉ IP…"
          value={props.searchQuery}
          onChange={(e) => props.onSearchChange(e.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") props.onSearchSubmit?.(); }}
        />
        <kbd>/</kbd>
      </div>
      <div className="topbar-actions">
        <span
          className={`connection-state ${!props.isDemoMode && props.isConnected ? "connected" : ""}`}
          role="status"
        >
          <Radio size={14} />
          <span>
          {props.isDemoMode
            ? "Dữ liệu mô phỏng"
            : props.isConnected
              ? "Đã kết nối"
              : "Đang kết nối lại"}
          {props.isDemoMode && <small>Chưa kết nối Controller</small>}
          {!props.isDemoMode &&
            props.isConnected &&
            props.latencyMs !== null && <small>{props.latencyMs} ms</small>}
          </span>
        </span>
        <button
          className="icon-button"
          aria-label="Làm mới dữ liệu"
          onClick={props.onRefresh}
          disabled={props.isRefreshing}
        >
          <RefreshCw size={17} className={props.isRefreshing ? "spin" : ""} />
        </button>
        <button
          className={`icon-button source-action ${props.isDemoMode ? "is-active" : ""}`}
          aria-label={
            props.isDemoMode ? "Kết nối Controller" : "Bật dữ liệu mẫu"
          }
          title={props.isDemoMode ? "Kết nối Controller" : "Bật dữ liệu mẫu"}
          onClick={props.onToggleDemoMode}
          disabled={props.isRefreshing}
        >
          <FlaskConical size={17} />
          {props.isDemoMode && <span>Kết nối</span>}
        </button>
      </div>
    </header>
  );
}
