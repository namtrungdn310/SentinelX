/**
 * REST API Client for SentinelX Controller.
 */

import type {
  DefenseAction,
  DefensePolicy,
  DetectionEvent,
  IPWhitelist,
  Incident,
  IncidentDetail,
  IncidentStatus,
  MetricQueryResponse,
  Node,
  PresetProfileType,
  Project,
  ProjectSettings,
  RealtimeMessage,
} from "./types";
import { MOCK_PROJECT_SETTINGS } from "./mockData";

const API_BASE = "/api/v1";

export async function fetchDetectionEvents(): Promise<RealtimeMessage[]> {
  const response = await fetch(`${API_BASE}/detection-events?limit=50`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("Không tải được lịch sử cảnh báo");
  const data: { items: DetectionEvent[] } = await response.json();
  return data.items.map((item) => ({
    event: "detection_alert",
    timestamp: item.detected_at,
    data: { ...item },
  }));
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Lỗi tải dự án: ${res.statusText}`);
  const data = await res.json();
  return data.map((project: Project & { project_id?: string }) => ({
    ...project,
    id: project.project_id ?? project.id,
  }));
}

export async function createProject(
  name: string,
  description?: string,
): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error(`Lỗi tạo dự án: ${res.statusText}`);
  const data = await res.json();
  return {
    id: data.project_id,
    name: data.name,
    description: data.description,
    created_at: data.created_at,
  };
}

export async function fetchNodes(projectId?: string): Promise<Node[]> {
  const url = projectId
    ? `${API_BASE}/nodes?project_id=${projectId}`
    : `${API_BASE}/nodes`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`Lỗi tải máy chủ: ${res.statusText}`);
  const data = await res.json();
  return data.map((n: Record<string, unknown>) => ({
    id: n.node_id || n.id,
    project_id: n.project_id,
    hostname: n.hostname,
    ip_address: n.ip_address,
    status: n.status,
    last_seen: n.last_seen || n.last_seen_at || null,
    created_at: n.created_at,
    agent_capabilities: (n.agent_capabilities as Record<string, unknown> | undefined) ?? undefined,
  }));
}

export async function createNode(
  projectId: string,
  hostname: string,
  ipAddress: string,
): Promise<Node> {
  const res = await fetch(`${API_BASE}/nodes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      hostname,
      ip_address: ipAddress,
    }),
  });
  if (!res.ok) throw new Error(`Lỗi đăng ký node: ${res.statusText}`);
  const data = await res.json();
  return {
    id: data.node_id,
    project_id: data.project_id,
    hostname: data.hostname,
    ip_address: data.ip_address,
    status: data.status,
    last_seen: data.last_seen,
    created_at: data.created_at,
  };
}

export async function createEnrollmentToken(
  nodeId: string,
  hours = 24,
): Promise<string> {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}/enrollment-tokens`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expires_in_hours: hours }),
  });
  if (!res.ok)
    throw new Error(`Lỗi tạo mã enrollment token: ${res.statusText}`);
  const data = await res.json();
  return data.enrollment_token;
}

export async function fetchNodeMetrics(
  nodeId: string,
  limit = 50,
): Promise<MetricQueryResponse> {
  const res = await fetch(
    `${API_BASE}/telemetry/nodes/${nodeId}/metrics?limit=${limit}`,
    { signal: AbortSignal.timeout(10000) },
  );
  if (!res.ok) throw new Error(`Lỗi tải số liệu node: ${res.statusText}`);
  return res.json();
}

// ----------------------------------------------------
// Incidents API (M5)
// ----------------------------------------------------

export async function fetchIncidents(params?: {
  projectId?: string;
  nodeId?: string;
  status?: string;
  severity?: string;
  limit?: number;
}): Promise<Incident[]> {
  const query = new URLSearchParams();
  if (params?.projectId) query.set("project_id", params.projectId);
  if (params?.nodeId) query.set("node_id", params.nodeId);
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.severity && params.severity !== "all") query.set("severity", params.severity);
  query.set("limit", String(params?.limit ?? 50));

  const res = await fetch(`${API_BASE}/incidents?${query.toString()}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Lỗi tải danh sách sự cố: ${res.statusText}`);
  const data = await res.json();
  return data.items || [];
}

export async function fetchIncidentDetail(incidentId: string): Promise<IncidentDetail> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Lỗi tải chi tiết sự cố: ${res.statusText}`);
  return res.json();
}

export async function updateIncident(
  incidentId: string,
  update: { status?: IncidentStatus; summary?: string },
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`Lỗi cập nhật sự cố: ${res.statusText}`);
  return res.json();
}

export async function deleteIncident(incidentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Lỗi xóa sự cố: ${res.statusText}`);
}

// ----------------------------------------------------
// Defense Actions API (M6, M7, M8)
// ----------------------------------------------------

export async function fetchDefenseActions(params?: {
  nodeId?: string;
  incidentId?: string;
  status?: string;
  limit?: number;
}): Promise<DefenseAction[]> {
  const query = new URLSearchParams();
  if (params?.nodeId) query.set("node_id", params.nodeId);
  if (params?.incidentId) query.set("incident_id", params.incidentId);
  if (params?.status && params.status !== "all") query.set("status", params.status);
  query.set("limit", String(params?.limit ?? 50));

  const res = await fetch(`${API_BASE}/defense/actions?${query.toString()}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Lỗi tải danh sách lệnh phòng thủ: ${res.statusText}`);
  const data = await res.json();
  return data.items || [];
}

export async function createManualDefenseAction(payload: {
  node_id: string;
  action_type: string;
  target_ip?: string | null;
  command_payload?: Record<string, unknown>;
  incident_id?: string | null;
}): Promise<DefenseAction> {
  const res = await fetch(`${API_BASE}/defense/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      if (typeof errBody?.detail === "string") {
        detail = errBody.detail;
      }
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(`Lỗi thực hiện lệnh phòng thủ: ${detail}`);
  }
  return res.json();
}

export async function revertDefenseAction(actionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/recovery/actions/${actionId}/revert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: "MANUAL_UNBLOCK" }),
  });
  if (!res.ok) throw new Error(`Lỗi gỡ bỏ lệnh chặn IP: ${res.statusText}`);
}

export async function cancelDefenseAction(actionId: string): Promise<DefenseAction> {
  const res = await fetch(`${API_BASE}/defense/actions/${actionId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Lỗi hủy lệnh phòng thủ chờ gửi: ${res.statusText}`);
  return res.json();
}

// ----------------------------------------------------
// Policies & Whitelist API (M5)
// ----------------------------------------------------

export async function fetchPolicies(projectId?: string): Promise<DefensePolicy[]> {
  const url = projectId
    ? `${API_BASE}/defense-policies?project_id=${projectId}`
    : `${API_BASE}/defense-policies`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`Lỗi tải danh mục chính sách: ${res.statusText}`);
  const data = await res.json();
  return data.items || [];
}

export async function createPolicy(
  projectId: string,
  policy: {
    name: string;
    event_type: string;
    action_type: string;
    target_params?: Record<string, unknown>;
    cooldown_seconds?: number;
    block_duration_seconds?: number;
    is_auto_execute?: boolean;
    is_active?: boolean;
  },
): Promise<DefensePolicy> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/defense-policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  if (!res.ok) throw new Error(`Lỗi tạo chính sách phòng thủ: ${res.statusText}`);
  return res.json();
}

export async function updatePolicy(
  policyId: string,
  update: {
    name?: string;
    action_type?: string;
    is_active?: boolean;
    is_auto_execute?: boolean;
    cooldown_seconds?: number;
    block_duration_seconds?: number;
  },
): Promise<DefensePolicy> {
  const res = await fetch(`${API_BASE}/defense-policies/${policyId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`Lỗi cập nhật chính sách: ${res.statusText}`);
  return res.json();
}

export async function deletePolicy(policyId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/defense-policies/${policyId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Lỗi xóa chính sách: ${res.statusText}`);
}

export async function fetchWhitelist(projectId: string): Promise<IPWhitelist[]> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/ip-whitelist`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Lỗi tải danh sách an toàn: ${res.statusText}`);
  const data = await res.json();
  return data.items || [];
}

export async function createWhitelist(
  projectId: string,
  cidr: string,
  description?: string,
): Promise<IPWhitelist> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/ip-whitelist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cidr,
      description,
    }),
  });
  if (!res.ok) throw new Error(`Lỗi thêm IP an toàn: ${res.statusText}`);
  return res.json();
}

export async function deleteWhitelist(whitelistId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/ip-whitelist/${whitelistId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Lỗi xóa IP an toàn: ${res.statusText}`);
}

// ----------------------------------------------------
// Project Settings & Guardrailed Presets API
// ----------------------------------------------------

export async function fetchProjectSettings(projectId: string): Promise<ProjectSettings> {
  const localKey = `sentinelx_settings_${projectId}`;
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/settings`, {
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      try {
        localStorage.setItem(localKey, JSON.stringify(data));
      } catch {
        // storage fallback
      }
      return data;
    }
  } catch {
    // fallback to local storage or mock
  }

  try {
    const saved = localStorage.getItem(localKey);
    if (saved) return JSON.parse(saved);
  } catch {
    // storage fallback
  }

  return (
    MOCK_PROJECT_SETTINGS[projectId] || {
      project_id: projectId,
      active_profile: "balanced",
      updated_at: new Date().toISOString(),
      updated_by: "system",
    }
  );
}

export async function updateProjectSettings(
  projectId: string,
  profile: PresetProfileType,
  updatedBy = "admin@sentinelx.com",
  strict = false,
): Promise<ProjectSettings> {
  const localKey = `sentinelx_settings_${projectId}`;
  const updated: ProjectSettings = {
    project_id: projectId,
    active_profile: profile,
    updated_at: new Date().toISOString(),
    updated_by: updatedBy,
  };

  if (strict) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_profile: profile, updated_by: updatedBy }),
    });
    if (!res.ok) throw new Error(`Lỗi lưu cấu hình dự án: ${res.statusText}`);
    const saved: ProjectSettings = await res.json();
    try {
      localStorage.setItem(localKey, JSON.stringify(saved));
    } catch {
      // storage fallback
    }
    return saved;
  }

  try {
    localStorage.setItem(localKey, JSON.stringify(updated));
  } catch {
    // storage fallback
  }

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_profile: profile, updated_by: updatedBy }),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // fallback to local updated
  }

  return updated;
}

export async function updateNodeSettings(
  nodeId: string,
  profile: PresetProfileType,
  updatedBy = "admin@sentinelx.com",
): Promise<ProjectSettings> {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active_profile: profile, updated_by: updatedBy }),
  });
  if (!res.ok) throw new Error(`Lỗi lưu cấu hình máy chủ: ${res.statusText}`);
  return res.json();
}
