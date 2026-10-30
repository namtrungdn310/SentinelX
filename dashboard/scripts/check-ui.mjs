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
    const { nodeHealth, nodeHealthLabel } = await server.ssrLoadModule("/src/presentation.ts");
    const { filterEvents, eventLabel, eventMatchesCategory } = await server.ssrLoadModule("/src/events.ts");
    const { LiveEventStream } = await server.ssrLoadModule("/src/components/LiveEventStream.tsx");
    const { MOCK_NODES } = await server.ssrLoadModule("/src/mockData.ts");
    const node = MOCK_NODES[0];
    const noop = () => {};

    for (const [route, expected] of Object.entries({
        overview: "Tổng quan hạ tầng",
        hosts: "Danh sách máy chủ",
        metrics: "Telemetry tài nguyên",
        events: "Nhật ký hệ thống",
    })) {
        window.location.hash = "#" + route;
        const html = renderToStaticMarkup(createElement(App));
        check("Render route #" + route, () => {
            assert.ok(html.includes(expected));
            assert.ok(html.includes("sentinelx-mark-v2.svg"));
            assert.ok(html.includes('aria-current="page"'));
            assert.ok(!/NaN|undefined|Infinity/.test(html));
            assert.ok(html.includes("Dữ liệu mô phỏng"));
            assert.ok(html.includes("Chưa kết nối Controller"));
            assert.ok(!html.includes('class="demo-notice"'), "Do not repeat the source notice below the header");
            assert.ok(
                !/THE BIG PICTURE|Stay curious|Stay in control|Infrastructure, in sync/.test(
                    html,
                ),
            );
        });
        if (route === "overview")
            check(
                "Overview summarizes the fleet without duplicating telemetry or host inventory",
                () => {
                    assert.ok(html.includes('aria-label="Tổng quan toàn cụm"'));
                    assert.ok(
                        html.includes('aria-label="Tổng hợp theo dự án"'),
                    );
                    assert.ok(html.includes('aria-label="Máy chủ sử dụng tài nguyên nhiều nhất"'));
                    assert.ok(html.includes('aria-label="Tỷ lệ máy chủ ổn định"'));
                    assert.ok(html.includes("Sự kiện gần nhất"));
                    assert.ok(
                        !html.includes('aria-label="Biểu đồ tài nguyên"'),
                    );
                    assert.ok(!html.includes('aria-label="Số mẫu telemetry"'));
                    assert.ok(!html.includes('id="host-fleet"'));
                    assert.ok(!html.includes('aria-label="Lọc sự kiện"'));
                },
            );
        if (route === "metrics")
            check("Telemetry is a single-host analysis view", () => {
                assert.ok(html.includes('id="telemetry-host"'));
                assert.ok(html.includes('aria-label="Biểu đồ tài nguyên"'));
                assert.ok(html.includes('aria-label="Số mẫu telemetry"'));
                assert.ok(!html.includes('aria-label="Tổng quan toàn cụm"'));
                assert.ok(!html.includes('aria-label="Chỉ số tổng quan"'));
            });
    }
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
        assert.ok(html.includes("Chưa có mẫu telemetry"));
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
    check("Health reflects memory, degradation and enrollment", () => {
        assert.equal(
            nodeHealth({ ...node, latestCpu: 10, latestMemory: 90 }),
            "warn",
        );
        assert.equal(nodeHealth({ ...node, status: "degraded" }), "warn");
        assert.equal(
            nodeHealth({ ...node, status: "unenrolled", latestCpu: 95 }),
            "unenrolled",
        );
        assert.equal(nodeHealth({ ...node, status: "offline" }), "crit");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: undefined }), "unknown");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: 75, latestMemory: 85 }), "ok");
        assert.equal(nodeHealth({ ...node, status: "online", latestCpu: 75.1, latestMemory: 85 }), "warn");
    });
    check("Status labels distinguish thresholds from an Agent reporting degradation", () => {
        assert.equal(nodeHealthLabel({ ...node, status: "degraded", latestCpu: 20, latestMemory: 30 }), "Suy giảm");
        assert.equal(nodeHealthLabel({ ...node, status: "online", latestCpu: 80, latestMemory: 30 }), "Vượt ngưỡng");
        assert.equal(nodeHealthLabel({ ...node, status: "unenrolled", latestCpu: 99 }), "Chờ đăng ký");
        assert.equal(nodeHealthLabel({ ...node, status: "offline", latestCpu: 99 }), "Mất kết nối");
    });
    check("Pending enrollment needs action but is not a resource warning", () => {
        const html = renderToStaticMarkup(createElement(KPICards, { nodes: [{ ...node, status: "unenrolled" }], isLoading: false }));
        assert.ok(html.includes("Cần xử lý"));
        assert.ok(html.includes("1 chờ đăng ký"));
        assert.ok(html.includes("0 cảnh báo"));
        assert.ok(!html.includes("stat-attention"));
        const warning = renderToStaticMarkup(createElement(KPICards, { nodes: [{ ...node, status: "offline" }], isLoading: false }));
        assert.ok(warning.includes("stat-attention"));
    });
    const eventFixture = ["metric_update", "system_alert", "node_status", "heartbeat", "node_enrolled", "future_event"].map((event, i) => ({ event, timestamp: `2026-10-23T10:00:0${i}Z`, data: { node_id: node.id, message: "Thông tin thử nghiệm" } }));
    check("Event categories keep All exhaustive and filter without reordering or mutating", () => {
        assert.deepEqual(filterEvents(eventFixture, [node], "all", ""), eventFixture);
        assert.deepEqual(filterEvents(eventFixture, [node], "telemetry", ""), [eventFixture[0]]);
        assert.deepEqual(filterEvents(eventFixture, [node], "status", ""), eventFixture.slice(1, 5));
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
        const html = renderToStaticMarkup(createElement(LiveEventStream, { events: eventFixture, nodes: [node], isConnected: true, isDemoMode: true }));
        assert.ok(html.includes('aria-pressed="true">Tất cả'));
        assert.ok(html.includes("Trạng thái &amp; cảnh báo"));
        assert.ok(html.includes("Sự kiện khác"));
        assert.ok(html.includes("future_event"));
        assert.ok(html.includes("Đang cập nhật · mô phỏng"));
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
    check("Network counters are not mislabeled as bytes per second", () => {
        const html = renderToStaticMarkup(
            createElement(KPICards, { nodes: MOCK_NODES, isLoading: false }),
        );
        assert.ok(html.includes("Dữ liệu mạng tích lũy"));
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
    } finally {
        globalThis.fetch = originalFetch;
    }
    console.log(`\n${passed} UI smoke checks passed.`);
} finally {
    await server.close();
    await rm(cacheDir, { recursive: true, force: true });
    delete globalThis.window;
}
