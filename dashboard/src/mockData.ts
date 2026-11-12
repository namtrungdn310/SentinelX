import type { Project, Node, MetricSample, RealtimeMessage, Incident, IncidentDetail } from "./types";

export const MOCK_PROJECTS: Project[] = [
  {
    id: "proj-prod-01",
    name: "Production Web Cluster",
    description:
      "Cụm máy chủ hạ tầng chính chạy tải dịch vụ thương mại điện tử",
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: "proj-edge-02",
    name: "Edge AI & Gateway",
    description: "Cụm tính toán biên, Reverse Proxy & Load Balancer phân tán",
    created_at: new Date(Date.now() - 20 * 86400000).toISOString(),
  },
  {
    id: "proj-data-03",
    name: "PostgreSQL Cluster",
    description: "Cụm lưu trữ PostgreSQL cho hạ tầng dữ liệu",
    created_at: new Date(Date.now() - 15 * 86400000).toISOString(),
  },
];

export const MOCK_NODES: Node[] = [
  {
    id: "node-edge-01",
    project_id: "proj-edge-02",
    hostname: "edge-ingress-sg01",
    ip_address: "10.0.1.10",
    status: "online",
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    latestCpu: 26.4,
    latestMemory: 48.2,
    latestDisk: 32.5,
    latestRxBytes: 18450000,
    latestTxBytes: 14200000,
  },
  {
    id: "node-api-02",
    project_id: "proj-prod-01",
    hostname: "api-gateway-node",
    ip_address: "10.0.1.15",
    status: "online",
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 9 * 86400000).toISOString(),
    latestCpu: 64.8,
    latestMemory: 72.1,
    latestDisk: 45.0,
    latestRxBytes: 42100000,
    latestTxBytes: 68900000,
  },
  {
    id: "node-db-03",
    project_id: "proj-data-03",
    hostname: "pg-primary-cluster",
    ip_address: "10.0.2.20",
    status: "degraded",
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 8 * 86400000).toISOString(),
    latestCpu: 18.2,
    latestMemory: 86.5,
    latestDisk: 61.2,
    latestRxBytes: 8500000,
    latestTxBytes: 6200000,
  },
  {
    id: "node-worker-04",
    project_id: "proj-prod-01",
    hostname: "worker-celery-pool",
    ip_address: "10.0.1.25",
    status: "online",
    last_seen: new Date().toISOString(),
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    latestCpu: 78.4,
    latestMemory: 55.0,
    latestDisk: 28.0,
    latestRxBytes: 12400000,
    latestTxBytes: 9800000,
  },
  {
    id: "node-backup-05",
    project_id: "proj-data-03",
    hostname: "backup-storage-nas",
    ip_address: "10.0.2.35",
    status: "offline",
    last_seen: new Date(Date.now() - 180000).toISOString(),
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
  },
  {
    id: "node-new-06",
    project_id: "proj-edge-02",
    hostname: "edge-inference-worker",
    ip_address: "10.0.1.40",
    status: "unenrolled",
    last_seen: null,
    created_at: new Date().toISOString(),
  },
];

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: "inc-syn-401",
    project_id: "proj-prod-01",
    title: "Tấn công SYN Flood nhắm vào API Gateway",
    status: "MITIGATING",
    severity: "CRITICAL",
    started_at: new Date(Date.now() - 15 * 60000).toISOString(),
    resolved_at: null,
    summary: "Phát hiện bão gói tin SYN bất thường (tỷ lệ 88.5%). Đã kích hoạt lệnh nftables drop IP 203.0.113.195 (30m).",
    event_count: 5,
  },
  {
    id: "inc-scan-402",
    project_id: "proj-edge-02",
    title: "Dò quét cổng diện rộng (Port Scan Anomaly)",
    status: "DETECTED",
    severity: "HIGH",
    started_at: new Date(Date.now() - 6 * 60000).toISOString(),
    resolved_at: null,
    summary: "IP 198.51.100.42 quét dồn dập 48 cổng đích trong cửa sổ 5s. Đang chờ đối soát chính sách phòng thủ.",
    event_count: 3,
  },
  {
    id: "inc-udp-398",
    project_id: "proj-edge-02",
    title: "Bão lưu lượng UDP đột biến (Traffic Spike)",
    status: "RESOLVED",
    severity: "MEDIUM",
    started_at: new Date(Date.now() - 95 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 35 * 60000).toISOString(),
    summary: "Lưu lượng UDP từ 192.0.2.77 vượt ngưỡng 5000 pps. Đã hết thời hạn block và khôi phục lưu thông bình thường.",
    event_count: 8,
  },
  {
    id: "inc-cpu-385",
    project_id: "proj-prod-01",
    title: "Quá tải CPU liên tục trên Celery Worker",
    status: "RESOLVED",
    severity: "HIGH",
    started_at: new Date(Date.now() - 180 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 120 * 60000).toISOString(),
    summary: "CPU đạt 94.2% trong 3 chu kỳ đo liên tiếp. Tiến trình worker đã tự ổn định sau khi giải phóng queue.",
    event_count: 3,
  },
];

export const MOCK_INCIDENT_DETAILS: Record<string, IncidentDetail> = {
  "inc-syn-401": {
    ...MOCK_INCIDENTS[0],
    events: [
      {
        id: "ev-syn-01",
        incident_id: "inc-syn-401",
        node_id: "node-api-02",
        detector_name: "syn_flood_detector",
        severity: "CRITICAL",
        attacker_ip: "203.0.113.195",
        confidence_score: 0.95,
        details: {
          syn_count: 520,
          ack_count: 4,
          syn_ratio: 0.99,
          targeted_ports: [80, 443],
        },
        detected_at: new Date(Date.now() - 14 * 60000).toISOString(),
      },
      {
        id: "ev-syn-02",
        incident_id: "inc-syn-401",
        node_id: "node-api-02",
        detector_name: "syn_flood_detector",
        severity: "CRITICAL",
        attacker_ip: "203.0.113.195",
        confidence_score: 0.98,
        details: {
          syn_count: 610,
          ack_count: 2,
          syn_ratio: 0.99,
          targeted_ports: [80, 443],
        },
        detected_at: new Date(Date.now() - 12 * 60000).toISOString(),
      },
    ],
  },
  "inc-scan-402": {
    ...MOCK_INCIDENTS[1],
    events: [
      {
        id: "ev-scan-01",
        incident_id: "inc-scan-402",
        node_id: "node-edge-01",
        detector_name: "port_scan_detector",
        severity: "HIGH",
        attacker_ip: "198.51.100.42",
        confidence_score: 0.88,
        details: {
          scanned_port_count: 48,
          targeted_ports: [22, 80, 443, 3306, 5432, 8080],
        },
        detected_at: new Date(Date.now() - 6 * 60000).toISOString(),
      },
    ],
  },
};

export function generateMockTelemetryHistory(
  node: Node,
  points = 30,
): MetricSample[] {
  const samples: MetricSample[] = [];
  const now = Date.now();
  const stepMs = 5000;
  const baseCpu = node.latestCpu ?? 20;
  const baseMem = node.latestMemory ?? 45;
  const baseDisk = node.latestDisk ?? 30;

  for (let i = points - 1; i >= 0; i--) {
    const time = new Date(now - i * stepMs).toISOString();
    const noiseCpu = (Math.sin(i / 3) + Math.random() * 0.4 - 0.2) * 8;
    const noiseMem = (Math.cos(i / 4) + Math.random() * 0.3 - 0.15) * 4;
    samples.push({
      observed_at: time,
      cpu_percent: Math.min(100, Math.max(0, Number((baseCpu + noiseCpu).toFixed(1)))),
      memory_percent: Math.min(100, Math.max(0, Number((baseMem + noiseMem).toFixed(1)))),
      disk_percent: baseDisk,
      network_rx_bytes: Math.floor(Math.random() * 5000000) + 1000000,
      network_tx_bytes: Math.floor(Math.random() * 3000000) + 500000,
    });
  }
  return samples;
}

export const MOCK_INITIAL_EVENTS: RealtimeMessage[] = [
  {
    event: "metric_update",
    data: {
      node_id: "node-edge-01",
      samples: [
        {
          observed_at: new Date(Date.now() - 10000).toISOString(),
          cpu_percent: 26.4,
          memory_percent: 48.2,
          disk_percent: 32.5,
          network_rx_bytes: 18450000,
          network_tx_bytes: 14200000,
        },
      ],
      received_at: new Date(Date.now() - 10000).toISOString(),
    },
    timestamp: new Date(Date.now() - 10000).toISOString(),
  },
  {
    event: "metric_update",
    data: {
      node_id: "node-api-02",
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
    event: "system_alert",
    data: {
      node_id: "node-db-03",
      severity: "warning",
      message:
        "Cảnh báo: Bộ nhớ RAM máy chủ pg-primary-cluster vượt ngưỡng 85%",
    },
    timestamp: new Date(Date.now() - 75000).toISOString(),
  },
  {
    event: "node_enrolled",
    data: {
      node_id: "node-worker-04",
      hostname: "worker-celery-pool",
      message: "Agent đã hoàn tất chứng thực enrollment token thành công",
    },
    timestamp: new Date(Date.now() - 140000).toISOString(),
  },
];
