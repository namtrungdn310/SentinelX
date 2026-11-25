/**
 * REST API Client for SentinelX Controller.
 */

import type {
  AgentBundleInfo,
  DefenseAction,
  DefensePolicy,
  DetectionEvent,
  IPWhitelist,
  Incident,
  IncidentDetail,
  IncidentStatus,
  LBAlgorithmType,
  MetricQueryResponse,
  Node,
  NodeLBRoleType,
  PresetProfileType,
  Project,
  ProjectLBConfig,
  ProjectLBStatus,
  ProjectSettings,
  RealtimeMessage,
} from "./types";

const API_BASE = "/api/v1";

async function extractApiError(res: Response, fallback: string): Promise<string> {
  let detail = res.statusText || `HTTP ${res.status}`;
  try {
    const errBody = await res.json();
    if (typeof errBody?.detail === "string" && errBody.detail.trim()) {
      detail = errBody.detail;
    } else if (Array.isArray(errBody?.detail) && errBody.detail.length > 0) {
      const msgs = errBody.detail
        .map((item: { msg?: unknown; loc?: unknown[] }) => {
          const msg = typeof item?.msg === "string" ? item.msg : "";
          const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null;
          return field && msg ? `${String(field)}: ${msg}` : msg;
        })
        .filter(Boolean);
      if (msgs.length > 0) detail = msgs.join("; ");
    } else if (typeof errBody?.error === "string" && errBody.error.trim()) {
      detail = errBody.error;
    }
  } catch {
    // ignore non-JSON body
  }
  return `${fallback}: ${detail}`;
}

export async function fetchDetectionEvents(): Promise<RealtimeMessage[]> {
  const response = await fetch(`${API_BASE}/detection-events?limit=50`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    throw new Error(await extractApiError(response, "Không tải được lịch sử cảnh báo"));
  }
  const data: { items: DetectionEvent[] } = await response.json();
  return data.items.map((item) => ({
    event: "detection_alert",
    timestamp: item.detected_at,
    data: { ...item },
  }));
}

export function defaultProjectLBConfig(): ProjectLBConfig {
  return {
    enabled: false,
    lb_url: null,
    algorithm: "round_robin",
    health_path: "/health",
    health_interval_seconds: 3,
    failure_threshold: 3,
    success_threshold: 2,
  };
}

function normalizeProject(data: Record<string, unknown>): Project {
  return {
    id: String(data.project_id ?? data.id),
    name: String(data.name ?? ""),
    description: (data.description as string | null) ?? null,
    load_balancer: (data.load_balancer as ProjectLBConfig | undefined) ?? defaultProjectLBConfig(),
    created_at: String(data.created_at ?? ""),
  };
}

function normalizeNode(data: Record<string, unknown>): Node {
  const rawCaps =
    data.agent_capabilities && typeof data.agent_capabilities === "object"
      ? (data.agent_capabilities as Record<string, unknown>)
      : undefined;
  const hw =
    rawCaps && typeof rawCaps.hardware === "object" && rawCaps.hardware !== null
      ? (rawCaps.hardware as Record<string, unknown>)
      : undefined;
  const rawStatus = String(data.status ?? "unenrolled");
  const status: Node["status"] =
    rawStatus === "online" || rawStatus === "offline" || rawStatus === "unenrolled"
      ? rawStatus
      : "offline";

  return {
    id: String(data.node_id ?? data.id),
    project_id: String(data.project_id ?? ""),
    hostname: String(data.hostname ?? ""),
    ip_address: String(data.ip_address ?? ""),
    status,
    os_info: (data.os_info as string | null | undefined) ?? null,
    last_seen: (data.last_seen ?? data.last_seen_at ?? null) as string | null,
    created_at: String(data.created_at ?? ""),
    lb_role: (data.lb_role as NodeLBRoleType | undefined) ?? "standalone",
    lb_backend_port: typeof data.lb_backend_port === "number" ? data.lb_backend_port : 8080,
    lb_health_path: (data.lb_health_path as string | null | undefined) ?? null,
    agent_capabilities: rawCaps,
    cpuCores:
      typeof hw?.cpu_cores === "number" && hw.cpu_cores > 0 ? hw.cpu_cores : undefined,
    totalMemoryBytes:
      typeof hw?.total_memory_bytes === "number" && hw.total_memory_bytes > 0
        ? hw.total_memory_bytes
        : undefined,
    totalDiskBytes:
      typeof hw?.total_disk_bytes === "number" && hw.total_disk_bytes > 0
        ? hw.total_disk_bytes
        : undefined,
  };
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải dự án"));
  const data = await res.json();
  return data.map((project: Record<string, unknown>) => normalizeProject(project));
}

export async function createProject(
  name: string,
  description?: string,
  loadBalancer?: ProjectLBConfig,
): Promise<Project> {
  const payload: Record<string, unknown> = {
    name: name.trim(),
    description: description?.trim() ? description.trim() : null,
  };
  if (loadBalancer) {
    payload.load_balancer = loadBalancer;
  }
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tạo dự án"));
  return normalizeProject(await res.json());
}

export async function updateProject(
  projectId: string,
  payload: { name?: string; description?: string | null; load_balancer?: ProjectLBConfig },
): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi cập nhật dự án"));
  return normalizeProject(await res.json());
}

export async function fetchNodes(projectId?: string): Promise<Node[]> {
  const url = projectId
    ? `${API_BASE}/nodes?project_id=${projectId}`
    : `${API_BASE}/nodes`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải máy chủ"));
  const data = await res.json();
  return data.map((n: Record<string, unknown>) => normalizeNode(n));
}

export async function createNode(
  projectId: string,
  hostname: string,
  ipAddress: string,
  lbConfig?: { lb_role?: NodeLBRoleType; lb_backend_port?: number; lb_health_path?: string | null },
): Promise<Node> {
  const res = await fetch(`${API_BASE}/nodes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      hostname: hostname.trim(),
      ip_address: ipAddress.trim(),
      ...(lbConfig ? lbConfig : {}),
    }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi đăng ký máy chủ"));
  return normalizeNode(await res.json());
}

export async function updateNode(
  nodeId: string,
  payload: {
    hostname?: string;
    lb_role?: NodeLBRoleType;
    lb_backend_port?: number;
    lb_health_path?: string | null;
  },
): Promise<Node> {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi cập nhật máy chủ"));
  return normalizeNode(await res.json());
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
  if (!res.ok) {
    throw new Error(await extractApiError(res, "Lỗi tạo mã enrollment token"));
  }
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
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải số liệu node"));
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
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải danh sách sự cố"));
  const data = await res.json();
  return data.items || [];
}

export async function fetchIncidentDetail(incidentId: string): Promise<IncidentDetail> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải chi tiết sự cố"));
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
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi cập nhật sự cố"));
  return res.json();
}

export async function deleteIncident(incidentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi xóa sự cố"));
}

// ----------------------------------------------------
// Defense Actions API (M6, M7, M8)
// ----------------------------------------------------

export async function fetchDefenseActions(params?: {
  projectId?: string;
  nodeId?: string;
  incidentId?: string;
  status?: string;
  limit?: number;
}): Promise<DefenseAction[]> {
  const query = new URLSearchParams();
  if (params?.projectId) query.set("project_id", params.projectId);
  if (params?.nodeId) query.set("node_id", params.nodeId);
  if (params?.incidentId) query.set("incident_id", params.incidentId);
  if (params?.status && params.status !== "all") query.set("status", params.status);
  query.set("limit", String(params?.limit ?? 50));

  const res = await fetch(`${API_BASE}/defense/actions?${query.toString()}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải danh sách lệnh phòng thủ"));
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
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi thực hiện lệnh phòng thủ"));
  return res.json();
}

export async function revertDefenseAction(actionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/recovery/actions/${actionId}/revert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: "MANUAL_UNBLOCK" }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi gỡ bỏ lệnh chặn IP"));
}

export async function cancelDefenseAction(actionId: string): Promise<DefenseAction> {
  const res = await fetch(`${API_BASE}/defense/actions/${actionId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi hủy lệnh phòng thủ chờ gửi"));
  return res.json();
}

// ----------------------------------------------------
// Policies & Whitelist API (M5)
// ----------------------------------------------------

function normalizePolicyResponse(
  raw: DefensePolicy & { enabled?: boolean },
): DefensePolicy {
  return {
    ...raw,
    is_active: Boolean(raw.is_active ?? raw.enabled),
  };
}

export async function fetchPolicies(projectId?: string): Promise<DefensePolicy[]> {
  const url = projectId
    ? `${API_BASE}/defense-policies?project_id=${projectId}`
    : `${API_BASE}/defense-policies`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải danh mục chính sách"));
  const data = await res.json();
  const items = Array.isArray(data.items) ? data.items : [];
  return items.map((item: DefensePolicy & { enabled?: boolean }) =>
    normalizePolicyResponse(item),
  );
}

export async function seedDefaultPolicies(projectId: string): Promise<DefensePolicy[]> {
  const res = await fetch(
    `${API_BASE}/projects/${projectId}/defense-policies/seed-defaults`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi khởi tạo chính sách mặc định"));
  const data = await res.json();
  const items = Array.isArray(data.items) ? data.items : [];
  return items.map((item: DefensePolicy & { enabled?: boolean }) =>
    normalizePolicyResponse(item),
  );
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
    body: JSON.stringify({
      name: policy.name,
      event_type: policy.event_type,
      action_type: policy.action_type,
      target_params: policy.target_params ?? {},
      cooldown_seconds: policy.cooldown_seconds ?? 300,
      block_duration_seconds: policy.block_duration_seconds ?? 1800,
      is_auto_execute: policy.is_auto_execute ?? true,
      enabled: policy.is_active ?? true,
    }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tạo chính sách phòng thủ"));
  return normalizePolicyResponse(await res.json());
}

export async function updatePolicy(
  policyId: string,
  update: {
    name?: string;
    action_type?: string;
    target_params?: Record<string, unknown>;
    is_active?: boolean;
    is_auto_execute?: boolean;
    cooldown_seconds?: number;
    block_duration_seconds?: number;
  },
): Promise<DefensePolicy> {
  const body: Record<string, unknown> = {};
  if (update.name !== undefined) body.name = update.name;
  if (update.action_type !== undefined) body.action_type = update.action_type;
  if (update.target_params !== undefined) body.target_params = update.target_params;
  if (update.is_active !== undefined) body.enabled = update.is_active;
  if (update.is_auto_execute !== undefined) body.is_auto_execute = update.is_auto_execute;
  if (update.cooldown_seconds !== undefined) body.cooldown_seconds = update.cooldown_seconds;
  if (update.block_duration_seconds !== undefined) {
    body.block_duration_seconds = update.block_duration_seconds;
  }

  const res = await fetch(`${API_BASE}/defense-policies/${policyId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi cập nhật chính sách"));
  return normalizePolicyResponse(await res.json());
}

export async function deletePolicy(policyId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/defense-policies/${policyId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi xóa chính sách"));
}

export async function fetchWhitelist(projectId: string): Promise<IPWhitelist[]> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/ip-whitelist`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải danh sách an toàn"));
  const data = await res.json();
  const items = Array.isArray(data.items) ? data.items : [];
  return items.map((item: IPWhitelist & { ip_or_cidr?: string }) => ({
    ...item,
    cidr: String(item.cidr ?? item.ip_or_cidr ?? ""),
  }));
}

export async function createWhitelist(
  projectId: string,
  ipOrCidr: string,
  description?: string,
): Promise<IPWhitelist> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/ip-whitelist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ip_or_cidr: ipOrCidr,
      description,
    }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi thêm IP an toàn"));
  const item = (await res.json()) as IPWhitelist & { ip_or_cidr?: string };
  return {
    ...item,
    cidr: String(item.cidr ?? item.ip_or_cidr ?? ipOrCidr),
  };
}

export async function deleteWhitelist(whitelistId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/ip-whitelist/${whitelistId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi xóa IP an toàn"));
}

// ----------------------------------------------------
// Project & Node Settings API
// ----------------------------------------------------

export async function fetchProjectSettings(projectId: string): Promise<ProjectSettings> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/settings`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải cấu hình dự án"));
  return res.json();
}

export async function updateProjectSettings(
  projectId: string,
  profile: PresetProfileType,
  updatedBy = "operator@sentinelx.local",
): Promise<ProjectSettings> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active_profile: profile, updated_by: updatedBy }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi lưu cấu hình dự án"));
  return res.json();
}

export async function updateNodeSettings(
  nodeId: string,
  profile: PresetProfileType,
  updatedBy = "operator@sentinelx.local",
): Promise<ProjectSettings> {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active_profile: profile, updated_by: updatedBy }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi lưu cấu hình máy chủ"));
  return res.json();
}

// ----------------------------------------------------
// Load Balancer API
// ----------------------------------------------------

export async function fetchProjectLBStatus(projectId: string): Promise<ProjectLBStatus> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/load-balancer`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi tải trạng thái Load Balancer"));
  return res.json();
}

export async function updateProjectLBConfig(
  projectId: string,
  config: ProjectLBConfig,
): Promise<ProjectLBStatus> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/load-balancer`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi lưu cấu hình Load Balancer"));
  return res.json();
}

export async function switchProjectLBAlgorithm(
  projectId: string,
  algorithm: LBAlgorithmType,
): Promise<ProjectLBStatus> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/load-balancer/algorithm`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ algorithm }),
  });
  if (!res.ok) throw new Error(await extractApiError(res, "Lỗi đổi thuật toán"));
  return res.json();
}

export async function setProjectLBBackendState(
  projectId: string,
  nodeId: string,
  enabled: boolean,
  force = false,
): Promise<ProjectLBStatus> {
  const res = await fetch(
    `${API_BASE}/projects/${projectId}/load-balancer/backends/${nodeId}/state`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, force }),
    },
  );
  if (!res.ok) {
    throw new Error(await extractApiError(res, "Lỗi cập nhật trạng thái backend"));
  }
  return res.json();
}

export async function fetchAgentBundleInfo(): Promise<AgentBundleInfo> {
  const res = await fetch(`${API_BASE}/system/agent-bundle`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) {
    throw new Error(await extractApiError(res, "Lỗi kiểm tra gói cài đặt Agent"));
  }
  return res.json();
}
