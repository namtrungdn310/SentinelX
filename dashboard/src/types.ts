/**
 * Type definitions matching SentinelX Controller REST & WebSocket contracts.
 */

export type NodeStatus = 'unenrolled' | 'online' | 'offline' | 'degraded';
export type LBAlgorithmType = 'round_robin' | 'least_in_flight';
export type NodeLBRoleType = 'standalone' | 'lb_backend';

export interface ProjectLBConfig {
  enabled: boolean;
  lb_url: string | null;
  algorithm: LBAlgorithmType;
  health_path: string;
  health_interval_seconds: number;
  failure_threshold: number;
  success_threshold: number;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  load_balancer?: ProjectLBConfig;
  created_at: string;
}

export interface Node {
  id: string;
  project_id: string;
  hostname: string;
  ip_address: string;
  status: NodeStatus;
  last_seen: string | null;
  created_at: string;
  lb_role?: NodeLBRoleType;
  lb_backend_port?: number;
  lb_health_path?: string | null;
  agent_capabilities?: Record<string, unknown>;
  // Dynamic fields populated from telemetry
  latestCpu?: number;
  latestMemory?: number;
  latestDisk?: number;
  latestRxBytes?: number;
  latestTxBytes?: number;
  // Hardware specifications (capacity basis)
  cpuCores?: number;
  totalMemoryBytes?: number;
  totalDiskBytes?: number;
}

export interface MetricSample {
  observed_at: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number | null;
  network_tx_bytes: number | null;
  network_rx_bytes: number | null;
}

export interface MetricQueryResponse {
  node_id: string;
  count: number;
  samples: MetricSample[];
}

export interface RealtimeMessage {
  event: 'metric_update' | 'node_status' | 'pong' | string;
  data: {
    node_id?: string;
    samples?: MetricSample[];
    received_at?: string;
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface DetectionEvent {
  id: string;
  node_id: string;
  detector_name: string;
  severity: 'MEDIUM' | 'HIGH' | 'CRITICAL';
  detected_at: string;
  details: Record<string, unknown>;
}

// ----------------------------------------------------
// Security, Incidents & Defense Contracts (M5 - M8)
// ----------------------------------------------------

export type IncidentStatus = 'DETECTED' | 'MITIGATING' | 'RESOLVED' | 'FALSE_POSITIVE';
export type IncidentDefenseStatus = 'DELIVERY_FAILED' | 'EXECUTION_FAILED';
export type DetectionSeverity = 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Incident {
  id: string;
  project_id: string;
  node_id?: string | null;
  title: string;
  status: IncidentStatus;
  severity: DetectionSeverity;
  started_at: string;
  resolved_at: string | null;
  summary: string | null;
  defense_status?: IncidentDefenseStatus | null;
  event_count: number;
  attacker_ip?: string | null;
  targeted_ports?: number[];
  targeted_service?: string | null;
}

export interface DetectionEventResponse {
  id: string;
  incident_id?: string | null;
  node_id: string;
  detector_name: string;
  severity: DetectionSeverity;
  attacker_ip?: string | null;
  confidence_score: number;
  details: Record<string, unknown>;
  detected_at: string;
}

export interface IncidentDetail extends Incident {
  events: DetectionEventResponse[];
}

export type DefenseActionStatus =
  | 'PENDING'
  | 'SENT'
  | 'APPLIED'
  | 'FAILED'
  | 'REVERTED'
  | 'SIMULATED'
  | 'SKIPPED'
  | 'EXPIRED'
  | 'CANCELLED';

export interface DefenseAction {
  id: string;
  incident_id: string | null;
  policy_id: string | null;
  node_id: string;
  action_type: string;
  target_ip: string | null;
  command_payload: Record<string, unknown>;
  status: DefenseActionStatus;
  agent_ack_at: string | null;
  error_message: string | null;
  created_at: string;
  applied_at?: string | null;
  effective_until?: string | null;
}

export interface DefensePolicy {
  id: string;
  project_id?: string;
  name: string;
  event_type: string;
  action_type: string;
  target_params: Record<string, unknown>;
  cooldown_seconds: number;
  block_duration_seconds: number;
  is_auto_execute: boolean;
  is_active: boolean;
  priority?: number;
  created_at?: string;
}

export interface IPWhitelist {
  id: string;
  project_id: string;
  cidr: string;
  description: string | null;
  created_at: string;
}

export type PresetProfileType = "balanced" | "high_sensitivity" | "resource_saving";

export interface TelemetryDetectionPreset {
  id: PresetProfileType;
  name: string;
  tagline: string;
  description: string;
  recommendedFor: string;
  badgeTone: "ok" | "warn" | "medium";
  telemetry_interval_seconds: number;
  consecutive_samples: number;
  cpu_overload_window_seconds: number;
  memory_overload_window_seconds: number;
  disk_overload_window_seconds: number;
  network_window_seconds: number;
  network_step_seconds: number;
  port_scan_threshold_ports: number;
  syn_flood_min_syn: number;
  syn_ack_ratio: number;
  agent_cpu_impact: string;
  network_overhead: string;
}

export interface ProjectSettings {
  project_id: string;
  active_profile: PresetProfileType;
  updated_at: string;
  updated_by: string;
}

export interface LBBackendRuntime {
  name: string;
  url: string;
  node_id: string | null;
  weight?: number;
  health_path: string | null;
  is_healthy: boolean;
  admin_enabled: boolean;
  health_state: string;
  in_flight: number;
  total_requests: number;
  success_requests: number;
  error_requests: number;
  consecutive_successes: number;
  consecutive_failures: number;
  last_health_check_at: string | null;
  last_health_status_code?: number | null;
  last_health_error: string | null;
  flapping_detected?: boolean;
}

export interface ProjectLBStatus {
  project_id: string;
  enabled: boolean;
  lb_url: string | null;
  algorithm: LBAlgorithmType;
  reachable: boolean;
  sync_status: 'disabled' | 'synced' | 'unreachable' | 'error' | string;
  sync_message: string | null;
  health_check: {
    enabled: boolean;
    path: string;
    interval_seconds: number;
    failure_threshold: number;
    success_threshold: number;
  };
  total_backends: number;
  healthy_backends: number;
  routable_backends: number;
  admin_disabled_backends: number;
  total_in_flight: number;
  total_requests: number;
  total_success: number;
  total_errors: number;
  backends: LBBackendRuntime[];
}

