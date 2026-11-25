import { useRef, useEffect } from "react";
import { Search, Radio, RefreshCw } from "lucide-react";
import type { Project } from "../types";

interface HeaderProps {
  projects?: Project[];
  selectedProject?: string | null;
  onSelectProject?: (id: string | null) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onSearchSubmit?: () => void;
  isConnected: boolean;
  latencyMs: number | null;
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
      <div className="global-search">
        <Search size={16} />
        <input
          ref={searchRef}
          aria-label={props.selectedProject ? "Tìm máy chủ" : "Tìm dự án"}
          aria-description={
            props.selectedProject
              ? "Tìm tên máy chủ hoặc IP. Nhấn Enter để mở danh sách kết quả."
              : "Tìm kiếm dự án theo tên hoặc mô tả."
          }
          placeholder={
            props.selectedProject
              ? "Tìm tên máy chủ hoặc địa chỉ IP…"
              : "Tìm kiếm dự án…"
          }
          value={props.searchQuery}
          onChange={(e) => props.onSearchChange(e.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && props.selectedProject) {
              props.onSearchSubmit?.();
            }
          }}
        />
        <kbd>/</kbd>
      </div>

      {props.selectedProject && (
        <div className="topbar-actions">
          <span
            className={`connection-state ${
              props.isConnected ? "connected" : "reconnecting"
            }`}
            role="status"
          >
            <Radio
              size={14}
              className={!props.isConnected ? "spin-animation" : ""}
            />
            <span>
              {props.isConnected ? "Đã kết nối" : "Đang kết nối lại"}
              {props.isConnected && props.latencyMs !== null && (
                <small>{props.latencyMs} ms</small>
              )}
            </span>
          </span>

          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={props.onRefresh}
            disabled={props.isRefreshing}
            aria-label="Làm mới dữ liệu từ Controller"
          >
            <RefreshCw
              size={13}
              className={props.isRefreshing ? "spin-animation" : ""}
            />
            <span>{props.isRefreshing ? "Đang kết nối..." : "Làm mới"}</span>
          </button>
        </div>
      )}
    </header>
  );
}
