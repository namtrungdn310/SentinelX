/**
 * REST API Client for SentinelX Controller.
 */

import type { MetricQueryResponse, Node, Project } from "./types";

const API_BASE = "/api/v1";

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
