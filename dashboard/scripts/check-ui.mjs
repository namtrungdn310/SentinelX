import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

// Render smoke checks run without a Controller, database, browser or extra packages.
// They verify route rendering, wire ID mapping, sample order and data truthfulness.
const root = fileURLToPath(new URL("../", import.meta.url));
const cacheDir = await mkdtemp(join(tmpdir(), "sentinelx-ui-check-"));
const server = await createServer({
    root,
    cacheDir,
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
});
globalThis.window = {
    location: { hash: "#overview", origin: "http://dashboard.test" },
};
let passed = 0;
const check = (name, test) => {
    test();
    passed++;
    console.log("PASS", name);
};
try {
    const [originalMark, brandMark, favicon, entryHtml, themeCss, appCss] = await Promise.all([
        "public/sentinelx-mark-v1.svg",
        "public/sentinelx-mark-v2.svg",
        "public/sentinelx-favicon-v2.svg",
        "index.html",
        "src/index.css",
        "src/App.css",
    ].map((file) => readFile(join(root, file), "utf8")));
    check("Logo recolor preserves geometry and matches console colors", () => {
        const paths = (svg) => [...svg.matchAll(/\bd="([^"]+)"/g)].map((match) => match[1]);
        assert.equal(paths(originalMark).length, 2);
        assert.deepEqual(paths(brandMark), paths(originalMark));
        assert.deepEqual(paths(favicon), paths(originalMark));
        for (const [token, color] of [["action-primary", "#25282D"], ["brand-cyan", "#147D73"]]) {
            assert.ok(brandMark.includes(`fill="${color}"`));
            assert.ok(favicon.includes(`fill="${color}"`));
            assert.ok(themeCss.toLowerCase().includes(`--${token}: ${color.toLowerCase()}`));
        }
        assert.ok(!/linearGradient|filter=/.test(brandMark));
        assert.match(appCss, /\.brand-x\s*\{\s*color:\s*var\(--brand-cyan\)/);
        assert.match(favicon, /prefers-color-scheme:\s*dark/);
        assert.match(entryHtml, /href="%BASE_URL%sentinelx-favicon-v2\.svg"/);
        assert.ok(!entryHtml.includes("sentinelx-mark-v1"));
    });
    const { App } = await server.ssrLoadModule("/src/App.tsx");
    const { TelemetryChart } = await server.ssrLoadModule(
        "/src/components/TelemetryChart.tsx",
    );
    const { NodeMatrix } = await server.ssrLoadModule(
        "/src/components/NodeMatrix.tsx",
    );
    const { KPICards } = await server.ssrLoadModule(
        "/src/components/KPICards.tsx",
    );
    const { NodeDetailModal } = await server.ssrLoadModule("/src/components/NodeDetailModal.tsx");
    const { classifyIncidentHandling, nodeHealth, nodeHealthLabel, validateManualBlockIp, validateWhitelistCidr } = await server.ssrLoadModule("/src/presentation.ts");
    const { filterEvents, eventLabel, eventMatchesCategory, formatRealtimeMessage, mergeEvents } = await server.ssrLoadModule("/src/events.ts");
    const { LiveEventStream } = await server.ssrLoadModule("/src/components/LiveEventStream.tsx");
    const { IncidentsView } = await server.ssrLoadModule("/src/components/IncidentsView.tsx");
    const { IncidentDetailModal } = await server.ssrLoadModule("/src/components/IncidentDetailModal.tsx");
    const { DefenseView } = await server.ssrLoadModule("/src/components/DefenseView.tsx");
    const { ManualBlockModal } = await server.ssrLoadModule("/src/components/ManualBlockModal.tsx");
    const { PoliciesView } = await server.ssrLoadModule("/src/components/PoliciesView.tsx");
    const { EditPolicyModal } = await server.ssrLoadModule("/src/components/EditPolicyModal.tsx");
    const { AddWhitelistModal } = await server.ssrLoadModule("/src/components/AddWhitelistModal.tsx");
    const { SettingsView } = await server.ssrLoadModule("/src/components/SettingsView.tsx");
    const { LoadBalancerView } = await server.ssrLoadModule("/src/components/LoadBalancerView.tsx");
    const { LBPoolPickerModal } = await server.ssrLoadModule("/src/components/LBPoolPickerModal.tsx");
    const { AddProjectModal } = await server.ssrLoadModule("/src/components/AddProjectModal.tsx");
    const { ProjectLBConfigModal } = await server.ssrLoadModule("/src/components/ProjectLBConfigModal.tsx");
    const { AddNodeModal } = await server.ssrLoadModule("/src/components/AddNodeModal.tsx");
    const { AgentInstallSection } = await server.ssrLoadModule("/src/components/AgentInstallSection.tsx");
    const { buildLinuxBundleCommand, buildDevUvCommand } = await server.ssrLoadModule("/src/agentInstall.ts");
    const { SecurityToast } = await server.ssrLoadModule("/src/components/SecurityToast.tsx");
    const { InfrastructureOverview } = await server.ssrLoadModule("/src/components/InfrastructureOverview.tsx");
    const { TELEMETRY_PRESETS } = await server.ssrLoadModule("/src/presets.ts");

    const TEST_PROJECTS = [
        {
            id: "proj-prod-01",
            name: "Production Web Cluster",
            description: "Main production ingress cluster",
            created_at: "2026-10-15T08:00:00Z",
            load_balancer: {
                enabled: true,
                algorithm: "round_robin",
                listen_port: 8080,
                lb_url: "http://192.168.1.5:8080",
                health_path: "/health",
                probe_interval_seconds: 10,
                failure_threshold: 3,
                recovery_threshold: 2,
                backend_node_ids: ["node-api-01", "node-api-02"],
            },
        },
        {
            id: "proj-staging-01",
            name: "Staging Env",
            description: null,
            created_at: "2026-10-16T08:00:00Z",
            load_balancer: {
                enabled: false,
                algorithm: "round_robin",
                listen_port: 8080,
                lb_url: null,
                health_path: "/health",
                probe_interval_seconds: 10,
                failure_threshold: 3,
                recovery_threshold: 2,
                backend_node_ids: [],
            },
        },
        {
            id: "proj-db-01",
            name: "Database Cluster",
            description: "PostgreSQL cluster",
            created_at: "2026-10-17T08:00:00Z",
            load_balancer: {
                enabled: false,
                algorithm: "round_robin",
                listen_port: 8080,
                lb_url: null,
                health_path: "/health",
                probe_interval_seconds: 10,
                failure_threshold: 3,
                recovery_threshold: 2,
                backend_node_ids: [],
            },
        },
    ];
    const TEST_NODES = [
        {
            id: "node-api-01",
            project_id: "proj-prod-01",
            hostname: "api-gateway-node",
            ip_address: "10.0.1.15",
            os_info: "Ubuntu 24.04",
            status: "online",
            last_seen: "2026-11-24T10:00:00Z",
            created_at: "2026-10-15T08:05:00Z",
            lb_role: "lb_backend",
            agent_capabilities: {
                hardware: {
                    cpu_cores: 8,
                    total_memory_bytes: 16 * 1024 ** 3,
                    total_disk_bytes: 200 * 1024 ** 3,
                },
            },
            latestCpu: 42.5,
            latestMemory: 58.2,
            latestDisk: 35.0,
            latestRxBytes: 120000,
            latestTxBytes: 98000,
        },
        {
            id: "node-api-02",
            project_id: "proj-prod-01",
            hostname: "worker-celery-pool",
            ip_address: "10.0.1.25",
            os_info: "Ubuntu 24.04",
            status: "online",
            last_seen: "2026-11-24T10:00:00Z",
            created_at: "2026-10-15T08:10:00Z",
            lb_role: "lb_backend",
            latestCpu: 68.0,
            latestMemory: 74.0,
            latestDisk: 41.0,
            latestRxBytes: 85000,
            latestTxBytes: 64000,
        },
        {
            id: "node-db-01",
            project_id: "proj-db-01",
            hostname: "pg-primary-cluster",
            ip_address: "10.0.2.10",
            os_info: "Ubuntu 24.04",
            status: "online",
            last_seen: "2026-11-24T10:00:00Z",
            created_at: "2026-10-17T08:05:00Z",
            lb_role: "standalone",
            latestCpu: 31.0,
            latestMemory: 62.0,
            latestDisk: 55.0,
        },
        {
            id: "node-db-02",
            project_id: "proj-db-01",
            hostname: "backup-storage-nas",
            ip_address: "10.0.2.20",
            os_info: "Ubuntu 24.04",
            status: "offline",
            last_seen: "2026-11-24T09:00:00Z",
            created_at: "2026-10-17T08:10:00Z",
            lb_role: "standalone",
        },
    ];
    const TEST_POLICIES = [
        {
            id: "pol-syn-01",
            project_id: "proj-prod-01",
            name: "TCP Flood / SYN Flood",
            event_type: "syn_flood_detector",
            action_type: "BLOCK_IP_NFTABLES",
            target_params: { threshold: 200 },
            is_auto_execute: true,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: true,
        },
        {
            id: "pol-scan-01",
            project_id: "proj-prod-01",
            name: "Chặn các IP quét cổng",
            event_type: "port_scan_detector",
            action_type: "BLOCK_IP_NFTABLES",
            target_params: { threshold: 15 },
            is_auto_execute: true,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: true,
        },
        {
            id: "pol-udp-01",
            project_id: "proj-prod-01",
            name: "UDP Flood / Traffic Spike",
            event_type: "udp_flood_detector",
            action_type: "BLOCK_IP_NFTABLES",
            target_params: { threshold: 30 },
            is_auto_execute: true,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: true,
        },
        {
            id: "pol-cpu-01",
            project_id: "proj-prod-01",
            name: "Quá tải CPU",
            event_type: "cpu_threshold_detector",
            action_type: "ALERT_ONLY",
            target_params: { threshold: 75 },
            is_auto_execute: false,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: false,
        },
        {
            id: "pol-mem-01",
            project_id: "proj-prod-01",
            name: "Quá tải RAM",
            event_type: "memory_exhaustion_detector",
            action_type: "RESTART_SERVICE",
            target_params: { service_name: "nginx" },
            is_auto_execute: true,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: true,
        },
        {
            id: "pol-disk-01",
            project_id: "proj-prod-01",
            name: "Đầy dung lượng ổ đĩa",
            event_type: "disk_full_detector",
            action_type: "ALERT_ONLY",
            target_params: { threshold: 85 },
            is_auto_execute: false,
            cooldown_seconds: 60,
            block_duration_seconds: 1800,
            is_active: false,
        },
    ];
    const TEST_INCIDENTS = [
        {
            id: "inc-syn-401",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "syn_flood_detector",
            status: "MITIGATING",
            severity: "CRITICAL",
            title: "Tấn công SYN Flood",
            summary: "IP: 203.0.113.195 · 750 pps (>= 200 pps)\nnftables: DROP 203.0.113.195 (thời hạn: 30 phút)",
            event_count: 3,
            opened_at: "2026-11-24T09:58:00Z",
            last_seen_at: "2026-11-24T09:59:00Z",
            resolved_at: null,
            defense_status: "EXECUTING",
            attacker_ip: "203.0.113.195",
        },
        {
            id: "inc-cpu-385",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "cpu_threshold_detector",
            status: "DETECTED",
            severity: "HIGH",
            title: "CPU vượt ngưỡng",
            summary: "CPU: 82.0% (>= 75.0%)",
            event_count: 1,
            opened_at: "2026-11-24T09:55:00Z",
            last_seen_at: "2026-11-24T09:55:00Z",
            resolved_at: null,
        },
        {
            id: "inc-disk-409",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "disk_full_detector",
            status: "DETECTED",
            severity: "HIGH",
            title: "Ổ đĩa gần đầy",
            summary: "Ổ đĩa /: 88.0% (>= 85.0%)",
            event_count: 1,
            opened_at: "2026-11-24T09:54:00Z",
            last_seen_at: "2026-11-24T09:54:00Z",
            resolved_at: null,
        },
        {
            id: "inc-mem-408",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "memory_exhaustion_detector",
            status: "DETECTED",
            severity: "HIGH",
            title: "RAM vượt ngưỡng",
            summary: "RAM: 87.5% (>= 85.0%)",
            event_count: 1,
            opened_at: "2026-11-24T09:53:00Z",
            last_seen_at: "2026-11-24T09:53:00Z",
            resolved_at: null,
            defense_status: "PENDING_EXECUTION",
        },
        {
            id: "inc-mem-405",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "memory_exhaustion_detector",
            status: "MITIGATING",
            severity: "CRITICAL",
            title: "Cạn kiệt RAM",
            summary: "RAM: 92.0% (>= 85.0%)\nservice: RESTART nginx",
            event_count: 2,
            opened_at: "2026-11-24T09:50:00Z",
            last_seen_at: "2026-11-24T09:52:00Z",
            resolved_at: null,
            defense_status: "EXECUTING",
        },
        {
            id: "inc-scan-402",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "port_scan_detector",
            status: "DETECTED",
            severity: "HIGH",
            title: "Quét cổng",
            summary: "IP: 198.51.100.42 · 48 cổng (TCP) (>= 15/10s)",
            event_count: 1,
            opened_at: "2026-11-24T09:48:00Z",
            last_seen_at: "2026-11-24T09:48:00Z",
            resolved_at: null,
            defense_status: "PENDING_EXECUTION",
            attacker_ip: "198.51.100.42",
        },
        {
            id: "inc-udp-395",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "udp_flood_detector",
            status: "MITIGATING",
            severity: "CRITICAL",
            title: "UDP Flood",
            summary: "IP: 198.51.100.77 · 180 pps (>= 30 pps)",
            event_count: 2,
            opened_at: "2026-11-24T09:45:00Z",
            last_seen_at: "2026-11-24T09:46:00Z",
            resolved_at: null,
            attacker_ip: "198.51.100.77",
        },
        {
            id: "inc-udp-398",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "udp_flood_detector",
            status: "DETECTED",
            severity: "CRITICAL",
            title: "UDP Flood bùng phát",
            summary: "IP: 198.51.100.77 · 5.420 pps (>= 30 pps) · 42.5 MB/s (>= 500.0 KB/s)",
            event_count: 1,
            opened_at: "2026-11-24T09:47:00Z",
            last_seen_at: "2026-11-24T09:47:00Z",
            resolved_at: null,
            attacker_ip: "198.51.100.77",
        },
        {
            id: "inc-syn-390",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "syn_flood_detector",
            status: "RESOLVED",
            severity: "CRITICAL",
            title: "SYN Flood đã xử lý",
            summary: "IP: 203.0.113.88 · đã chặn\nnftables: DROP 203.0.113.88 (thời hạn: 30 phút)",
            event_count: 3,
            opened_at: "2026-11-24T08:30:00Z",
            last_seen_at: "2026-11-24T08:32:00Z",
            resolved_at: "2026-11-24T09:00:00Z",
            defense_status: "EXECUTED",
            attacker_ip: "203.0.113.88",
        },
        {
            id: "inc-mem-389",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "memory_exhaustion_detector",
            status: "RESOLVED",
            severity: "CRITICAL",
            title: "RAM cao đã xử lý",
            summary: "RAM: 91.5% (>= 85.0%)\nservice: RESTART java",
            event_count: 2,
            opened_at: "2026-11-24T08:20:00Z",
            last_seen_at: "2026-11-24T08:21:00Z",
            resolved_at: "2026-11-24T08:25:00Z",
            defense_status: "EXECUTED",
        },
        {
            id: "inc-disk-391",
            project_id: "proj-prod-01",
            node_id: "node-api-01",
            incident_type: "disk_full_detector",
            status: "RESOLVED",
            severity: "HIGH",
            title: "Ổ đĩa đầy đã giải phóng",
            summary: "Ổ đĩa /tmp: 91.2% (>= 85.0%)",
            event_count: 1,
            opened_at: "2026-11-24T08:10:00Z",
            last_seen_at: "2026-11-24T08:10:00Z",
            resolved_at: "2026-11-24T08:15:00Z",
        },
        {
            id: "inc-cpu-382",
            project_id: "proj-prod-01",
            node_id: "node-api-02",
            incident_type: "cpu_threshold_detector",
            status: "RESOLVED",
            severity: "HIGH",
            title: "CPU quá tải đã hạ nhiệt",
            summary: "CPU: 88.0% (>= 75.0%)",
            event_count: 1,
            opened_at: "2026-11-24T08:00:00Z",
            last_seen_at: "2026-11-24T08:00:00Z",
            resolved_at: "2026-11-24T08:05:00Z",
        },
    ];
    const TEST_DEFENSE_ACTIONS = [
        {
            id: "act-01",
            node_id: "node-api-02",
            incident_id: "inc-syn-401",
            action_type: "BLOCK_IP_NFTABLES",
            target_ip: "203.0.113.195",
            command_payload: { duration_seconds: 1800, trigger_reason: "SYN Flood" },
            status: "APPLIED",
            triggered_by: "AUTO_POLICY",
            created_at: "2026-11-24T09:58:10Z",
            effective_until: "2099-01-01T00:00:00Z",
        },
        {
            id: "act-02",
            node_id: "node-api-01",
            incident_id: "inc-scan-402",
            action_type: "BLOCK_IP_NFTABLES",
            target_ip: "198.51.100.42",
            command_payload: { duration_seconds: 1800 },
            status: "PENDING",
            triggered_by: "AUTO_POLICY",
            created_at: "2026-11-24T09:48:10Z",
        },
        {
            id: "act-03",
            node_id: "node-api-02",
            incident_id: "inc-udp-395",
            action_type: "BLOCK_IP_NFTABLES",
            target_ip: "198.51.100.77",
            command_payload: { duration_seconds: 900 },
            status: "PENDING",
            triggered_by: "AUTO_POLICY",
            created_at: "2026-11-24T09:45:10Z",
        },
        {
            id: "act-04",
            node_id: "node-api-01",
            incident_id: "inc-mem-405",
            action_type: "RESTART_SERVICE",
            target_ip: null,
            command_payload: { service_name: "nginx" },
            status: "APPLIED",
            triggered_by: "AUTO_POLICY",
            created_at: "2026-11-24T09:50:10Z",
        },
    ];
    const TEST_WHITELIST = [
        {
            id: "wl-01",
            project_id: "proj-prod-01",
            cidr: "192.168.1.0/24",
            description: "LAN Subnet",
            created_at: "2026-10-15T08:00:00Z",
        },
    ];
    const node = TEST_NODES[0];
    const noop = () => {};

    assert.ok(Boolean(TELEMETRY_PRESETS.balanced));

    const authHtml = renderToStaticMarkup(createElement(App));
    check("App renders cleanly without mock data", () => {
        assert.ok(authHtml.includes("Sentinel"));
        assert.ok(!authHtml.includes("Dữ liệu mô phỏng"));
        assert.ok(!/NaN|undefined|Infinity/.test(authHtml));
    });

    check("Overview summarizes the fleet without duplicating telemetry or host inventory", () => {
        const overviewHtml = renderToStaticMarkup(
            createElement(InfrastructureOverview, {
                nodes: TEST_NODES,
                onSelectNode: noop,
                onOpenDetail: noop,
                onAddNode: noop,
            }),
        );
        assert.ok(overviewHtml.includes('aria-label="Tổng quan toàn cụm"'));
        assert.ok(overviewHtml.includes('aria-label="Máy chủ sử dụng tài nguyên nhiều nhất"'));
        assert.ok(overviewHtml.includes('aria-label="Máy chủ ổn định"'));
        assert.ok(!overviewHtml.includes('aria-label="Biểu đồ tài nguyên"'));
        assert.ok(!overviewHtml.includes('aria-label="Số mẫu dữ liệu"'));
        assert.ok(!overviewHtml.includes('id="host-fleet"'));
        assert.ok(!overviewHtml.includes('aria-label="Lọc sự kiện"'));
    });

    check("Telemetry is a single-host analysis view", () => {
        const metricsHtml = renderToStaticMarkup(
            createElement(TelemetryChart, {
                selectedNode: node,
                samples: [],
                isLoading: false,
            }),
        );
        assert.ok(metricsHtml.includes('aria-label="Biểu đồ tài nguyên"'));
    });
    const samples = [80, 20, 50].map((cpu, index) => ({
        observed_at: [
            "2026-10-16T10:02:00Z",
            "2026-10-16T10:00:00Z",
            "2026-10-16T10:01:00Z",
        ][index],
        cpu_percent: cpu,
        memory_percent: 60,
        disk_percent: null,
        network_rx_bytes: null,
        network_tx_bytes: null,
    }));
    const chart = renderToStaticMarkup(
        createElement(TelemetryChart, {
            selectedNode: node,
            samples,
            isLoading: false,
        }),
    );
    check("Chart sorts mixed REST / push samples chronologically", () => {
        assert.ok(chart.includes("<b>80.0%</b>"));
        const labels = [
            ...chart.matchAll(/class="chart-axis"[^>]*>([^<]+)</g),
        ].map((match) => match[1]);
        assert.ok(labels.length >= 7 && labels.length <= 10);
        assert.ok(chart.includes("Dùng phím mũi tên"));
    });
    check("Unavailable telemetry has an explicit empty state", () => {
        const html = renderToStaticMarkup(
            createElement(TelemetryChart, {
                selectedNode: node,
                samples: [],
                isLoading: false,
            }),
        );
        assert.ok(html.includes("Chưa có mẫu dữ liệu"));
    });
    check("Failed telemetry offers retry", () => {
        const html = renderToStaticMarkup(
            createElement(TelemetryChart, {
                selectedNode: node,
                samples: [],
                isLoading: false,
                error: "Test error",
                onRetry: noop,
            }),
        );
        assert.ok(html.includes('role="alert"'));
        assert.ok(html.includes("Thử lại"));
    });
    check("Health reflects memory, thresholds and enrollment", () => {
        assert.equal(
            nodeHealth({ ...node, latestCpu: 10, latestMemory: 90 }),
            "warn",
        );
        assert.equal(
            nodeHealth({ ...node, status: "unenrolled", latestCpu: 95 }),
            "unenrolled",
        );
        assert.equal(nodeHealth({ ...node, status: "offline" }), "crit");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: undefined }), "unknown");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: 75, latestMemory: 85 }), "ok");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: 75.1, latestMemory: 85 }), "warn");
    });
    check("Status labels reflect real node status and thresholds without synthetic degradation", () => {
        assert.equal(nodeHealthLabel({ ...node, status: "online", latestCpu: 20, latestMemory: 30 }), "Ổn định");
        assert.equal(nodeHealthLabel({ ...node, status: "online", latestCpu: 80, latestMemory: 30 }), "Vượt ngưỡng");
        assert.equal(nodeHealthLabel({ ...node, status: "unenrolled", latestCpu: 99 }), "Chờ đăng ký");
        assert.equal(nodeHealthLabel({ ...node, status: "offline", latestCpu: 99 }), "Mất kết nối");
    });
    check("Overview KPI separates host connectivity from active security incidents", () => {
        const htmlNoIncidents = renderToStaticMarkup(createElement(KPICards, {
            nodes: [{ ...node, status: "unenrolled" }],
            incidents: [],
            isLoading: false,
        }));
        assert.ok(htmlNoIncidents.includes("Máy chủ trực tuyến"));
        assert.ok(htmlNoIncidents.includes("1 chờ đăng ký"));
        assert.ok(htmlNoIncidents.includes("Sự cố đang mở"));
        assert.ok(!htmlNoIncidents.includes("Cần xử lý"));
        assert.ok(!htmlNoIncidents.includes("stat-attention"));

        const activeProdIncidents = TEST_INCIDENTS.filter((i) => i.project_id === TEST_PROJECTS[0].id);
        const withIncidents = renderToStaticMarkup(createElement(KPICards, {
            nodes: [node],
            incidents: activeProdIncidents,
            isLoading: false,
        }));
        assert.ok(withIncidents.includes("stat-attention"));
        assert.ok(withIncidents.includes("khẩn cấp"));
        assert.ok(withIncidents.includes("cao"));
    });
    const detection = { event: "detection_alert", timestamp: "2026-11-06T10:00:00Z", data: {
        id: "detection-1", node_id: node.id, severity: "CRITICAL", detector_name: "cpu_threshold_detector",
        details: { metric_name: "cpu_percent", current_value: 98, threshold_value: 95, consecutive_samples: 3 },
    }};
    check("Detection alerts show severity and resource details with text, and belong to Alert category", () => {
        const html = renderToStaticMarkup(createElement(LiveEventStream, { events: [detection], nodes: [node], isConnected: true }));
        assert.ok(html.includes("Khẩn cấp"));
        assert.ok(html.includes("CPU 98% ≥ 95%"));
        assert.ok(html.includes("3 mẫu liên tiếp"));
        assert.ok(html.includes("Bất thường tài nguyên"));
        assert.ok(html.includes('event-type warn'));
        assert.equal(eventMatchesCategory("detection_alert", "alert"), true);
        assert.deepEqual(filterEvents([detection], [node], "alert", "cpu_percent"), [detection]);
    });
    check("REST detection history merges with WebSocket replay by stable event ID", () => {
        const older = { ...detection, timestamp: "2026-11-06T09:00:00Z", data: { ...detection.data, id: "detection-2" } };
        const merged = mergeEvents([older, detection], [detection]);
        assert.deepEqual(merged, [detection, older]);
        assert.equal(mergeEvents(Array.from({ length: 100 }, (_, i) => ({ ...detection, data: { ...detection.data, id: String(i) } }))).length, 50);
    });
    const eventFixture = ["metric_update", "system_alert", "node_status", "heartbeat", "node_enrolled", "future_event"].map((event, i) => ({ event, timestamp: `2026-10-23T10:00:0${i}Z`, data: { node_id: node.id, message: "Thông tin thử nghiệm" } }));
    check("Event categories keep All exhaustive and filter without reordering or mutating", () => {
        assert.deepEqual(filterEvents(eventFixture, [node], "all", ""), eventFixture);
        assert.deepEqual(filterEvents(eventFixture, [node], "telemetry", ""), [eventFixture[0]]);
        assert.deepEqual(filterEvents(eventFixture, [node], "alert", ""), [eventFixture[1]]);
        assert.deepEqual(filterEvents(eventFixture, [node], "status", ""), eventFixture.slice(2, 5));
        assert.equal(eventMatchesCategory("future_event", "status"), false);
        assert.equal(eventLabel("future_event"), "Sự kiện khác");
        assert.equal(eventLabel("toString"), "Sự kiện khác");
    });
    check("Event search intersects category, readable label, raw ID, host and payload", () => {
        assert.equal(filterEvents(eventFixture, [node], "all", " CẢNH BÁO ")[0], eventFixture[1]);
        assert.equal(filterEvents(eventFixture, [node], "telemetry", "system_alert").length, 0);
        assert.equal(filterEvents(eventFixture, [node], "all", node.hostname.toUpperCase()).length, 6);
        assert.equal(filterEvents(eventFixture, [node], "all", "thử nghiệm").length, 6);
        assert.equal(filterEvents(eventFixture, [node], "all", "future_event")[0], eventFixture[5]);
    });
    check("Event stream defaults to All, exposes raw IDs and keeps source/state explicit", () => {
        const html = renderToStaticMarkup(createElement(LiveEventStream, { events: eventFixture, nodes: [node], isConnected: true }));
        assert.ok(html.includes('aria-pressed="true">Tất cả'));
        assert.ok(html.includes(">Cảnh báo<"));
        assert.ok(html.includes(">Thao tác<"));
        assert.ok(html.includes(">Kết nối<"));
        assert.ok(html.includes(">Mẫu dữ liệu<"));
        assert.ok(!html.includes("Dữ liệu mô phỏng"));
        assert.ok(html.includes("Sự kiện khác"));
        assert.ok(html.includes("future_event"));
        assert.ok(html.includes('class="event-controls"'));
    });
    check("Node filtering empty state is actionable", () => {
        const html = renderToStaticMarkup(
            createElement(NodeMatrix, {
                nodes: [],
                selectedNodeId: null,
                onSelectNode: noop,
                isLoading: false,
            }),
        );
        assert.ok(html.includes("Thử đổi từ khóa"));
    });
    check("Missing CPU / RAM is not displayed as 0% utilization", () => {
        const html = renderToStaticMarkup(
            createElement(KPICards, {
                nodes: [
                    { ...node, latestCpu: undefined, latestMemory: undefined },
                ],
                isLoading: false,
            }),
        );
        assert.ok(html.includes("Chưa có dữ liệu CPU"));
        assert.ok(html.includes("Chưa có dữ liệu RAM"));
    });
    check("Network deltas explain their scope without claiming throughput or cumulative totals", () => {
        const html = renderToStaticMarkup(
            createElement(KPICards, { nodes: TEST_NODES, isLoading: false }),
        );
        assert.ok(html.includes("Mạng · mẫu gần nhất"));
        assert.ok(!html.includes("tích lũy"));
        assert.ok(!html.includes("B/s"));
    });
    const api = await server.ssrLoadModule("/src/api.ts");
    const { mergeSamples, timeTicks } = await server.ssrLoadModule("/src/telemetry.ts");
    check("Late, duplicate and invalid samples never roll back the latest reading", () => {
        const merged = mergeSamples([samples[0]], [samples[1], samples[0], { ...samples[2], observed_at: "invalid" }]);
        assert.equal(merged.length, 2);
        assert.equal(merged.at(-1).cpu_percent, 80);
    });
    check("Clock ticks stay separated even when samples cluster at the end", () => {
        for (const width of [240, 322, 700, 1600]) {
            const ticks = timeTicks(0, 100000, width);
            for (let index = 1; index < ticks.length; index++) {
                assert.ok((ticks[index] - ticks[index - 1]) / 100000 * width >= 84);
            }
        }
        assert.deepEqual(timeTicks(100, 100, 322), [100]);
    });
    check("A single valid sample renders markers and invalid dates are excluded", () => {
        const html = renderToStaticMarkup(createElement(TelemetryChart, { selectedNode: node, samples: [samples[0], { ...samples[0], observed_at: "bad" }], isLoading: false }));
        assert.ok(html.includes("1 mẫu"));
        assert.ok(html.includes("<circle"));
        assert.ok(!/NaN|Invalid Date|Infinity/.test(html));
    });
    check("Zero network counters are present data, not missing values", () => {
        const html = renderToStaticMarkup(createElement(KPICards, { nodes: [{ ...node, latestRxBytes: 0, latestTxBytes: 0 }], isLoading: false }));
        assert.ok(html.includes("0 B"));
        assert.ok(!html.includes("Dữ liệu chưa đủ"));
    });
    check("Unreadable disk is distinguishable from a measured zero in host details", () => {
        const render = (latestDisk) => renderToStaticMarkup(createElement(NodeDetailModal, {
            node: { ...node, latestDisk }, isOpen: true, onClose: noop,
        }));
        assert.ok(render(undefined).includes("Không có dữ liệu ổ đĩa"));
        assert.ok(!render(0).includes("Không có dữ liệu ổ đĩa"));
        assert.ok(render(0).includes("0.0%"));
    });
    check("SettingsView auto-checks apply-to-all for uniform cluster and omits inline toast box", () => {
        const html = renderToStaticMarkup(createElement(SettingsView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            projects: TEST_PROJECTS,
            nodes: TEST_NODES,
        }));
        assert.ok(html.includes("Thay đổi cấu hình"));
        assert.ok(html.includes('class="apply-all-checkbox is-checked"'));
        assert.ok(html.includes('checked=""'));
        assert.ok(!html.includes("settings-simple-toast"));
    });
    check("SecurityToast renders bottom stack for incidents, defense actions, and settings updates", () => {
        assert.equal(
            renderToStaticMarkup(createElement(SecurityToast, { toasts: [], onClose: noop, onNavigate: noop })),
            "",
        );
        const html = renderToStaticMarkup(createElement(SecurityToast, {
            toasts: [
                {
                    id: "inc-1",
                    type: "incident",
                    title: "Phát hiện sự cố an ninh mới",
                    message: "SYN Flood vượt ngưỡng cảnh báo (750 pps)",
                    attackerIp: "198.51.100.19",
                    severity: "CRITICAL",
                    targetView: "incidents",
                },
                {
                    id: "def-1",
                    type: "defense",
                    title: "Tường lửa đã kích hoạt",
                    message: "Đã khóa địa chỉ IP nguồn tấn công",
                    targetView: "defense",
                },
                {
                    id: "cfg-1",
                    type: "settings",
                    title: "Cập nhật cấu hình thành công",
                    message: "Đã áp dụng cấu hình [Tiết kiệm tài nguyên (Resource-Saving)] cho máy chủ api-gateway-node.",
                },
            ],
            onClose: noop,
            onNavigate: noop,
        }));
        assert.ok(html.includes("security-toast-stack"));
        assert.ok(html.includes("toast-incident"));
        assert.ok(html.includes("toast-defense"));
        assert.ok(html.includes("toast-settings"));
        assert.ok(html.includes('role="alert"'));
        assert.ok(html.includes('role="status"'));
        assert.ok(html.includes("Cập nhật cấu hình thành công"));
        assert.ok(html.includes("Đã áp dụng cấu hình [Tiết kiệm tài nguyên (Resource-Saving)] cho máy chủ api-gateway-node."));
        assert.equal((html.match(/toast-link-btn/g) || []).length, 2);
    });
    check("IncidentsView omits icons from Khẩn cấp/Cao badges and splits auto vs manual handling", () => {
        const syn = TEST_INCIDENTS.find((i) => i.id === "inc-syn-401");
        const cpu = TEST_INCIDENTS.find((i) => i.id === "inc-cpu-385");
        const disk = TEST_INCIDENTS.find((i) => i.id === "inc-disk-409");
        assert.equal(classifyIncidentHandling(syn, TEST_POLICIES).mode, "auto");
        assert.equal(classifyIncidentHandling(cpu, TEST_POLICIES).mode, "manual");
        assert.equal(classifyIncidentHandling(disk, TEST_POLICIES).mode, "manual");

        const html = renderToStaticMarkup(createElement(IncidentsView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            nodes: TEST_NODES,
            initialIncidents: TEST_INCIDENTS,
            initialPolicies: TEST_POLICIES,
            initialDefenseActions: TEST_DEFENSE_ACTIONS,
        }));
        assert.ok(html.includes("Xử lý tự động"));
        assert.ok(html.includes("Xử lý thủ công"));
        assert.ok(html.includes("Đã giải quyết"));
        assert.ok(html.includes("severity-guide-bar"));
        assert.ok(html.includes("Vượt ngưỡng cảnh báo ban đầu"));
        assert.ok(html.includes("Duy trì vượt ngưỡng ≥ 60 giây (hoặc đạt ≥ 95% / tấn công lớn)"));
        assert.ok(!html.includes("Cần xử lý thủ công"));
        assert.ok(!html.includes('<option value="MEDIUM">'));
        assert.ok(html.includes("Đang chờ Agent tải lệnh"));
        assert.ok(!html.includes("incident-section-header"));
        assert.ok(html.includes("inc-syn-401"));
        assert.ok(!html.includes("inc-cpu-385"));
        assert.ok(!html.includes("inc-disk-409"));
        assert.ok(!html.includes("inc-syn-390"));
        assert.ok(!html.includes("inc-mem-389"));
        assert.ok(html.includes('<span class="severity-badge crit">Khẩn cấp</span>'));
        assert.ok(html.includes('<span class="severity-badge warn">Cao</span>'));
        assert.ok(html.includes("status-badge info"));
        assert.ok(html.includes("status-badge pending"));

        const resolvedTabHtml = renderToStaticMarkup(createElement(IncidentsView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            nodes: TEST_NODES,
            initialTab: "resolved",
            initialIncidents: TEST_INCIDENTS,
            initialPolicies: TEST_POLICIES,
            initialDefenseActions: TEST_DEFENSE_ACTIONS,
        }));
        assert.ok(resolvedTabHtml.includes("inc-syn-390"));
        assert.ok(resolvedTabHtml.includes("inc-mem-389"));
        assert.ok(resolvedTabHtml.includes("inc-disk-391"));
        assert.ok(resolvedTabHtml.includes("inc-cpu-382"));
        assert.ok(resolvedTabHtml.includes("danger-icon-button"));
        assert.ok(!resolvedTabHtml.includes("inc-syn-401"));

        const modalHtml = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: syn,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(!modalHtml.includes("Cơ chế xử lý"));
        assert.ok(!modalHtml.includes("Kích hoạt lệnh chặn IP 203.0.113.195"));
        assert.ok(modalHtml.includes("Đang kích hoạt"));
        assert.ok(modalHtml.includes("\nnftables: DROP 203.0.113.195 (thời hạn: 30 phút)"));

        const mem = TEST_INCIDENTS.find((i) => i.id === "inc-mem-408");
        const memModalHtml = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: mem,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(memModalHtml.includes("Đang chờ Agent tải lệnh"));
        assert.ok(!memModalHtml.includes("Tự động · Tự động tối ưu"));

        const cpuModalHtml = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: cpu,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(cpuModalHtml.includes("Đang diễn ra"));
        assert.ok(!cpuModalHtml.includes("Chính sách tự động đang tắt"));

        const synResolved = TEST_INCIDENTS.find((i) => i.id === "inc-syn-390");
        const diskResolved = TEST_INCIDENTS.find((i) => i.id === "inc-disk-391");
        assert.equal(classifyIncidentHandling(synResolved, TEST_POLICIES).mode, "auto");
        assert.equal(classifyIncidentHandling(diskResolved, TEST_POLICIES).mode, "manual");
        assert.ok(resolvedTabHtml.includes("inc-syn-390"));
        assert.ok(resolvedTabHtml.includes("Đã giải quyết"));

        const synResolvedModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: synResolved,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(!synResolvedModal.includes("Xử lý tự động · Đã hoàn tất"));
        assert.ok(!synResolvedModal.includes("Xử lý thủ công · Đã đóng"));

        const diskResolvedModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: diskResolved,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(diskResolvedModal.includes("Ổ đĩa /tmp: 91.2% (&gt;= 85.0%)"));
        assert.ok(!diskResolvedModal.includes("Thủ công: Đã giải quyết"));

        const scan = TEST_INCIDENTS.find((i) => i.id === "inc-scan-402");
        assert.equal(scan.summary, "IP: 198.51.100.42 · 48 cổng (TCP) (>= 15/10s)");

        const udpMitigating = TEST_INCIDENTS.find((i) => i.id === "inc-udp-395");
        assert.ok(udpMitigating.summary.includes("180 pps (>= 30 pps)"));
        const udpDetected = TEST_INCIDENTS.find((i) => i.id === "inc-udp-398");
        assert.ok(udpDetected.summary.includes("5.420 pps (>= 30 pps) · 42.5 MB/s (>= 500.0 KB/s)"));

        const memResolved = TEST_INCIDENTS.find((i) => i.id === "inc-mem-389");
        const cpuResolved = TEST_INCIDENTS.find((i) => i.id === "inc-cpu-382");
        const memMitigating = TEST_INCIDENTS.find((i) => i.id === "inc-mem-405");
        assert.equal(classifyIncidentHandling(memResolved, TEST_POLICIES).mode, "auto");
        assert.equal(classifyIncidentHandling(cpuResolved, TEST_POLICIES).mode, "manual");
        assert.equal(classifyIncidentHandling(memMitigating, TEST_POLICIES).mode, "auto");
        assert.equal(classifyIncidentHandling(memMitigating, TEST_POLICIES).label, "Tự động · Khởi động lại dịch vụ");
        assert.equal(
            classifyIncidentHandling(
                { ...memMitigating, summary: "RAM: 90.0% (>= 85.0%)\nos-cache: CLEAR" },
                TEST_POLICIES,
            ).label,
            "Tự động · Giải phóng bộ nhớ đệm",
        );
        assert.ok(resolvedTabHtml.includes("inc-mem-389"));
        assert.ok(memResolved.summary.includes("\nservice: RESTART java"));

        const memMitigatingModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: memMitigating,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(memMitigatingModal.includes("Đang kích hoạt"));
        assert.ok(!memMitigatingModal.includes("Kích hoạt khởi động lại dịch vụ nginx"));
        assert.ok(memMitigatingModal.includes("\nservice: RESTART nginx"));
        assert.ok(memMitigatingModal.includes("Đánh dấu đã giải quyết"));
        assert.ok(!synResolvedModal.includes("Đánh dấu đã giải quyết"));

        const scanModalHtml = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: scan,
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(scanModalHtml.includes("Đang chờ Agent tải lệnh"));
        assert.ok(scanModalHtml.includes("Đánh dấu đã giải quyết"));

        const falsePositiveModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: { ...scan, status: "FALSE_POSITIVE" },
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(falsePositiveModal.includes("Báo động giả"));
        assert.ok(!falsePositiveModal.includes("Đánh dấu đã giải quyết"));

        const deliveryFailedModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: { ...scan, defense_status: "DELIVERY_FAILED" },
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(deliveryFailedModal.includes("Tải lệnh bị lỗi"));
        assert.ok(deliveryFailedModal.includes("Đánh dấu đã giải quyết"));

        const executionFailedModal = renderToStaticMarkup(createElement(IncidentDetailModal, {
            incident: { ...scan, defense_status: "EXECUTION_FAILED" },
            nodes: TEST_NODES,
            policies: TEST_POLICIES,
            isOpen: true,
            onClose: noop,
        }));
        assert.ok(executionFailedModal.includes("Kích hoạt bị lỗi"));
        assert.ok(executionFailedModal.includes("Đánh dấu đã giải quyết"));

        const resolvedMsg = formatRealtimeMessage({
            event: "incident_update",
            timestamp: "2026-11-23T10:00:00Z",
            data: { id: "inc-1", title: "Tấn công SYN Flood", status: "RESOLVED" },
        });
        assert.ok(resolvedMsg.includes("Đã giải quyết"));
        assert.ok(!resolvedMsg.includes("RESOLVED"));

        const execErrMsg = formatRealtimeMessage({
            event: "incident_update",
            timestamp: "2026-11-23T10:00:00Z",
            data: {
                id: "inc-2",
                title: "Cạn kiệt RAM",
                status: "DETECTED",
                defense_status: "EXECUTION_FAILED",
            },
        });
        assert.ok(execErrMsg.includes("Kích hoạt bị lỗi"));
    });
    check("DefenseView scopes strictly to firewall actions and separates pending/reverted/failed controls", () => {
        const defaultProjectNodes = TEST_NODES.filter(
            (n) => n.project_id === TEST_PROJECTS[0].id,
        );
        const defenseHtml = renderToStaticMarkup(createElement(DefenseView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            nodes: defaultProjectNodes,
            initialActions: TEST_DEFENSE_ACTIONS,
        }));
        assert.ok(defenseHtml.includes("203.0.113.195"));
        assert.ok(defenseHtml.includes("198.51.100.42"));
        assert.ok(defenseHtml.includes("198.51.100.77"));
        assert.ok(!defenseHtml.includes("RESTART_SERVICE"));
        assert.ok(!defenseHtml.includes(">RESTART<"));
        assert.ok(defenseHtml.includes("Đang chờ"));
        assert.ok(defenseHtml.includes("Chờ Agent tải lệnh"));
        assert.ok(defenseHtml.includes("Hủy lệnh"));
        assert.ok(defenseHtml.includes("Gỡ chặn"));
        assert.ok(!defenseHtml.includes("Vĩnh viễn"));
        assert.ok(defenseHtml.includes("Thời gian chặn IP"));
        assert.ok(defenseHtml.includes("Cấu hình 15 phút"));
        assert.ok(defenseHtml.includes("30 phút"));
        assert.ok(!defenseHtml.includes("15m 00s"));
        assert.match(appCss, /\.defense-view\s*>\s*\.kpi-grid[\s\S]*?margin-bottom:\s*0/);

        const modalHtml = renderToStaticMarkup(createElement(ManualBlockModal, {
            isOpen: true,
            onClose: noop,
            nodes: defaultProjectNodes,
            onActionCreated: noop,
        }));
        assert.ok(!modalHtml.includes('value="0"'));
        assert.ok(modalHtml.includes('value="1440"'));
        assert.ok(modalHtml.includes("Thời gian chặn IP"));

        const targetNode = defaultProjectNodes.find((n) => n.id === "node-api-02") ?? defaultProjectNodes[0];
        const prodWhitelist = TEST_WHITELIST.filter((w) => w.project_id === TEST_PROJECTS[0].id);
        assert.equal(validateManualBlockIp("203.0.113.250", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, true);
        assert.equal(validateManualBlockIp("2001:db8::99", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, true);
        assert.equal(validateManualBlockIp("not-an-ip", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
        assert.equal(validateManualBlockIp("127.0.0.1", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
        assert.equal(validateManualBlockIp("::1", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
        assert.equal(validateManualBlockIp(targetNode.ip_address, targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
        assert.equal(validateManualBlockIp("192.168.1.55", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
        assert.equal(validateManualBlockIp("203.0.113.195", targetNode, prodWhitelist, TEST_DEFENSE_ACTIONS).valid, false);
    });
    check("PoliciesView renders whitelist validation and fixed toggle-only system policies", async () => {
        const policiesHtml = renderToStaticMarkup(createElement(PoliciesView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            projects: TEST_PROJECTS,
            initialPolicies: TEST_POLICIES,
            initialWhitelist: TEST_WHITELIST,
        }));
        assert.ok(policiesHtml.includes("192.168.1.0/24"));
        assert.ok(policiesHtml.includes("Danh sách an toàn"));
        assert.ok(policiesHtml.includes("Chính sách bảo vệ tự động"));

        const fixedPoliciesTabHtml = renderToStaticMarkup(createElement(PoliciesView, {
            selectedProjectId: TEST_PROJECTS[0].id,
            projects: TEST_PROJECTS,
            initialTab: "policies",
            initialPolicies: TEST_POLICIES,
            initialWhitelist: TEST_WHITELIST,
        }));
        assert.ok(fixedPoliciesTabHtml.includes("TCP Flood / SYN Flood"));
        assert.ok(fixedPoliciesTabHtml.includes("Chặn các IP quét cổng"));
        assert.ok(fixedPoliciesTabHtml.includes("UDP Flood / Traffic Spike"));
        assert.ok(fixedPoliciesTabHtml.includes("Quá tải CPU"));
        assert.ok(fixedPoliciesTabHtml.includes("Quá tải RAM"));
        assert.ok(fixedPoliciesTabHtml.includes('role="switch"'));
        assert.ok(!fixedPoliciesTabHtml.includes("Làm mới chính sách"));
        assert.ok(!fixedPoliciesTabHtml.includes("Quy tắc tự động ứng phó"));
        assert.ok(!fixedPoliciesTabHtml.includes("Thêm chính sách"));
        assert.ok(fixedPoliciesTabHtml.includes("Chỉnh sửa chính sách"));
        assert.ok(!fixedPoliciesTabHtml.includes("nftables-badge"));
        assert.ok(!fixedPoliciesTabHtml.includes("adaptive-badge"));
        assert.ok(!fixedPoliciesTabHtml.includes("Xóa chính sách"));
        assert.ok(!fixedPoliciesTabHtml.includes("Vĩnh viễn"));

        const editNetHtml = renderToStaticMarkup(createElement(EditPolicyModal, {
            isOpen: true,
            onClose: noop,
            policy: TEST_POLICIES[0],
            onPolicyUpdated: noop,
        }));
        assert.ok(!editNetHtml.includes('value="0"'));
        assert.ok(editNetHtml.includes('value="1440"'));
        assert.ok(!editNetHtml.includes('-action"'));
        assert.ok(!editNetHtml.includes("Hành động áp dụng khi bật"));
        assert.ok(!editNetHtml.includes("ALERT_ONLY"));
        assert.ok(!editNetHtml.includes("CLEAR_OS_CACHE"));

        const cpuPol = TEST_POLICIES.find((p) => p.event_type === "cpu_threshold_detector");
        const editCpuHtml = renderToStaticMarkup(createElement(EditPolicyModal, {
            isOpen: true,
            onClose: noop,
            policy: cpuPol,
            onPolicyUpdated: noop,
        }));
        assert.ok(editCpuHtml.includes('-action"'));
        assert.ok(!editCpuHtml.includes("CLEAR_OS_CACHE"));
        assert.ok(editCpuHtml.includes("ALERT_ONLY"));
        assert.ok(editCpuHtml.includes("RESTART_SERVICE"));

        const memPol = TEST_POLICIES.find((p) => p.event_type === "memory_exhaustion_detector");
        const editMemHtml = renderToStaticMarkup(createElement(EditPolicyModal, {
            isOpen: true,
            onClose: noop,
            policy: memPol,
            onPolicyUpdated: noop,
        }));
        assert.ok(editMemHtml.includes('-action"'));
        assert.ok(editMemHtml.includes("CLEAR_OS_CACHE"));
        assert.ok(editMemHtml.includes("RESTART_SERVICE"));
        assert.ok(!editMemHtml.includes("hoặc tiến trình"));
        assert.ok(!editMemHtml.includes("ALERT_ONLY"));

        const whitelistHtml = renderToStaticMarkup(createElement(AddWhitelistModal, {
            isOpen: true,
            onClose: noop,
            projectId: TEST_PROJECTS[0].id,
            onWhitelistCreated: noop,
        }));
        assert.ok(whitelistHtml.includes("Thêm IP an toàn"));

        const prodWhitelist = TEST_WHITELIST.filter((w) => w.project_id === TEST_PROJECTS[0].id);
        assert.equal(validateWhitelistCidr("203.0.113.10", prodWhitelist).valid, true);
        assert.equal(validateWhitelistCidr("2001:db8::/48", prodWhitelist).valid, true);
        assert.equal(validateWhitelistCidr("999.1.2.3", prodWhitelist).valid, false);
        assert.equal(validateWhitelistCidr("bad:ip", prodWhitelist).valid, false);
        assert.equal(validateWhitelistCidr("192.168.1.0/24", prodWhitelist).valid, false);
    });
    const originalFetch = globalThis.fetch;
    try {
        globalThis.fetch = async () =>
            new Response(
                JSON.stringify([
                    {
                        project_id: "project-uuid",
                        name: "Lab",
                        description: null,
                        created_at: "2026-10-16T00:00:00Z",
                    },
                ]),
            );
        const projects = await api.fetchProjects();
        check("Controller project_id maps to dashboard ID", () =>
            assert.equal(projects[0].id, "project-uuid"),
        );

        let sentWhitelistBody = null;
        globalThis.fetch = async (_url, init) => {
            sentWhitelistBody = JSON.parse(String(init?.body ?? "{}"));
            return new Response(JSON.stringify({
                id: "wl-live-1",
                project_id: "project-uuid",
                ip_or_cidr: "203.0.113.0/24",
                description: "Office",
                created_at: "2026-10-16T00:00:00Z",
            }));
        };
        const createdWl = await api.createWhitelist("project-uuid", "203.0.113.0/24", "Office");
        check("createWhitelist sends ip_or_cidr and normalizes cidr response", () => {
            assert.equal(sentWhitelistBody.ip_or_cidr, "203.0.113.0/24");
            assert.equal(sentWhitelistBody.cidr, undefined);
            assert.equal(createdWl.cidr, "203.0.113.0/24");
        });

        let sentPolicyPatchBody = null;
        globalThis.fetch = async (_url, init) => {
            sentPolicyPatchBody = JSON.parse(String(init?.body ?? "{}"));
            return new Response(JSON.stringify({
                id: "pol-live-1",
                project_id: "project-uuid",
                name: "SYN Block",
                event_type: "syn_flood_detector",
                action_type: "BLOCK_IP_NFTABLES",
                target_params: {},
                is_auto_execute: true,
                cooldown_seconds: 60,
                block_duration_seconds: 1800,
                enabled: false,
            }));
        };
        const updatedPol = await api.updatePolicy("pol-live-1", { is_active: false });
        check("updatePolicy maps is_active to enabled wire field", () => {
            assert.equal(sentPolicyPatchBody.enabled, false);
            assert.equal(sentPolicyPatchBody.is_active, undefined);
            assert.equal(updatedPol.is_active, false);
        });

        check("LoadBalancerView renders animated topology for LB project and CTA for standalone project", () => {
            const prodProj = TEST_PROJECTS[0];
            const prodNodes = TEST_NODES.filter((n) => n.project_id === prodProj.id);
            const liveLbStatus = {
                project_id: prodProj.id,
                enabled: true,
                lb_url: "http://192.168.1.5:8080",
                algorithm: "round_robin",
                reachable: true,
                sync_status: "synced",
                sync_message: null,
                health_check: {
                    enabled: true,
                    path: "/health",
                    interval_seconds: 10,
                    failure_threshold: 3,
                    success_threshold: 2,
                },
                total_backends: 2,
                healthy_backends: 2,
                routable_backends: 2,
                admin_disabled_backends: 0,
                total_in_flight: 1,
                total_requests: 120,
                total_success: 120,
                total_errors: 0,
                backends: [
                    {
                        name: "api-gateway-node",
                        url: "http://10.0.1.15:8080",
                        node_id: "node-api-01",
                        weight: 1,
                        health_path: "/health",
                        is_healthy: true,
                        admin_enabled: true,
                        health_state: "healthy",
                        in_flight: 1,
                        total_requests: 60,
                        success_requests: 60,
                        error_requests: 0,
                        consecutive_successes: 3,
                        consecutive_failures: 0,
                        last_health_check_at: "2026-11-24T10:00:00Z",
                        last_health_error: null,
                    },
                    {
                        name: "worker-celery-pool",
                        url: "http://10.0.1.25:8080",
                        node_id: "node-api-02",
                        weight: 1,
                        health_path: "/health",
                        is_healthy: true,
                        admin_enabled: true,
                        health_state: "healthy",
                        in_flight: 0,
                        total_requests: 60,
                        success_requests: 60,
                        error_requests: 0,
                        consecutive_successes: 3,
                        consecutive_failures: 0,
                        last_health_check_at: "2026-11-24T10:00:00Z",
                        last_health_error: null,
                    },
                ],
            };
            const lbHtml = renderToStaticMarkup(createElement(LoadBalancerView, {
                project: prodProj,
                projectNodes: prodNodes,
                initialStatus: liveLbStatus,
                onOpenConfig: noop,
                onUpdateProjectLB: async () => prodProj,
                onUpdateNode: async () => prodNodes[0],
                onNotify: noop,
            }));
            assert.ok(lbHtml.includes("Luồng phân phối tải trực tiếp"));
            assert.ok(lbHtml.includes("lb-connector-svg"));
            assert.ok(lbHtml.includes("animateMotion"));
            assert.ok(lbHtml.includes("SENTINELX LB HUB"));
            assert.ok(lbHtml.includes("NGUỒN TRUY CẬP"));
            assert.ok(lbHtml.includes(">Client<"));
            assert.ok(lbHtml.includes("HTTP Reverse Proxy"));
            assert.ok(lbHtml.includes("Round Robin"));
            assert.ok(!lbHtml.includes("lb-algo-segmented"));
            assert.ok(!lbHtml.includes("Pool đã đồng bộ"));
            assert.ok(!lbHtml.includes("Least In-Flight"));
            assert.ok(lbHtml.includes("api-gateway-node"));
            assert.ok(lbHtml.includes("HEALTHY"));
            assert.ok(lbHtml.includes('role="switch"'));
            assert.ok(lbHtml.includes("lb-slider-track is-on"));
            assert.ok(lbHtml.includes("Ổn định"));
            assert.ok(!lbHtml.includes(">Đồng bộ</button>"));

            const dbProj = TEST_PROJECTS[2];
            const dbNodes = TEST_NODES.filter((n) => n.project_id === dbProj.id);
            const emptyLbHtml = renderToStaticMarkup(createElement(LoadBalancerView, {
                project: dbProj,
                projectNodes: dbNodes,
                onOpenConfig: noop,
                onGoToHosts: noop,
                onUpdateProjectLB: async () => dbProj,
                onUpdateNode: async () => dbNodes[0],
            }));
            assert.ok(emptyLbHtml.includes('role="switch"'));
            assert.ok(emptyLbHtml.includes("Tắt"));
            assert.ok(emptyLbHtml.includes("Luồng phân phối tải trực tiếp"));
            assert.ok(emptyLbHtml.includes("Chẩn đoán Health Check"));
            assert.ok(emptyLbHtml.includes("Chọn máy chủ vào Pool"));
            assert.ok(!emptyLbHtml.includes("lb-picker-box"));
            assert.ok(!emptyLbHtml.includes("Đăng ký thêm máy chủ"));

            const pickerModalHtml = renderToStaticMarkup(createElement(LBPoolPickerModal, {
                isOpen: true,
                projectName: dbProj.name,
                eligibleNodes: dbNodes.filter((n) => n.status === "online"),
                unavailableCount: 1,
                onClose: noop,
                onConfirmAdd: async () => {},
            }));
            assert.ok(pickerModalHtml.includes("lb-node-metric-card"));
            assert.ok(pickerModalHtml.includes("pg-primary-cluster"));
            assert.ok(pickerModalHtml.includes("CPU"));
            assert.ok(pickerModalHtml.includes("RAM"));
            assert.ok(!pickerModalHtml.includes("backup-storage-nas"));
            assert.ok(pickerModalHtml.includes("Ẩn 1 máy chưa kết nối / offline"));

            const emptyPickerModalHtml = renderToStaticMarkup(createElement(LBPoolPickerModal, {
                isOpen: true,
                projectName: dbProj.name,
                eligibleNodes: [],
                unavailableCount: 0,
                onClose: noop,
                onConfirmAdd: async () => {},
            }));
            assert.ok(emptyPickerModalHtml.includes("Mọi máy chủ của dự án đã nằm trong LB Pool"));
            assert.ok(!emptyPickerModalHtml.includes("Chọn thẻ máy chủ để thêm vào Pool"));
            assert.ok(!emptyPickerModalHtml.includes("Tới trang Máy chủ"));
        });

        check("LB modals and node creation stay clean without duplicate LB fields", () => {
            const addProjHtml = renderToStaticMarkup(createElement(AddProjectModal, {
                isOpen: true,
                onClose: noop,
                onCreateProject: async () => TEST_PROJECTS[0],
            }));
            assert.ok(addProjHtml.includes("Tên dự án"));
            assert.ok(!addProjHtml.includes("Bật Load Balancer"));

            const editLbHtml = renderToStaticMarkup(createElement(ProjectLBConfigModal, {
                isOpen: true,
                project: TEST_PROJECTS[0],
                mode: "lb",
                onClose: noop,
                onSave: async () => {},
            }));
            assert.ok(editLbHtml.includes(">Endpoint LB<"));
            assert.ok(editLbHtml.includes(">Health Check<"));
            assert.ok(editLbHtml.includes("Chu kỳ probe"));
            assert.ok(editLbHtml.includes(">Ngưỡng eject<"));
            assert.ok(editLbHtml.includes("Ngưỡng hồi phục"));
            assert.ok(!editLbHtml.includes("Bật Load Balancer"));
            assert.ok(editLbHtml.includes("Thuật toán chia tải"));
            assert.ok(editLbHtml.includes("Round Robin"));
            assert.ok(editLbHtml.includes("(hiện tại)"));
            assert.ok(editLbHtml.includes("Least In-Flight"));

            const editProjInfoHtml = renderToStaticMarkup(createElement(ProjectLBConfigModal, {
                isOpen: true,
                project: TEST_PROJECTS[0],
                mode: "project",
                onClose: noop,
                onSave: async () => {},
            }));
            assert.ok(editProjInfoHtml.includes("Tên dự án"));
            assert.ok(!editProjInfoHtml.includes("Endpoint LB riêng"));

            const addNodeHtml = renderToStaticMarkup(createElement(AddNodeModal, {
                projects: TEST_PROJECTS,
                selectedProjectId: TEST_PROJECTS[0].id,
                isOpen: true,
                onClose: noop,
                onNodeCreated: noop,
            }));
            assert.ok(addNodeHtml.includes("Đăng ký máy chủ"));
            assert.ok(!addNodeHtml.includes("Vai trò trong cụm Load Balancer"));
        });

        check("KPICards renders LB metric card inline in 6-card row only when project LB is enabled", () => {
            const prodProj = TEST_PROJECTS[0];
            const prodNodes = TEST_NODES.filter((n) => n.project_id === prodProj.id);
            const kpiWithLb = renderToStaticMarkup(createElement(KPICards, {
                nodes: prodNodes,
                activeProject: prodProj,
                isLoading: false,
                onOpenLoadBalancer: noop,
            }));
            assert.ok(kpiWithLb.includes("kpi-grid-6"));
            assert.ok(kpiWithLb.includes("Cân bằng tải"));
            assert.ok(kpiWithLb.includes("Round Robin"));

            const dbProj = TEST_PROJECTS[2];
            const kpiWithoutLb = renderToStaticMarkup(createElement(KPICards, {
                nodes: [node],
                activeProject: dbProj,
                isLoading: false,
            }));
            assert.ok(kpiWithoutLb.includes("kpi-grid-5"));
            assert.ok(!kpiWithoutLb.includes("Cân bằng tải"));
        });

        check("AgentInstallSection generates safe Linux bundle commands and dev fallback cleanly", () => {
            const bundleInfo = {
                available: true,
                release: "0.1.0-deadbeefcafe",
                filename: "sentinelx-agent-0.1.0-deadbeefcafe.tar.gz",
                sha256: "a".repeat(64),
                size_bytes: 58368,
                download_path: "/api/v1/system/agent-bundle/download",
            };
            const linuxCmd = buildLinuxBundleCommand({
                controllerUrl: "http://192.168.1.10:8000/",
                nodeId: "node-uuid-01",
                bundleInfo,
            });
            assert.ok(linuxCmd.includes("http://192.168.1.10:8000/api/v1/system/agent-bundle/download"));
            assert.ok(linuxCmd.includes("sha256sum -c -"));
            assert.ok(linuxCmd.includes("manage.py install"));
            assert.ok(linuxCmd.includes("manage.py enroll"));
            assert.ok(linuxCmd.includes("manage.py restart"));
            assert.ok(!linuxCmd.includes("secret-token"));

            const devCmd = buildDevUvCommand({
                controllerUrl: "http://192.168.1.10:8000",
                nodeId: "node-uuid-01",
                token: "secret-token",
            });
            assert.ok(devCmd.includes("SENTINELX_ENROLLMENT_TOKEN='secret-token'"));
            assert.ok(devCmd.includes("uv run python -m sentinelx_agent.main"));

            const sectionHtml = renderToStaticMarkup(createElement(AgentInstallSection, {
                nodeId: "node-uuid-01",
                token: "secret-token",
                controllerUrl: "http://192.168.1.10:8000",
                bundleInfo,
            }));
            assert.ok(sectionHtml.includes("Cài chuẩn Linux (systemd)"));
            assert.ok(sectionHtml.includes("Chạy nhanh (uv run)"));
            assert.ok(sectionHtml.includes("sentinelx-agent-0.1.0-deadbeefcafe.tar.gz"));
            assert.ok(sectionHtml.includes("/api/v1/system/agent-bundle/download"));
            assert.ok(sectionHtml.includes("secret-token"));
        });

        check("Security empty states, LB pill nowrap, sidebar scroll, and NodeDetailModal metrics CTA are consistent", () => {
            assert.match(appCss, /\.empty-state-card\s*\{[^}]*align-items:\s*center/s);
            assert.match(appCss, /\.sidebar-scroll\s*\{[^}]*overflow-y:\s*auto/s);
            assert.match(appCss, /\.project-lb-pill\s*\{[^}]*white-space:\s*nowrap/s);

            const emptyDefense = renderToStaticMarkup(createElement(DefenseView, {
                selectedProjectId: TEST_PROJECTS[0].id,
                nodes: [node],
                initialActions: [],
            }));
            assert.ok(emptyDefense.includes("empty-state-card"));

            const emptyPolicies = renderToStaticMarkup(createElement(PoliciesView, {
                selectedProjectId: TEST_PROJECTS[0].id,
                projects: TEST_PROJECTS,
                initialWhitelist: [],
                initialPolicies: [],
            }));
            assert.ok(emptyPolicies.includes("empty-state-card"));

            const detailWithMetrics = renderToStaticMarkup(createElement(NodeDetailModal, {
                node,
                isOpen: true,
                onClose: noop,
                onInspectMetrics: noop,
            }));
            assert.ok(detailWithMetrics.includes("Xem mẫu dữ liệu"));
        });
    } finally {
        globalThis.fetch = originalFetch;
    }
    console.log(`\n${passed} UI smoke checks passed.`);
} finally {
    await server.close();
    await rm(cacheDir, { recursive: true, force: true });
    delete globalThis.window;
}
