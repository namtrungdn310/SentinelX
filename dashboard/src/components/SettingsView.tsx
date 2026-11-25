import { useEffect, useState, useMemo } from "react";
import {
  Activity,
  Check,
  Clock,
  Cpu,
  Globe,
  Leaf,
  RefreshCw,
  ShieldCheck,
  Zap,
} from "lucide-react";
import type {
  Project,
  Node,
  PresetProfileType,
  ProjectSettings,
} from "../types";
import type { SecurityToastPayload } from "./SecurityToast";
import { TELEMETRY_PRESETS } from "../presets";
import {
  fetchProjectSettings,
  updateNodeSettings,
  updateProjectSettings,
} from "../api";
import { authService } from "../auth";

interface Props {
  selectedProjectId: string | null;
  projects: Project[];
  nodes: Node[];
  onProfileApplied?: (newProfile: PresetProfileType) => void;
  onSettingsPersisted?: (nodeIds: string[], profile: PresetProfileType, updatedAt: string) => void;
  onNotify?: (toast: SecurityToastPayload) => void;
}

function resolveNodeConfig(
  node: Node,
  projectSettings: ProjectSettings | null,
): { profile: PresetProfileType; updatedAt: string } {
  const capSettings = (
    node.agent_capabilities as
      | { settings?: { active_profile?: string; updated_at?: string } }
      | undefined
  )?.settings;
  if (
    capSettings?.active_profile &&
    Object.hasOwn(TELEMETRY_PRESETS, capSettings.active_profile)
  ) {
    return {
      profile: capSettings.active_profile as PresetProfileType,
      updatedAt: capSettings.updated_at || node.last_seen || node.created_at,
    };
  }
  if (
    projectSettings?.active_profile &&
    Object.hasOwn(TELEMETRY_PRESETS, projectSettings.active_profile)
  ) {
    return {
      profile: projectSettings.active_profile,
      updatedAt: projectSettings.updated_at,
    };
  }
  return {
    profile: "balanced",
    updatedAt: node.last_seen || node.created_at || new Date().toISOString(),
  };
}

export function SettingsView({
  selectedProjectId,
  projects,
  nodes,
  onProfileApplied,
  onSettingsPersisted,
  onNotify,
}: Props) {
  const effectiveProjectId = selectedProjectId || projects[0]?.id || "";
  const currentProject = projects.find((p) => p.id === effectiveProjectId);
  const [projectSettings, setProjectSettings] = useState<ProjectSettings | null>(null);

  useEffect(() => {
    if (!effectiveProjectId) {
      return;
    }
    let cancelled = false;
    void fetchProjectSettings(effectiveProjectId)
      .then((res) => {
        if (!cancelled) setProjectSettings(res);
      })
      .catch(() => null);
    return () => {
      cancelled = true;
    };
  }, [effectiveProjectId]);

  const availableNodes = useMemo(
    () =>
      nodes.filter(
        (n) => !effectiveProjectId || n.project_id === effectiveProjectId,
      ),
    [nodes, effectiveProjectId],
  );

  const [selectedNodeId, setSelectedNodeId] = useState<string>("");

  const effectiveNodeId = useMemo(() => {
    if (selectedNodeId && availableNodes.some((n) => n.id === selectedNodeId)) {
      return selectedNodeId;
    }
    return availableNodes[0]?.id || "";
  }, [availableNodes, selectedNodeId]);

  const selectedNode = useMemo(() => {
    return availableNodes.find((n) => n.id === effectiveNodeId) || null;
  }, [availableNodes, effectiveNodeId]);

  const [activeProfile, setActiveProfile] = useState<PresetProfileType>(() => {
    return selectedNode
      ? resolveNodeConfig(selectedNode, projectSettings).profile
      : "balanced";
  });
  const [lastUpdated, setLastUpdated] = useState<string>(() => {
    return selectedNode
      ? resolveNodeConfig(selectedNode, projectSettings).updatedAt
      : new Date().toISOString();
  });
  const [applyToAllInProject, setApplyToAllInProject] = useState(() => {
    if (availableNodes.length <= 1) return false;
    const firstProfile = resolveNodeConfig(availableNodes[0], null).profile;
    return availableNodes.every(
      (n) => resolveNodeConfig(n, null).profile === firstProfile,
    );
  });

  // Synchronously adjust state when selected node or project changes
  const [prevNodeId, setPrevNodeId] = useState(effectiveNodeId);
  const [prevProjectId, setPrevProjectId] = useState(effectiveProjectId);
  const [prevProjSettingsAt, setPrevProjSettingsAt] = useState(
    projectSettings?.updated_at ?? "",
  );

  if (
    prevNodeId !== effectiveNodeId ||
    prevProjectId !== effectiveProjectId ||
    prevProjSettingsAt !== (projectSettings?.updated_at ?? "")
  ) {
    setPrevNodeId(effectiveNodeId);
    setPrevProjectId(effectiveProjectId);
    setPrevProjSettingsAt(projectSettings?.updated_at ?? "");
    if (selectedNode) {
      const { profile, updatedAt } = resolveNodeConfig(selectedNode, projectSettings);
      setActiveProfile(profile);
      setLastUpdated(updatedAt);
    } else if (projectSettings) {
      setActiveProfile(projectSettings.active_profile);
      setLastUpdated(projectSettings.updated_at);
    }
    if (prevProjectId !== effectiveProjectId) {
      if (availableNodes.length > 1) {
        const firstProfile = resolveNodeConfig(
          availableNodes[0],
          projectSettings,
        ).profile;
        const allSame = availableNodes.every(
          (n) => resolveNodeConfig(n, projectSettings).profile === firstProfile,
        );
        setApplyToAllInProject(allSame);
      } else {
        setApplyToAllInProject(false);
      }
    }
  }

  const [applyingProfile, setApplyingProfile] = useState<PresetProfileType | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  const activePreset = useMemo(() => {
    return TELEMETRY_PRESETS[activeProfile] || TELEMETRY_PRESETS.balanced;
  }, [activeProfile]);

  const handleApplyPreset = async (profileId: PresetProfileType) => {
    if (!selectedNode || applyingProfile) return;
    try {
      setApplyingProfile(profileId);
      setSettingsError(null);
      const operatorEmail =
        authService.getCurrentUser()?.email || "operator@sentinelx.local";
      const targetProjectId = selectedNode.project_id || effectiveProjectId;

      const saved = applyToAllInProject
        ? await updateProjectSettings(targetProjectId, profileId, operatorEmail)
        : await updateNodeSettings(selectedNode.id, profileId, operatorEmail);

      const now = saved.updated_at || new Date().toISOString();
      if (applyToAllInProject) {
        setProjectSettings(saved);
        setApplyToAllInProject(true);
      } else {
        const allSame =
          availableNodes.length > 1 &&
          availableNodes.every((n) => {
            if (n.id === selectedNode.id) return true;
            return resolveNodeConfig(n, projectSettings).profile === profileId;
          });
        setApplyToAllInProject(allSame);
      }

      const updatedNodeIds = applyToAllInProject
        ? availableNodes.map((n) => n.id)
        : [selectedNode.id];

      onSettingsPersisted?.(updatedNodeIds, profileId, now);
      setActiveProfile(profileId);
      setLastUpdated(now);
      onProfileApplied?.(profileId);

      const targetPreset = TELEMETRY_PRESETS[profileId];
      onNotify?.({
        id: `toast-settings-${profileId}`,
        type: "settings",
        title: "Cập nhật cấu hình thành công",
        message: applyToAllInProject
          ? `Đã áp dụng cấu hình [${targetPreset.name}] cho toàn bộ ${availableNodes.length} máy chủ trong ${currentProject?.name || "dự án"}.`
          : `Đã áp dụng cấu hình [${targetPreset.name}] cho máy chủ ${selectedNode.hostname}.`,
      });
    } catch (err: unknown) {
      setSettingsError(
        err instanceof Error ? err.message : "Không lưu được cấu hình xuống Controller",
      );
    } finally {
      setApplyingProfile(null);
    }
  };

  return (
    <div className="settings-simple-container">
      {settingsError && (
        <div className="connection-error" role="alert">
          <span>{settingsError}</span>
        </div>
      )}
      {/* 1. Server Selector Toolbar (Identical to Telemetry view) */}
      <div className="telemetry-host-toolbar">
        <select
          id="settings-host"
          value={effectiveNodeId}
          onChange={(event) => setSelectedNodeId(event.target.value)}
          disabled={!availableNodes.length}
          aria-label="Chọn máy chủ"
        >
          {!availableNodes.length && (
            <option value="">Không có máy chủ phù hợp</option>
          )}
          {availableNodes.map((node) => (
            <option key={node.id} value={node.id}>
              {node.hostname} · {node.ip_address}
            </option>
          ))}
        </select>

        {/* Right Corner Update Timestamp */}
        <div className="config-meta font-mono" style={{ marginLeft: "auto" }}>
          <Clock size={13} />
          <span>
            Cập nhật: {new Date(lastUpdated).toLocaleTimeString("vi-VN")} · {new Date(lastUpdated).toLocaleDateString("vi-VN")}
          </span>
        </div>
      </div>

      {/* 2. Window Monitoring - Split Resource vs Network */}
      {selectedNode && (
        <div className="specs-split-container">
          {/* Nhóm 1: Cửa sổ Tài nguyên (CPU / RAM / Disk) */}
          <div className="spec-category-block">
            <div className="spec-category-header">
              <Cpu size={15} />
              <span>Cửa sổ tài nguyên (CPU, RAM, Đĩa)</span>
            </div>
            <div className="spec-category-grid">
              <div className="spec-tile">
                <div className="spec-tile-head">
                  <Clock size={13} />
                  <span>Chu kỳ lấy mẫu</span>
                </div>
                <strong className="spec-tile-val font-mono">
                  {activePreset.telemetry_interval_seconds.toFixed(1)}s / lần
                </strong>
              </div>

              <div className="spec-tile">
                <div className="spec-tile-head">
                  <ShieldCheck size={13} />
                  <span>Kiểm chứng quá tải</span>
                </div>
                <strong className="spec-tile-val font-mono">
                  {activePreset.cpu_overload_window_seconds.toFixed(0)}s (3 chu kỳ liên tiếp)
                </strong>
              </div>
            </div>
          </div>

          {/* Nhóm 2: Cửa sổ và kiểm chứng sự cố mạng */}
          <div className="spec-category-block">
            <div className="spec-category-header">
              <Globe size={15} />
              <span>Cửa sổ và kiểm chứng sự cố mạng (Network &amp; Port Scan)</span>
            </div>
            <div className="spec-category-grid">
              <div className="spec-tile">
                <div className="spec-tile-head">
                  <Activity size={13} />
                  <span>Cửa sổ gói tin mạng</span>
                </div>
                <strong className="spec-tile-val font-mono">
                  {activePreset.network_window_seconds}s (sliding: {activePreset.network_step_seconds}s)
                </strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. 3 Presets Options Section */}
      <div className="panel preset-selection-panel">
        <div className="preset-panel-header">
          <div>
            <h3 className="preset-panel-title">Thay đổi cấu hình</h3>
          </div>

          {availableNodes.length > 1 && (
            <label className={`apply-all-checkbox ${applyToAllInProject ? "is-checked" : ""}`}>
              <input
                type="checkbox"
                checked={applyToAllInProject}
                onChange={(e) => setApplyToAllInProject(e.target.checked)}
              />
              <span>
                Áp dụng cho <strong>{availableNodes.length} máy chủ</strong> trong {currentProject?.name || "dự án"}
              </span>
            </label>
          )}
        </div>

        <div className="preset-grid-3">
          {/* Option 1: Balanced */}
          {(() => {
            const preset = TELEMETRY_PRESETS.balanced;
            const isActive = activeProfile === "balanced";
            const isApplying = applyingProfile === "balanced";

            return (
              <div className={`preset-box ${isActive ? "selected" : ""}`}>
                <div className="preset-box-top">
                  <div className="preset-box-icon balanced-icon">
                    <ShieldCheck size={20} />
                  </div>
                  <div className="preset-box-tags">
                    <span className="rec-badge">Mặc định</span>
                    {isActive && <span className="active-badge">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-box-name">Balanced</h4>

                <div className="preset-bullets font-mono">
                  <div>• Đo tài nguyên: <strong>{preset.telemetry_interval_seconds}s</strong></div>
                  <div>• Kiểm chứng quá tải: <strong>{preset.cpu_overload_window_seconds}s</strong></div>
                  <div>• Cửa sổ mạng: <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong></div>
                  <div>• Tải CPU Agent: <strong>{preset.agent_cpu_impact}</strong></div>
                </div>

                <button
                  type="button"
                  className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                  onClick={() => handleApplyPreset("balanced")}
                  disabled={isActive || Boolean(applyingProfile) || !selectedNode}
                >
                  {isApplying ? (
                    <>
                      <RefreshCw size={13} className="spin" /> Đang lưu...
                    </>
                  ) : isActive ? (
                    <>
                      <Check size={13} /> Đang áp dụng
                    </>
                  ) : (
                    "Áp dụng"
                  )}
                </button>
              </div>
            );
          })()}

          {/* Option 2: High Sensitivity */}
          {(() => {
            const preset = TELEMETRY_PRESETS.high_sensitivity;
            const isActive = activeProfile === "high_sensitivity";
            const isApplying = applyingProfile === "high_sensitivity";

            return (
              <div className={`preset-box ${isActive ? "selected" : ""}`}>
                <div className="preset-box-top">
                  <div className="preset-box-icon high-icon">
                    <Zap size={20} />
                  </div>
                  <div className="preset-box-tags">
                    {isActive && <span className="active-badge">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-box-name">High Sensitivity</h4>

                <div className="preset-bullets font-mono">
                  <div>• Đo tài nguyên: <strong>{preset.telemetry_interval_seconds}s</strong></div>
                  <div>• Kiểm chứng quá tải: <strong>{preset.cpu_overload_window_seconds}s</strong></div>
                  <div>• Cửa sổ mạng: <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong></div>
                  <div>• Tải CPU Agent: <strong>{preset.agent_cpu_impact}</strong></div>
                </div>

                <button
                  type="button"
                  className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                  onClick={() => handleApplyPreset("high_sensitivity")}
                  disabled={isActive || Boolean(applyingProfile) || !selectedNode}
                >
                  {isApplying ? (
                    <>
                      <RefreshCw size={13} className="spin" /> Đang lưu...
                    </>
                  ) : isActive ? (
                    <>
                      <Check size={13} /> Đang áp dụng
                    </>
                  ) : (
                    "Áp dụng"
                  )}
                </button>
              </div>
            );
          })()}

          {/* Option 3: Resource Saving */}
          {(() => {
            const preset = TELEMETRY_PRESETS.resource_saving;
            const isActive = activeProfile === "resource_saving";
            const isApplying = applyingProfile === "resource_saving";

            return (
              <div className={`preset-box ${isActive ? "selected" : ""}`}>
                <div className="preset-box-top">
                  <div className="preset-box-icon saving-icon">
                    <Leaf size={20} />
                  </div>
                  <div className="preset-box-tags">
                    {isActive && <span className="active-badge">✓ Đang dùng</span>}
                  </div>
                </div>

                <h4 className="preset-box-name">Resource-Saving</h4>

                <div className="preset-bullets font-mono">
                  <div>• Đo tài nguyên: <strong>{preset.telemetry_interval_seconds}s</strong></div>
                  <div>• Kiểm chứng quá tải: <strong>{preset.cpu_overload_window_seconds}s</strong></div>
                  <div>• Cửa sổ mạng: <strong>{preset.network_window_seconds}s (trượt {preset.network_step_seconds}s)</strong></div>
                  <div>• Tải CPU Agent: <strong>{preset.agent_cpu_impact}</strong></div>
                </div>

                <button
                  type="button"
                  className={`btn ${isActive ? "btn-outline active-btn" : "btn-primary"}`}
                  onClick={() => handleApplyPreset("resource_saving")}
                  disabled={isActive || Boolean(applyingProfile) || !selectedNode}
                >
                  {isApplying ? (
                    <>
                      <RefreshCw size={13} className="spin" /> Đang lưu...
                    </>
                  ) : isActive ? (
                    <>
                      <Check size={13} /> Đang áp dụng
                    </>
                  ) : (
                    "Áp dụng"
                  )}
                </button>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
