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
