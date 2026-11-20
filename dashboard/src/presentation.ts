import type { Node } from "./types";
export type Health = "ok" | "warn" | "crit" | "unenrolled" | "unknown";
export const validMetric = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
export const formatPercent = (value: unknown): string =>
  validMetric(value) ? `${value.toFixed(1)}%` : "—";
export function nodeHealth(node: Node): Health {
  if (node.status === "unenrolled") return "unenrolled";
  if (node.status === "offline") return "crit";
  if (
    node.status === "degraded" ||
    (validMetric(node.latestCpu) && node.latestCpu > 75) ||
    (validMetric(node.latestMemory) && node.latestMemory > 85)
  )
    return "warn";
  return validMetric(node.latestCpu) && validMetric(node.latestMemory) ? "ok" : "unknown";
}
export const healthLabels: Record<Health, string> = {
  ok: "Ổn định",
  warn: "Cảnh báo",
  crit: "Mất kết nối",
  unenrolled: "Chờ đăng ký",
  unknown: "Chưa có mẫu",
};
// A degraded Agent is not necessarily over a resource threshold.
export function nodeHealthLabel(node: Node): string {
  const health = nodeHealth(node);
  if (health !== "warn") return healthLabels[health];
  return (validMetric(node.latestCpu) && node.latestCpu > 75) ||
    (validMetric(node.latestMemory) && node.latestMemory > 85)
    ? "Vượt ngưỡng"
    : "Suy giảm";
}
export function nodeRole(hostname: string): string {
  const name = hostname.toLowerCase();
  if (/ingress|gateway|lb/.test(name)) return "Gateway";
  if (/db|pg|primary/.test(name)) return "Database";
  if (/api|backend/.test(name)) return "API server";
  return "Worker";
}
export function formatBytes(bytes: number): string {
  if (!validMetric(bytes)) return "—";
  if (bytes <= 0) return "0 B";
  const index = Math.min(3, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(1)} ${["B", "KB", "MB", "GB"][index]}`;
}

export function getNodeHardware(node: Partial<Node>): {
  cpuCores: number;
  totalMemoryBytes: number;
  totalDiskBytes: number;
} {
  const name = (node.hostname || "").toLowerCase();
  let defaultCores = 4;
  let defaultMemGb = 2; // Default 2 GB RAM (matching user reference)
  let defaultDiskGb = 80;

  if (/ingress|gateway|edge/.test(name)) {
    defaultCores = 2;
    defaultMemGb = 2;
    defaultDiskGb = 50;
  } else if (/db|pg|primary|postgres/.test(name)) {
    defaultCores = 8;
    defaultMemGb = 8;
    defaultDiskGb = 200;
  } else if (/worker|celery/.test(name)) {
    defaultCores = 4;
    defaultMemGb = 2;
    defaultDiskGb = 100;
  } else if (/storage|nas|backup/.test(name)) {
    defaultCores = 2;
    defaultMemGb = 4;
    defaultDiskGb = 500;
  }

  return {
    cpuCores: node.cpuCores ?? defaultCores,
    totalMemoryBytes: node.totalMemoryBytes ?? defaultMemGb * 1024 * 1024 * 1024,
    totalDiskBytes: node.totalDiskBytes ?? defaultDiskGb * 1024 * 1024 * 1024,
  };
}

export function formatMemoryUsage(percent?: number, totalBytes?: number): string {
  if (!validMetric(percent)) return "—";
  const total = totalBytes ?? 2 * 1024 * 1024 * 1024;
  const usedBytes = (percent / 100) * total;
  return `${formatBytes(usedBytes)} / ${formatBytes(total)}`;
}

export function formatCpuUsage(percent?: number, cores?: number): string {
  if (!validMetric(percent)) return "—";
  const totalCores = cores ?? 4;
  const usedCores = ((percent / 100) * totalCores).toFixed(1);
  return `${usedCores} / ${totalCores} vCPU`;
}

export function formatDiskUsage(percent?: number, totalBytes?: number): string {
  if (!validMetric(percent)) return "—";
  const total = totalBytes ?? 100 * 1024 * 1024 * 1024;
  const usedBytes = (percent / 100) * total;
  return `${formatBytes(usedBytes)} / ${formatBytes(total)}`;
}

/**
 * Format danh sách cổng thành các khoảng (ranges) hoặc cổng đơn lẻ:
 * Ví dụ: [20, 21, 22, 80, 443, 8080, 8081, 8082] -> "20 - 22, 80, 443, 8080 - 8082"
 * Nếu không có cổng hoặc sự cố tài nguyên: trả về "—"
 */
export function formatPortRanges(ports?: number[] | null): string {
  if (!ports || !Array.isArray(ports) || ports.length === 0) return "—";
  const valid = ports.filter((p) => typeof p === "number" && Number.isInteger(p) && p > 0);
  if (valid.length === 0) return "—";
  const sorted = Array.from(new Set(valid)).sort((a, b) => a - b);

  const segments: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];

  for (let i = 1; i < sorted.length; i++) {
    const curr = sorted[i];
    if (curr === prev + 1) {
      prev = curr;
    } else {
      segments.push(start === prev ? String(start) : `${start} - ${prev}`);
      start = curr;
      prev = curr;
    }
  }
  segments.push(start === prev ? String(start) : `${start} - ${prev}`);
  return segments.join(", ");
}

export interface PortSummary {
  visible: string;
  remaining: number;
}

/**
 * Tách tóm tắt danh sách cổng:
 * - visible: danh sách cổng đầu tiên (tối đa maxVisible)
 * - remaining: số cổng còn lại
 */
export function getPortSummary(ports?: number[] | null, maxVisible: number = 2): PortSummary | null {
  if (!ports || !Array.isArray(ports) || ports.length === 0) return null;
  const valid = ports.filter((p) => typeof p === "number" && Number.isInteger(p) && p > 0);
  if (valid.length === 0) return null;
  const sorted = Array.from(new Set(valid)).sort((a, b) => a - b);
  if (sorted.length <= maxVisible) {
    return { visible: sorted.join(", "), remaining: 0 };
  }
  return {
    visible: sorted.slice(0, maxVisible).join(", "),
    remaining: sorted.length - maxVisible,
  };
}

/**
 * Tóm tắt danh sách cổng hiển thị ngoài bảng:
 * - Nếu không có cổng hoặc sự cố tài nguyên: "—"
 * - Nếu <= 2 cổng: hiển thị toàn bộ, ví dụ: "53", "80, 443"
 * - Nếu > 2 cổng: hiển thị 2 cổng đầu tiên và [+N] cổng còn lại, ví dụ: "80, 443 [+1]"
 */
export function formatPortSummary(ports?: number[] | null, maxVisible: number = 2): string {
  const summary = getPortSummary(ports, maxVisible);
  if (!summary) return "—";
  if (summary.remaining === 0) return summary.visible;
  return `${summary.visible} [+${summary.remaining}]`;
}

export type AssetCategory =
  | "web"
  | "database"
  | "admin"
  | "dns"
  | "recon"
  | "process"
  | "network";

export interface TargetedAsset {
  name: string;
  category: AssetCategory;
  ports: number[];
  protocol: string;
  badgeLabel: string;
  subLabel: string;
  riskSummary: string;
}

export function getTargetedAsset(params: {
  ports?: number[] | null;
  protocol?: string | null;
  detectorName?: string | null;
  processName?: string | null;
  pid?: number | string | null;
  title?: string | null;
  summary?: string | null;
}): TargetedAsset {
  const ports = params.ports && params.ports.length > 0 ? params.ports : [];
  const protocol = (params.protocol || "tcp").toLowerCase();
  const detector = (params.detectorName || "").toLowerCase();
  const title = (params.title || "").toLowerCase();
  const summary = (params.summary || "").toLowerCase();

  // 1. Kiểm tra sự cố tài nguyên hoặc tiến trình ứng dụng
  if (
    params.processName ||
    params.pid ||
    detector.includes("cpu") ||
    detector.includes("memory") ||
    detector.includes("disk") ||
    title.includes("cpu") ||
    title.includes("ram") ||
    title.includes("bộ nhớ") ||
    title.includes("worker")
  ) {
    const proc =
      params.processName ||
      (title.includes("celery") ? "celery-worker" : "tiến trình hệ thống");
    return {
      name: `Tiến trình ${proc}`,
      category: "process",
      ports: [],
      protocol: "Nội bộ",
      badgeLabel: `Tiến trình ${proc}`,
      subLabel: params.pid ? `PID: ${params.pid}` : "Vi xử lý / Bộ nhớ",
      riskSummary:
        "Tiến trình nội bộ chiếm dụng tài nguyên quá mức gây suy giảm hiệu năng hệ thống",
    };
  }

  // 2. Trích xuất cổng từ tiêu đề hoặc tóm tắt nếu mảng cổng bị rỗng
  let effectivePorts = [...ports];
  if (effectivePorts.length === 0) {
    if (
      title.includes("api gateway") ||
      title.includes("web") ||
      summary.includes("api") ||
      summary.includes("syn")
    ) {
      effectivePorts = [80, 443];
    } else if (title.includes("port scan") || title.includes("quét cổng")) {
      effectivePorts = [22, 80, 443, 3306, 5432];
    } else if (title.includes("udp") || summary.includes("udp")) {
      effectivePorts = [53];
    }
  }

  // 3. Quét đa cổng / Dò quét diện rộng
  if (
    effectivePorts.length >= 4 ||
    detector.includes("port_scan") ||
    title.includes("quét cổng") ||
    title.includes("port scan")
  ) {
    return {
      name: "Toàn bộ máy chủ (Dò quét đa cổng)",
      category: "recon",
      ports: effectivePorts,
      protocol: protocol.toUpperCase(),
      badgeLabel:
        effectivePorts.length > 0
          ? `Quét ${effectivePorts.length} cổng`
          : "Dò quét đa cổng",
      subLabel:
        effectivePorts.length > 0
          ? `Cổng ${effectivePorts.slice(0, 3).join(", ")}...`
          : "Dải cổng 1..65535",
      riskSummary:
        "Kẻ tấn công rà quét diện rộng để dò tìm dịch vụ và cổng sơ hở trên máy chủ",
    };
  }

  // 4. Dịch vụ Web (80, 443, 8080, 8000, 3000)
  if (
    effectivePorts.some((p) => [80, 443, 8080, 8000, 3000].includes(p)) ||
    title.includes("api") ||
    title.includes("web")
  ) {
    const portList = effectivePorts.filter((p) =>
      [80, 443, 8080, 8000, 3000].includes(p)
    );
    const labelPorts = portList.length > 0 ? portList.join(", ") : "80, 443";
    return {
      name: "Dịch vụ Web và Cổng vào Ingress",
      category: "web",
      ports: effectivePorts,
      protocol: protocol.toUpperCase(),
      badgeLabel: "Dịch vụ Web",
      subLabel: `Cổng ${labelPorts} / ${protocol.toUpperCase()}`,
      riskSummary:
        "Nguy cơ làm chậm hoặc tê liệt luồng truy cập của khách hàng vào website",
    };
  }

  // 5. Cơ sở dữ liệu (5432, 3306, 6379, 27017)
  if (
    effectivePorts.some((p) => [5432, 3306, 6379, 27017].includes(p)) ||
    title.includes("database") ||
    title.includes("cơ sở dữ liệu")
  ) {
    const isPg = effectivePorts.includes(5432);
    return {
      name: isPg ? "Cơ sở dữ liệu PostgreSQL" : "Cơ sở dữ liệu nội bộ",
      category: "database",
      ports: effectivePorts,
      protocol: protocol.toUpperCase(),
      badgeLabel: isPg ? "PostgreSQL" : "Cơ sở dữ liệu",
      subLabel: `Cổng ${effectivePorts.join(", ")} / ${protocol.toUpperCase()}`,
      riskSummary:
        "Nguy cơ làm tràn kết nối và nghẽn truy vấn dữ liệu nhạy cảm của hệ thống",
    };
  }

  // 6. Quản trị từ xa SSH (22, 3389)
  if (
    effectivePorts.some((p) => [22, 3389].includes(p)) ||
    title.includes("ssh")
  ) {
    return {
      name: "Dịch vụ quản trị từ xa SSH",
      category: "admin",
      ports: effectivePorts,
      protocol: protocol.toUpperCase(),
      badgeLabel: "Quản trị SSH",
      subLabel: `Cổng ${effectivePorts.join(", ")} / ${protocol.toUpperCase()}`,
      riskSummary:
        "Nguy cơ tấn công dò quét cô lập quyền điều khiển từ xa của người quản trị",
    };
  }

  // 7. Dịch vụ phân giải tên miền DNS (53)
  if (effectivePorts.includes(53) || title.includes("dns")) {
    return {
      name: "Dịch vụ phân giải tên miền DNS",
      category: "dns",
      ports: effectivePorts,
      protocol: protocol.toUpperCase(),
      badgeLabel: "Dịch vụ DNS",
      subLabel: `Cổng 53 / ${protocol.toUpperCase()}`,
      riskSummary:
        "Nguy cơ làm gián đoạn phân giải tên miền và nghẽn băng thông card mạng",
    };
  }

  // 8. Tầng mạng chung
  const portStr =
    effectivePorts.length > 0
      ? `Cổng ${effectivePorts.join(", ")}`
      : "Giao diện mạng";
  return {
    name:
      effectivePorts.length > 0
        ? `Dịch vụ tại cổng ${effectivePorts.join(", ")}`
        : "Card mạng máy chủ",
    category: "network",
    ports: effectivePorts,
    protocol: protocol.toUpperCase(),
    badgeLabel: "Mạng máy chủ",
    subLabel: `${portStr} / ${protocol.toUpperCase()}`,
    riskSummary: "Lưu lượng bất thường gây áp lực lên tầng mạng của máy chủ",
  };
}
