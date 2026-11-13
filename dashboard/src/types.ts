/**
 * Type definitions matching SentinelX Controller REST & WebSocket contracts.
 */

export type NodeStatus = 'unenrolled' | 'online' | 'offline' | 'degraded';

export interface Project {
  id: string;
  name: string;
  description: string | null;
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
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  detected_at: string;
  details: Record<string, unknown>;
}

// ----------------------------------------------------
// Security, Incidents & Defense Contracts (M5 - M8)
// ----------------------------------------------------

export type IncidentStatus = 'DETECTED' | 'MITIGATING' | 'RESOLVED' | 'FALSE_POSITIVE';
export type DetectionSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Incident {
  id: string;
  project_id: string;
  title: string;
  status: IncidentStatus;
  severity: DetectionSeverity;
  started_at: string;
  resolved_at: string | null;
  summary: string | null;
  event_count: number;
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

export type DefenseActionStatus = 'PENDING' | 'SENT' | 'APPLIED' | 'FAILED' | 'REVERTED';

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
}

export interface DefensePolicy {
  id: string;
  name: string;
  event_type: string;
  action_type: string;
  target_params: Record<string, unknown>;
  cooldown_seconds: number;
  block_duration_seconds: number;
  is_auto_execute: boolean;
  is_active: boolean;
  created_at: string;
}

export interface IPWhitelist {
  id: string;
  project_id: string;
  cidr: string;
  description: string | null;
  created_at: string;
}
