import { useState, useMemo } from "react";
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
} from "../types";
import type { SecurityToastPayload } from "./SecurityToast";
import { TELEMETRY_PRESETS, MOCK_PROJECT_SETTINGS } from "../mockData";
import { updateNodeSettings, updateProjectSettings } from "../api";

interface Props {
  selectedProjectId: string | null;
  projects: Project[];
  nodes: Node[];
  isDemoMode: boolean;
  onProfileApplied?: (newProfile: PresetProfileType) => void;
  onSettingsPersisted?: (nodeIds: string[], profile: PresetProfileType, updatedAt: string) => void;
  onNotify?: (toast: SecurityToastPayload) => void;
}

function resolveNodeConfig(
  node: Node,
  projectId: string
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
  try {
    // 1. Try node-specific local setting
    const nodeSaved = localStorage.getItem(`sentinelx_node_settings_${node.id}`);
    if (nodeSaved) {
      const parsed = JSON.parse(nodeSaved);
      if (parsed.active_profile) {
        return {
          profile: parsed.active_profile as PresetProfileType,
          updatedAt: parsed.updated_at || new Date().toISOString(),
        };
      }
    }
    // 2. Try project local setting
    const projSaved = localStorage.getItem(`sentinelx_settings_${node.project_id || projectId}`);
    if (projSaved) {
      const parsed = JSON.parse(projSaved);
      if (parsed.active_profile) {
        return {
          profile: parsed.active_profile as PresetProfileType,
          updatedAt: parsed.updated_at || new Date().toISOString(),
        };
      }
    }
    // 3. Fallback to mock project setting or default balanced
    const mockProj = MOCK_PROJECT_SETTINGS[node.project_id || projectId];
    return {
      profile: (mockProj?.active_profile || "balanced") as PresetProfileType,
      updatedAt: mockProj?.updated_at || new Date().toISOString(),
    };
  } catch {
    return {
      profile: "balanced",
      updatedAt: new Date().toISOString(),
    };
  }
}

export function SettingsView({
  selectedProjectId,
  projects,
  nodes,
  isDemoMode,
  onProfileApplied,
  onSettingsPersisted,
  onNotify,
}: Props) {
  const effectiveProjectId = selectedProjectId || projects[0]?.id || "";
  const currentProject = projects.find((p) => p.id === effectiveProjectId);

  // Filter nodes belonging to the current project, or all nodes if none filtered
  const availableNodes = useMemo(() => {
    const filtered = nodes.filter(
      (n) => !effectiveProjectId || n.project_id === effectiveProjectId
    );
    return filtered.length > 0 ? filtered : nodes;
  }, [nodes, effectiveProjectId]);

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

  // Read active profile for this specific node (with fallback to project setting)
  const [activeProfile, setActiveProfile] = useState<PresetProfileType>(() => {
    return selectedNode ? resolveNodeConfig(selectedNode, effectiveProjectId).profile : "balanced";
  });
  const [lastUpdated, setLastUpdated] = useState<string>(() => {
    return selectedNode ? resolveNodeConfig(selectedNode, effectiveProjectId).updatedAt : new Date().toISOString();
  });
  const [applyToAllInProject, setApplyToAllInProject] = useState(() => {
    if (availableNodes.length <= 1) return false;
    const firstProfile = resolveNodeConfig(availableNodes[0], effectiveProjectId).profile;
    return availableNodes.every(
      (n) => resolveNodeConfig(n, effectiveProjectId).profile === firstProfile
    );
  });

  // Synchronously adjust state when selected node or project changes (React pattern: adjusting state during render)
  const [prevNodeId, setPrevNodeId] = useState(effectiveNodeId);
  const [prevProjectId, setPrevProjectId] = useState(effectiveProjectId);

  if (prevNodeId !== effectiveNodeId || prevProjectId !== effectiveProjectId) {
    setPrevNodeId(effectiveNodeId);
    setPrevProjectId(effectiveProjectId);
    if (selectedNode) {
      const { profile, updatedAt } = resolveNodeConfig(selectedNode, effectiveProjectId);
      setActiveProfile(profile);
      setLastUpdated(updatedAt);
    }
    // Only re-evaluate applyToAllInProject default when switching to a different project
    if (prevProjectId !== effectiveProjectId) {
      if (availableNodes.length > 1) {
        const firstProfile = resolveNodeConfig(availableNodes[0], effectiveProjectId).profile;
        const allSame = availableNodes.every(
          (n) => resolveNodeConfig(n, effectiveProjectId).profile === firstProfile
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
      let now = new Date().toISOString();
      const targetProjectId = selectedNode.project_id || effectiveProjectId;

      if (!isDemoMode) {
        if (applyToAllInProject) {
          const saved = await updateProjectSettings(
            targetProjectId,
            profileId,
            "admin@sentinelx.com",
            true,
          );
          now = saved.updated_at || now;
        } else {
          const saved = await updateNodeSettings(
            selectedNode.id,
            profileId,
            "admin@sentinelx.com",
          );
          now = saved.updated_at || now;
        }
      } else if (applyToAllInProject) {
        void updateProjectSettings(targetProjectId, profileId);
      }

      // 1. Save local node setting
      localStorage.setItem(
        `sentinelx_node_settings_${selectedNode.id}`,
        JSON.stringify({
          node_id: selectedNode.id,
          active_profile: profileId,
          updated_at: now,
          updated_by: "admin@sentinelx.com",
        })
      );

      // 2. If apply to all or updating project level
      const updatedNodeIds = applyToAllInProject
        ? availableNodes.map((n) => n.id)
        : [selectedNode.id];
      if (applyToAllInProject) {
        availableNodes.forEach((n) => {
          localStorage.setItem(
            `sentinelx_node_settings_${n.id}`,
            JSON.stringify({
              node_id: n.id,
              active_profile: profileId,
              updated_at: now,
              updated_by: "admin@sentinelx.com",
            })
          );
        });
        localStorage.setItem(
          `sentinelx_settings_${targetProjectId}`,
          JSON.stringify({
            project_id: targetProjectId,
            active_profile: profileId,
            updated_at: now,
            updated_by: "admin@sentinelx.com",
          })
        );
        setApplyToAllInProject(true);
      } else {
        // Updated only selectedNode: recheck if all nodes now share the same profile
        const allSame = availableNodes.length > 1 && availableNodes.every((n) => {
          if (n.id === selectedNode.id) return true;
          return resolveNodeConfig(n, effectiveProjectId).profile === profileId;
        });
        setApplyToAllInProject(allSame);
      }

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
        err instanceof Error ? err.message : "Không lưu được cấu hình xuống Controller"
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
                  disabled={isActive || Boolean(applyingProfile)}
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
                  disabled={isActive || Boolean(applyingProfile)}
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
                  disabled={isActive || Boolean(applyingProfile)}
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
