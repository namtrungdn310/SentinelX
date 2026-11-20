import { useEffect, useState, useMemo } from "react";
import {
  Activity,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Cpu,
  Globe,
  HardDrive,
  Leaf,
  Lock,
  RefreshCw,
  Server,
  ShieldCheck,
  Sliders,
  Zap,
} from "lucide-react";
import type {
  Project,
  Node,
  PresetProfileType,
  ProjectSettings,
} from "../types";
import { TELEMETRY_PRESETS, MOCK_PROJECT_SETTINGS } from "../mockData";
import { fetchProjectSettings, updateProjectSettings } from "../api";

interface Props {
  selectedProjectId: string | null;
  projects: Project[];
  nodes: Node[];
  isDemoMode: boolean;
  onProfileApplied?: (newProfile: PresetProfileType) => void;
}

export function SettingsView({
  selectedProjectId,
  projects,
  nodes,
  isDemoMode,
  onProfileApplied,
}: Props) {
  const effectiveProjectId = selectedProjectId || projects[0]?.id || "";
  const currentProject = projects.find((p) => p.id === effectiveProjectId);

  const [settings, setSettings] = useState<ProjectSettings>(() => {
    return (
      MOCK_PROJECT_SETTINGS[effectiveProjectId] || {
        project_id: effectiveProjectId,
        active_profile: "balanced",
        updated_at: new Date().toISOString(),
        updated_by: "system",
      }
    );
  });

  const [isLoading, setIsLoading] = useState(false);
  const [applyingProfile, setApplyingProfile] = useState<PresetProfileType | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load project settings when effectiveProjectId changes
  useEffect(() => {
    if (!effectiveProjectId) return;
    let isMounted = true;
    const timer = window.setTimeout(() => {
      setIsLoading(true);
      setError(null);

      void fetchProjectSettings(effectiveProjectId)
        .then((data) => {
          if (isMounted) setSettings(data);
        })
        .catch((err: unknown) => {
          if (isMounted) {
            setError(err instanceof Error ? err.message : "Lỗi tải cấu hình dự án");
          }
        })
        .finally(() => {
          if (isMounted) setIsLoading(false);
        });
    }, 0);

    return () => {
      isMounted = false;
      window.clearTimeout(timer);
    };
  }, [effectiveProjectId, isDemoMode]);

  const activePreset = useMemo(() => {
    return TELEMETRY_PRESETS[settings.active_profile] || TELEMETRY_PRESETS.balanced;
  }, [settings.active_profile]);

  const handleApplyPreset = async (profileId: PresetProfileType) => {
    if (profileId === settings.active_profile || applyingProfile) return;
    try {
      setApplyingProfile(profileId);
      setError(null);

      const targetPreset = TELEMETRY_PRESETS[profileId];
      const updated = await updateProjectSettings(
        effectiveProjectId,
        profileId,
        "admin@sentinelx.com"
      );

      setSettings(updated);
      onProfileApplied?.(profileId);
      setSuccessToast(`Đã áp dụng thành công hồ sơ [${targetPreset.name}] cho dự án!`);

      window.setTimeout(() => {
        setSuccessToast(null);
      }, 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi cập nhật cấu hình");
    } finally {
      setApplyingProfile(null);
    }
  };

  const projectNodes = useMemo(() => {
    return nodes.filter((n) => !effectiveProjectId || n.project_id === effectiveProjectId);
  }, [nodes, effectiveProjectId]);

  return (
    <div className="settings-container">
      {/* 1. Header Toolbar */}
      <div className="panel settings-header-card">
        <div className="settings-header-main">
          <div className="settings-header-icon-wrap">
            <Sliders size={22} className="text-accent" />
          </div>
          <div>
            <div className="settings-header-badge-row">
              <span className="badge-scope">
                <Server size={12} /> Cấu hình dự án: <strong>{currentProject?.name || "Tất cả dự án"}</strong>
              </span>
              <span className="badge-sync-live">
                <span className="pulse-indicator" /> Đồng bộ sâu (Live Deep Sync)
              </span>
            </div>
            <h2 className="settings-title">Thiết lập cấu hình thu thập &amp; phát hiện</h2>
            <p className="settings-subtitle">
              Tùy biến nhịp lấy mẫu và cửa sổ phát hiện theo các hồ sơ chuẩn hóa an toàn (Guardrailed Profiles).
              Hệ thống tự động đồng bộ xuống toàn bộ Agent máy chủ qua nhịp Heartbeat mà không cần khởi động lại dịch vụ.
            </p>
          </div>
        </div>

        <div className="settings-header-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              setIsLoading(true);
              void fetchProjectSettings(effectiveProjectId).then((data) => {
                setSettings(data);
                setIsLoading(false);
              });
            }}
            disabled={isLoading}
            title="Tải lại thông số cấu hình"
          >
            <RefreshCw size={14} className={isLoading ? "spin" : ""} />
            <span>Làm mới</span>
          </button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {successToast && (
        <div className="settings-alert-banner success" role="alert">
          <CheckCircle2 size={18} />
          <div className="alert-content">
            <strong>Cập nhật thành công</strong>
            <p>{successToast}</p>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="settings-alert-banner error" role="alert">
          <AlertTriangle size={18} />
          <div className="alert-content">
            <strong>Không thể lưu cấu hình</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* 2. Active Specs Banner (Read-only Observability) */}
      <div className="panel active-profile-banner">
        <div className="active-banner-top">
          <div className="active-banner-title-group">
            <span className="active-banner-eyebrow">HỒ SƠ HIỆN ĐANG HOẠT ĐỘNG TRÊN CỤM</span>
            <div className="active-profile-name-row">
              <h3 className="active-profile-name">{activePreset.name}</h3>
              <span className={`status-badge ${activePreset.badgeTone}`}>
                <Check size={12} /> Đang áp dụng ({projectNodes.length} máy chủ)
              </span>
            </div>
            <p className="active-profile-desc">{activePreset.description}</p>
          </div>

          <div className="active-banner-meta">
            <span className="meta-item">
              <Clock size={13} />
              Cập nhật lúc:{" "}
              <strong>
                {new Date(settings.updated_at).toLocaleTimeString("vi-VN")} ·{" "}
                {new Date(settings.updated_at).toLocaleDateString("vi-VN")}
              </strong>
            </span>
            <span className="meta-item">
              Người thực hiện: <strong>{settings.updated_by}</strong>
            </span>
          </div>
        </div>

        {/* 4 Quick Telemetry KPI Badges */}
        <div className="active-specs-grid">
          <div className="spec-metric-card">
            <div className="spec-metric-head">
              <Activity size={15} />
              <span>Nhịp đo tài nguyên</span>
            </div>
            <strong className="spec-metric-value font-mono">
              {activePreset.telemetry_interval_seconds.toFixed(1)}s
            </strong>
            <small>Lấy mẫu CPU, RAM, Disk qua psutil</small>
          </div>

          <div className="spec-metric-card">
            <div className="spec-metric-head">
              <Cpu size={15} />
              <span>Xác nhận quá tải</span>
            </div>
            <strong className="spec-metric-value font-mono">
              {activePreset.cpu_overload_window_seconds.toFixed(0)}s
            </strong>
            <small>{activePreset.consecutive_samples} mẫu liên tiếp chống false-alarm</small>
          </div>

          <div className="spec-metric-card">
            <div className="spec-metric-head">
              <Globe size={15} />
              <span>Cửa sổ trích xuất mạng</span>
            </div>
            <strong className="spec-metric-value font-mono">
              {activePreset.network_window_seconds}s
            </strong>
            <small>Bước trượt sliding window {activePreset.network_step_seconds}s</small>
          </div>

          <div className="spec-metric-card">
            <div className="spec-metric-head">
              <HardDrive size={15} />
              <span>Ngưỡng dò quét cổng</span>
            </div>
            <strong className="spec-metric-value font-mono">
              ≥ {activePreset.port_scan_threshold_ports} cổng
            </strong>
            <small>Chuẩn hóa trong cửa sổ mạng</small>
          </div>
        </div>
      </div>

      {/* 3. Preset Selection Cards (Bento 3 columns) */}
      <section className="settings-section">
        <div className="section-head">
          <h3 className="section-title">Hồ sơ cấu hình chuẩn hóa (Guardrailed Profiles)</h3>
          <p className="section-desc">
            Chọn một trong 3 phương án chuẩn hóa đã được tối ưu toán học và an toàn tải.
            Hệ thống khóa cứng các phạm vi bất biến để bảo vệ Agent và tránh làm tràn bộ nhớ máy chủ.
          </p>
        </div>

        <div className="preset-cards-grid">
          {/* Card 1: Balanced */}
          {(() => {
            const preset = TELEMETRY_PRESETS.balanced;
            const isActive = settings.active_profile === "balanced";
            const isApplying = applyingProfile === "balanced";

            return (
              <div className={`preset-card ${isActive ? "active" : ""}`}>
                <div className="preset-card-header">
                  <div className="preset-icon-wrap icon-balanced">
                    <ShieldCheck size={20} />
                  </div>
                  <div className="preset-badge-group">
                    <span className="preset-rec-tag">Khuyên dùng</span>
                    {isActive && <span className="preset-active-tag">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-card-title">{preset.name}</h4>
                <p className="preset-card-tagline">{preset.tagline}</p>

                <div className="preset-specs-list font-mono">
                  <div className="preset-spec-row">
                    <span>Chu kỳ lấy mẫu tài nguyên:</span>
                    <strong>{preset.telemetry_interval_seconds}s / lần</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Xác nhận quá tải CPU/RAM:</span>
                    <strong>{preset.cpu_overload_window_seconds}s (3 mẫu)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Cửa sổ mạng (Network Window):</span>
                    <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Ngưỡng nhạy dò quét cổng:</span>
                    <strong>≥ {preset.port_scan_threshold_ports} cổng</strong>
                  </div>
                </div>

                <div className="preset-impact-box">
                  <div className="impact-item">
                    <span>Mức chiếm CPU Agent:</span>
                    <strong>{preset.agent_cpu_impact}</strong>
                  </div>
                  <div className="impact-item">
                    <span>Băng thông giám sát:</span>
                    <strong>{preset.network_overhead}</strong>
                  </div>
                </div>

                <div className="preset-footer">
                  <button
                    type="button"
                    className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                    onClick={() => handleApplyPreset("balanced")}
                    disabled={isActive || Boolean(applyingProfile)}
                  >
                    {isApplying ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Đang áp dụng...
                      </>
                    ) : isActive ? (
                      <>
                        <Check size={14} /> Đang kích hoạt
                      </>
                    ) : (
                      "Áp dụng hồ sơ này"
                    )}
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Card 2: High Sensitivity */}
          {(() => {
            const preset = TELEMETRY_PRESETS.high_sensitivity;
            const isActive = settings.active_profile === "high_sensitivity";
            const isApplying = applyingProfile === "high_sensitivity";

            return (
              <div className={`preset-card ${isActive ? "active" : ""}`}>
                <div className="preset-card-header">
                  <div className="preset-icon-wrap icon-high-sens">
                    <Zap size={20} />
                  </div>
                  <div className="preset-badge-group">
                    <span className="preset-tag-sens">Độ nhạy cao</span>
                    {isActive && <span className="preset-active-tag">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-card-title">{preset.name}</h4>
                <p className="preset-card-tagline">{preset.tagline}</p>

                <div className="preset-specs-list font-mono">
                  <div className="preset-spec-row">
                    <span>Chu kỳ lấy mẫu tài nguyên:</span>
                    <strong>{preset.telemetry_interval_seconds}s / lần</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Xác nhận quá tải CPU/RAM:</span>
                    <strong>{preset.cpu_overload_window_seconds}s (3 mẫu)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Cửa sổ mạng (Network Window):</span>
                    <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Ngưỡng nhạy dò quét cổng:</span>
                    <strong>≥ {preset.port_scan_threshold_ports} cổng</strong>
                  </div>
                </div>

                <div className="preset-impact-box">
                  <div className="impact-item">
                    <span>Mức chiếm CPU Agent:</span>
                    <strong>{preset.agent_cpu_impact}</strong>
                  </div>
                  <div className="impact-item">
                    <span>Băng thông giám sát:</span>
                    <strong>{preset.network_overhead}</strong>
                  </div>
                </div>

                <div className="preset-footer">
                  <button
                    type="button"
                    className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                    onClick={() => handleApplyPreset("high_sensitivity")}
                    disabled={isActive || Boolean(applyingProfile)}
                  >
                    {isApplying ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Đang áp dụng...
                      </>
                    ) : isActive ? (
                      <>
                        <Check size={14} /> Đang kích hoạt
                      </>
                    ) : (
                      "Áp dụng hồ sơ này"
                    )}
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Card 3: Resource Saving */}
          {(() => {
            const preset = TELEMETRY_PRESETS.resource_saving;
            const isActive = settings.active_profile === "resource_saving";
            const isApplying = applyingProfile === "resource_saving";

            return (
              <div className={`preset-card ${isActive ? "active" : ""}`}>
                <div className="preset-card-header">
                  <div className="preset-icon-wrap icon-saving">
                    <Leaf size={20} />
                  </div>
                  <div className="preset-badge-group">
                    <span className="preset-tag-saving">Tiết kiệm I/O</span>
                    {isActive && <span className="preset-active-tag">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-card-title">{preset.name}</h4>
                <p className="preset-card-tagline">{preset.tagline}</p>

                <div className="preset-specs-list font-mono">
                  <div className="preset-spec-row">
                    <span>Chu kỳ lấy mẫu tài nguyên:</span>
                    <strong>{preset.telemetry_interval_seconds}s / lần</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Xác nhận quá tải CPU/RAM:</span>
                    <strong>{preset.cpu_overload_window_seconds}s (3 mẫu)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Cửa sổ mạng (Network Window):</span>
                    <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong>
                  </div>
                  <div className="preset-spec-row">
                    <span>Ngưỡng nhạy dò quét cổng:</span>
                    <strong>≥ {preset.port_scan_threshold_ports} cổng</strong>
                  </div>
                </div>

                <div className="preset-impact-box">
                  <div className="impact-item">
                    <span>Mức chiếm CPU Agent:</span>
                    <strong>{preset.agent_cpu_impact}</strong>
                  </div>
                  <div className="impact-item">
                    <span>Băng thông giám sát:</span>
                    <strong>{preset.network_overhead}</strong>
                  </div>
                </div>

                <div className="preset-footer">
                  <button
                    type="button"
                    className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                    onClick={() => handleApplyPreset("resource_saving")}
                    disabled={isActive || Boolean(applyingProfile)}
                  >
                    {isApplying ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Đang áp dụng...
                      </>
                    ) : isActive ? (
                      <>
                        <Check size={14} /> Đang kích hoạt
                      </>
                    ) : (
                      "Áp dụng hồ sơ này"
                    )}
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      </section>

      {/* 4. Detailed Specification Matrix Table */}
      <section className="settings-section">
        <div className="section-head">
          <h3 className="section-title">Bảng đối chiếu thông số &amp; Giới hạn an toàn</h3>
          <p className="section-desc">
            Chi tiết các tham số vận hành của từng hồ sơ và lý do kỹ thuật đằng sau các quy chuẩn khóa cứng.
          </p>
        </div>

        <div className="panel table-panel">
          <div className="table-scroll">
            <table className="host-table settings-matrix-table" aria-label="Bảng đối chiếu thông số cấu hình">
              <thead>
                <tr>
                  <th>Chỉ số / Tham số vận hành</th>
                  <th>Tiêu chuẩn (Balanced)</th>
                  <th>Nhạy cao (High Sensitivity)</th>
                  <th>Tiết kiệm tài nguyên</th>
                  <th>Lan can an toàn (Guardrail Rule)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <strong>Chu kỳ lấy mẫu tài nguyên (`telemetry_interval`)</strong>
                    <small className="text-muted block">Tần suất Agent gọi `psutil` đo tải CPU/RAM/Disk</small>
                  </td>
                  <td className="font-mono">5.0 giây / lần</td>
                  <td className="font-mono" style={{ color: "var(--status-warn)" }}>2.0 giây / lần</td>
                  <td className="font-mono">10.0 giây / lần</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Tối thiểu ≥ 1.0s (Chống cạn kiệt CPU máy chủ)
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Cửa sổ xác nhận CPU/RAM quá tải</strong>
                    <small className="text-muted block">Thời gian duy trì tải cao trước khi kích hoạt cảnh báo</small>
                  </td>
                  <td className="font-mono">15 giây (3 mẫu × 5s)</td>
                  <td className="font-mono">6 giây (3 mẫu × 2s)</td>
                  <td className="font-mono">30 giây (3 mẫu × 10s)</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Cố định 3 mẫu liên tiếp (Loại trừ spike ảo)
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Cửa sổ xác nhận tràn ổ đĩa (`disk`)</strong>
                    <small className="text-muted block">Dung lượng phân vùng mount đạt ngưỡng báo động</small>
                  </td>
                  <td className="font-mono">5.0 giây (1 mẫu gần nhất)</td>
                  <td className="font-mono">2.0 giây (1 mẫu gần nhất)</td>
                  <td className="font-mono">10.0 giây (1 mẫu gần nhất)</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> 1 mẫu gần nhất (Dung lượng đĩa không spike tức thời)
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Cửa sổ trích xuất lưu lượng mạng (`window_seconds`)</strong>
                    <small className="text-muted block">Độ dài cửa sổ trượt tổng hợp đặc trưng gói tin</small>
                  </td>
                  <td className="font-mono">10 giây</td>
                  <td className="font-mono">6 giây</td>
                  <td className="font-mono">20 giây</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Bắt buộc là bội số của bước trượt (Định lý Nyquist)
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Bước trượt lưu lượng mạng (`step_seconds`)</strong>
                    <small className="text-muted block">Khoảng thời gian trượt cửa sổ sang chu kỳ kế tiếp</small>
                  </td>
                  <td className="font-mono">5 giây (Chồng lấp 50%)</td>
                  <td className="font-mono">2 giây (Chồng lấp 66%)</td>
                  <td className="font-mono">10 giây (Chồng lấp 50%)</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Chồng lấp từ 50% đến tối đa 12 cửa sổ
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Ngưỡng nhận diện dò quét cổng (`port_scan`)</strong>
                    <small className="text-muted block">Số cổng bị quét khác nhau trong cửa sổ chuẩn</small>
                  </td>
                  <td className="font-mono">≥ 15 cổng</td>
                  <td className="font-mono">≥ 10 cổng</td>
                  <td className="font-mono">≥ 25 cổng</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Chuẩn hóa tỷ lệ theo cửa sổ 10s
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <strong>Ngưỡng phát hiện SYN Flood DoS</strong>
                    <small className="text-muted block">Số gói tin SYN bất thường kèm tỷ lệ lệch SYN/ACK</small>
                  </td>
                  <td className="font-mono">≥ 50 SYN (Tỷ lệ ≥ 3.0)</td>
                  <td className="font-mono">≥ 30 SYN (Tỷ lệ ≥ 2.5)</td>
                  <td className="font-mono">≥ 80 SYN (Tỷ lệ ≥ 4.0)</td>
                  <td>
                    <span className="guardrail-pill">
                      <Lock size={11} /> Tự động loại trừ lưu lượng Outbound
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 5. Invariant System Guardrails Callout */}
      <section className="settings-section">
        <div className="panel guardrails-summary-card">
          <div className="guardrails-card-head">
            <Lock size={18} className="text-accent" />
            <div>
              <h4 className="guardrails-title">Lan can kỹ thuật bảo vệ bất biến (System Safety Invariants)</h4>
              <p className="guardrails-subtitle">
                Các nguyên tắc an toàn được nhúng cứng vào nhân Controller và Agent để bảo vệ hệ thống tuyệt đối.
              </p>
            </div>
          </div>

          <div className="guardrails-grid">
            <div className="guardrail-box">
              <span className="guardrail-num">01</span>
              <div>
                <strong>Chống suy kiệt tài nguyên Agent</strong>
                <p>
                  Agent từ chối mọi yêu cầu thiết lập chu kỳ dưới 1.0 giây. Điều này đảm bảo daemon giám sát không bao giờ trở thành nguyên nhân làm tắc nghẽn tài nguyên của ứng dụng nghiệp vụ chính.
                </p>
              </div>
            </div>

            <div className="guardrail-box">
              <span className="guardrail-num">02</span>
              <div>
                <strong>Định lý lấy mẫu Nyquist-Shannon cho mạng</strong>
                <p>
                  Độ dài cửa sổ bắt gói tin mạng bắt buộc phải là bội số nguyên của bước trượt (Step). Cơ chế này đảm bảo dữ liệu dòng chảy mạng không bị đứt đoạn hoặc bỏ sót các gói tin tại ranh giới chuyển giao.
                </p>
              </div>
            </div>

            <div className="guardrail-box">
              <span className="guardrail-num">03</span>
              <div>
                <strong>Triệt tiêu báo động giả tài nguyên (Spike Suppression)</strong>
                <p>
                  Không cho phép cảnh báo CPU/RAM chỉ với 1 mẫu đơn lẻ. Mọi cảnh báo tài nguyên nghiêm trọng đều bắt buộc phải vượt ngưỡng trong ít nhất 3 chu kỳ đo liên tiếp.
                </p>
              </div>
            </div>

            <div className="guardrail-box">
              <span className="guardrail-num">04</span>
              <div>
                <strong>Bảo mật một chiều (Agent Push Model)</strong>
                <p>
                  Mọi thay đổi cấu hình từ giao diện Controller được truyền tải an toàn xuống Agent qua phản hồi nhịp tim Heartbeat định kỳ. Không mở bất kỳ cổng kết nối ngược (reverse port/SSH) nào vào Agent.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
