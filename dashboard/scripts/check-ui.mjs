import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
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
    const { nodeHealth } = await server.ssrLoadModule("/src/presentation.ts");
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
            assert.ok(html.includes('aria-current="page"'));
            assert.ok(!/NaN|undefined|Infinity/.test(html));
            assert.ok(html.includes("dữ liệu mô phỏng"));
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
                    assert.ok(html.includes('aria-label="Máy chủ tải cao"'));
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
        assert.equal(labels.length, 8);
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
