import type {
  Project,
  Node,
  MetricSample,
  RealtimeMessage,
  Incident,
  IncidentDetail,
  DefenseAction,
  DefensePolicy,
  IPWhitelist,
} from "./types";

export const PROJ_PROD_ID = "77db55e0-1ebe-4b69-be7c-286519d21442";
export const PROJ_EDGE_ID = "8e3c00cf-d1f9-4dc7-95fa-569b33e95f21";
export const PROJ_DATA_ID = "11c586ac-f41b-4b6b-8440-dbb093da66a4";

export const MOCK_PROJECTS: Project[] = [
  {
    id: PROJ_PROD_ID,
    name: "Production Web Cluster",
    description:
      "Cụm máy chủ hạ tầng chính chạy tải dịch vụ thương mại điện tử",
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: PROJ_EDGE_ID,
    name: "Edge AI & Gateway",
    description: "Cụm tính toán biên, Reverse Proxy & Load Balancer phân tán",
    created_at: new Date(Date.now() - 20 * 86400000).toISOString(),
  },
  {
    id: PROJ_DATA_ID,
    name: "PostgreSQL Cluster",
    description: "Cụm lưu trữ PostgreSQL cho hạ tầng dữ liệu",
    created_at: new Date(Date.now() - 15 * 86400000).toISOString(),
  },
];

export const MOCK_NODES: Node[] = [
  {
    id: "node-edge-01",
    project_id: PROJ_EDGE_ID,
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
    cpuCores: 2,
    totalMemoryBytes: 2 * 1024 * 1024 * 1024,
    totalDiskBytes: 50 * 1024 * 1024 * 1024,
  },
  {
    id: "node-api-02",
    project_id: PROJ_PROD_ID,
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
    cpuCores: 4,
    totalMemoryBytes: 4 * 1024 * 1024 * 1024,
    totalDiskBytes: 80 * 1024 * 1024 * 1024,
  },
  {
    id: "node-db-03",
    project_id: PROJ_DATA_ID,
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
    cpuCores: 8,
    totalMemoryBytes: 8 * 1024 * 1024 * 1024,
    totalDiskBytes: 200 * 1024 * 1024 * 1024,
  },
  {
    id: "node-worker-04",
    project_id: PROJ_PROD_ID,
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
    cpuCores: 4,
    totalMemoryBytes: 2 * 1024 * 1024 * 1024,
    totalDiskBytes: 100 * 1024 * 1024 * 1024,
  },
  {
    id: "node-backup-05",
    project_id: PROJ_DATA_ID,
    hostname: "backup-storage-nas",
    ip_address: "10.0.2.35",
    status: "offline",
    last_seen: new Date(Date.now() - 180000).toISOString(),
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    cpuCores: 2,
    totalMemoryBytes: 4 * 1024 * 1024 * 1024,
    totalDiskBytes: 500 * 1024 * 1024 * 1024,
  },
  {
    id: "node-new-06",
    project_id: PROJ_EDGE_ID,
    hostname: "edge-inference-worker",
    ip_address: "10.0.1.40",
    status: "unenrolled",
    last_seen: null,
    created_at: new Date().toISOString(),
    cpuCores: 4,
    totalMemoryBytes: 4 * 1024 * 1024 * 1024,
    totalDiskBytes: 100 * 1024 * 1024 * 1024,
  },
];

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: "inc-syn-401",
    project_id: PROJ_PROD_ID,
    title: "Tấn công SYN Flood nhắm vào API Gateway",
    status: "MITIGATING",
    severity: "CRITICAL",
    started_at: new Date(Date.now() - 15 * 60000).toISOString(),
    resolved_at: null,
    summary:
      "Phát hiện bão gói tin SYN bất thường (tỷ lệ 88.5%). Đã kích hoạt lệnh nftables drop IP 203.0.113.195 (30m).",
    event_count: 5,
  },
  {
    id: "inc-scan-402",
    project_id: PROJ_EDGE_ID,
    title: "Dò quét cổng diện rộng (Port Scan Anomaly)",
    status: "DETECTED",
    severity: "HIGH",
    started_at: new Date(Date.now() - 6 * 60000).toISOString(),
    resolved_at: null,
    summary:
      "IP 198.51.100.42 quét dồn dập 48 cổng đích trong cửa sổ 5s. Đang chờ đối soát chính sách phòng thủ.",
    event_count: 3,
  },
  {
    id: "inc-udp-398",
    project_id: PROJ_EDGE_ID,
    title: "Bão lưu lượng UDP đột biến (Traffic Spike)",
    status: "RESOLVED",
    severity: "MEDIUM",
    started_at: new Date(Date.now() - 95 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 35 * 60000).toISOString(),
    summary:
      "Lưu lượng UDP từ 192.0.2.77 vượt ngưỡng 5000 pps. Đã hết thời hạn block và khôi phục lưu thông bình thường.",
    event_count: 8,
  },
  {
    id: "inc-cpu-385",
    project_id: PROJ_PROD_ID,
    title: "Quá tải CPU liên tục trên Celery Worker",
    status: "RESOLVED",
    severity: "HIGH",
    started_at: new Date(Date.now() - 180 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 120 * 60000).toISOString(),
    summary:
      "CPU đạt 94.2% trong 3 chu kỳ đo liên tiếp. Tiến trình worker đã tự ổn định sau khi giải phóng queue.",
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

export const MOCK_DEFENSE_ACTIONS: DefenseAction[] = [
  {
    id: "def-act-01",
    incident_id: "inc-syn-401",
    policy_id: "pol-01",
    node_id: "node-api-02",
    action_type: "BLOCK_IP_NFTABLES",
    target_ip: "203.0.113.195",
    command_payload: { duration_seconds: 1800, target: "203.0.113.195" },
    status: "APPLIED",
    agent_ack_at: new Date(Date.now() - 14 * 60000).toISOString(),
    error_message: null,
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
  {
    id: "def-act-02",
    incident_id: "inc-scan-402",
    policy_id: "pol-02",
    node_id: "node-edge-01",
    action_type: "BLOCK_IP_NFTABLES",
    target_ip: "198.51.100.42",
    command_payload: { duration_seconds: 900, target: "198.51.100.42" },
    status: "APPLIED",
    agent_ack_at: new Date(Date.now() - 5 * 60000).toISOString(),
    error_message: null,
    created_at: new Date(Date.now() - 6 * 60000).toISOString(),
  },
  {
    id: "def-act-03",
    incident_id: "inc-udp-398",
    policy_id: "pol-03",
    node_id: "node-edge-01",
    action_type: "BLOCK_IP_NFTABLES",
    target_ip: "192.0.2.77",
    command_payload: { duration_seconds: 600, target: "192.0.2.77" },
    status: "REVERTED",
    agent_ack_at: new Date(Date.now() - 94 * 60000).toISOString(),
    error_message: null,
    created_at: new Date(Date.now() - 95 * 60000).toISOString(),
  },
  {
    id: "def-act-04",
    incident_id: null,
    policy_id: null,
    node_id: "node-api-02",
    action_type: "BLOCK_IP_NFTABLES",
    target_ip: "127.0.0.1",
    command_payload: { duration_seconds: 300, target: "127.0.0.1" },
    status: "FAILED",
    agent_ack_at: new Date(Date.now() - 40 * 60000).toISOString(),
    error_message: "Local safety guardrail rejected: Target IP 127.0.0.1 is a loopback address",
    created_at: new Date(Date.now() - 41 * 60000).toISOString(),
  },
];

export const MOCK_POLICIES: DefensePolicy[] = [
  {
    id: "pol-01",
    name: "Chặn SYN Flood khẩn cấp",
    event_type: "syn_flood_detector",
    action_type: "BLOCK_IP_NFTABLES",
    target_params: { flags: "timeout" },
    cooldown_seconds: 60,
    block_duration_seconds: 1800,
    is_auto_execute: true,
    is_active: true,
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
  },
  {
    id: "pol-02",
    name: "Khóa IP trinh sát quét cổng",
    event_type: "port_scan_detector",
    action_type: "BLOCK_IP_NFTABLES",
    target_params: { flags: "timeout" },
    cooldown_seconds: 120,
    block_duration_seconds: 900,
    is_auto_execute: true,
    is_active: true,
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
  },
  {
    id: "pol-03",
    name: "Hạn chế bão lưu lượng UDP",
    event_type: "traffic_spike_detector",
    action_type: "RATE_LIMIT",
    target_params: { limit_pps: 1000 },
    cooldown_seconds: 60,
    block_duration_seconds: 600,
    is_auto_execute: false,
    is_active: true,
    created_at: new Date(Date.now() - 8 * 86400000).toISOString(),
  },
  {
    id: "pol-04",
    name: "Khởi động lại Worker khi tràn CPU",
    event_type: "cpu_saturation_detector",
    action_type: "RESTART_SERVICE",
    target_params: { service_name: "celery-worker" },
    cooldown_seconds: 300,
    block_duration_seconds: 0,
    is_auto_execute: false,
    is_active: false,
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
  },
];

export const MOCK_WHITELIST: IPWhitelist[] = [
  {
    id: "wl-01",
    project_id: PROJ_PROD_ID,
    cidr: "192.168.1.0/24",
    description: "Mạng LAN nội bộ phòng IT & Admin",
    created_at: new Date(Date.now() - 12 * 86400000).toISOString(),
  },
  {
    id: "wl-02",
    project_id: PROJ_PROD_ID,
    cidr: "10.0.0.0/8",
    description: "VPC Private Cloud Subnet",
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
  },
  {
    id: "wl-03",
    project_id: PROJ_EDGE_ID,
    cidr: "172.16.0.0/12",
    description: "Docker Bridge & Internal Overlay",
    created_at: new Date(Date.now() - 8 * 86400000).toISOString(),
  },
];

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
