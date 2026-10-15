import type { Project, Node, MetricSample, RealtimeMessage } from './types';

export const MOCK_PROJECTS: Project[] = [
  {
    id: 'proj-prod-01',
    name: 'Production Web Cluster',
    description: 'Cụm máy chủ hạ tầng chính chạy tải dịch vụ thương mại điện tử',
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: 'proj-edge-02',
    name: 'Edge AI & Gateway',
    description: 'Cụm tính toán biên, Reverse Proxy & Load Balancer phân tán',
    created_at: new Date(Date.now() - 20 * 86400000).toISOString(),
  },
  {
    id: 'proj-data-03',
    name: 'Database & Cache Layer',
    description: 'Cụm lưu trữ PostgreSQL Primary & Redis In-Memory Cache',
    created_at: new Date(Date.now() - 15 * 86400000).toISOString(),
  },
];

export const MOCK_NODES: Node[] = [
  {
    id: 'node-edge-01',
    project_id: 'proj-edge-02',
    hostname: 'edge-ingress-sg01',
    ip_address: '10.0.1.10',
    status: 'online',
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    latestCpu: 26.4,
    latestMemory: 48.2,
    latestDisk: 32.5,
    latestRxBytes: 18450000,
    latestTxBytes: 14200000,
  },
  {
    id: 'node-api-02',
    project_id: 'proj-prod-01',
    hostname: 'api-gateway-node',
    ip_address: '10.0.1.15',
    status: 'online',
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 9 * 86400000).toISOString(),
    latestCpu: 64.8,
    latestMemory: 72.1,
    latestDisk: 45.0,
    latestRxBytes: 42100000,
    latestTxBytes: 68900000,
  },
  {
    id: 'node-db-03',
    project_id: 'proj-data-03',
    hostname: 'pg-primary-cluster',
    ip_address: '10.0.2.20',
    status: 'online',
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 8 * 86400000).toISOString(),
    latestCpu: 81.5,
    latestMemory: 88.6,
    latestDisk: 76.4,
    latestRxBytes: 54300000,
    latestTxBytes: 112500000,
  },
  {
    id: 'node-worker-04',
    project_id: 'proj-prod-01',
    hostname: 'worker-celery-pool',
    ip_address: '10.0.3.12',
    status: 'online',
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    latestCpu: 38.2,
    latestMemory: 51.4,
    latestDisk: 28.0,
    latestRxBytes: 9400000,
    latestTxBytes: 6100000,
  },
  {
    id: 'node-backup-05',
    project_id: 'proj-prod-01',
    hostname: 'backup-dr-vault',
    ip_address: '10.0.4.8',
    status: 'unenrolled',
    last_seen: null,
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
    latestCpu: undefined,
    latestMemory: undefined,
    latestDisk: undefined,
    latestRxBytes: 0,
    latestTxBytes: 0,
  },
];

export function generateMockTelemetryHistory(node: Node, count = 30): MetricSample[] {
  const baseCpu = node.latestCpu ?? 35;
  const baseMem = node.latestMemory ?? 50;
  const samples: MetricSample[] = [];
  const now = Date.now();

  for (let i = count - 1; i >= 0; i--) {
    const timestamp = new Date(now - i * 10000).toISOString();
    // Generate realistic wave curve using harmonic sine + small variance
    const cpuOffset = Math.sin((i / 4) + (node.hostname.charCodeAt(0) % 10)) * 12 + ((i % 3) - 1) * 3;
    const memOffset = Math.cos(i / 6) * 6 + ((i % 2) - 0.5) * 1.5;

    const cpuVal = Math.round(Math.max(5, Math.min(98, baseCpu + cpuOffset)) * 10) / 10;
    const memVal = Math.round(Math.max(10, Math.min(99, baseMem + memOffset)) * 10) / 10;

    samples.push({
      observed_at: timestamp,
      cpu_percent: cpuVal,
      memory_percent: memVal,
      disk_percent: node.latestDisk ?? 40,
      network_rx_bytes: (node.latestRxBytes ?? 1000000) + Math.round(Math.sin(i) * 2000000),
      network_tx_bytes: (node.latestTxBytes ?? 1000000) + Math.round(Math.cos(i) * 3000000),
    });
  }

  return samples;
}

export const MOCK_INITIAL_EVENTS: RealtimeMessage[] = [
  {
    event: 'metric_update',
    data: {
      node_id: 'node-edge-01',
      samples: [
        {
          observed_at: new Date(Date.now() - 2000).toISOString(),
          cpu_percent: 26.4,
          memory_percent: 48.2,
          disk_percent: 32.5,
          network_rx_bytes: 18450000,
          network_tx_bytes: 14200000,
        },
      ],
      received_at: new Date(Date.now() - 2000).toISOString(),
    },
    timestamp: new Date(Date.now() - 2000).toISOString(),
  },
  {
    event: 'heartbeat',
    data: {
      node_id: 'node-db-03',
      hostname: 'pg-primary-cluster',
      status: 'healthy',
      uptime_seconds: 3628800,
      load_avg: [1.82, 1.45, 1.2],
    },
    timestamp: new Date(Date.now() - 15000).toISOString(),
  },
  {
    event: 'metric_update',
    data: {
      node_id: 'node-api-02',
      samples: [
        {
          observed_at: new Date(Date.now() - 32000).toISOString(),
          cpu_percent: 64.8,
          memory_percent: 72.1,
          disk_percent: 45.0,
          network_rx_bytes: 42100000,
          network_tx_bytes: 68900000,
        },
      ],
      received_at: new Date(Date.now() - 32000).toISOString(),
    },
    timestamp: new Date(Date.now() - 32000).toISOString(),
  },
  {
    event: 'system_alert',
    data: {
      node_id: 'node-db-03',
      severity: 'warning',
      message: 'Cảnh báo: Bộ nhớ RAM máy chủ pg-primary-cluster vượt ngưỡng 85%',
    },
    timestamp: new Date(Date.now() - 75000).toISOString(),
  },
  {
    event: 'node_enrolled',
    data: {
      node_id: 'node-worker-04',
      hostname: 'worker-celery-pool',
      message: 'Agent đã hoàn tất chứng thực enrollment token thành công',
    },
    timestamp: new Date(Date.now() - 140000).toISOString(),
  },
];
