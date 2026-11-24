import type {
  DefenseAction,
  DefensePolicy,
  DetectionSeverity,
  IPWhitelist,
  Incident,
  IncidentDefenseStatus,
  Node,
} from "./types";

export const SEVERITY_LABELS: Record<DetectionSeverity, string> = {
  MEDIUM: "Trung bình",
  HIGH: "Cao",
  CRITICAL: "Khẩn cấp",
};

export function severityLabel(severity: string, fallback = severity): string {
  return Object.hasOwn(SEVERITY_LABELS, severity)
    ? SEVERITY_LABELS[severity as DetectionSeverity]
    : fallback;
}
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

export function formatCapacityPair(usedBytes: number, totalBytes: number): string {
  if (!validMetric(usedBytes) || !validMetric(totalBytes) || totalBytes <= 0) return "—";
  const index = Math.min(3, Math.floor(Math.log(totalBytes) / Math.log(1024)));
  const unit = ["B", "KB", "MB", "GB"][index];
  const divisor = 1024 ** index;
  const usedVal = (usedBytes / divisor).toFixed(1);
  const totalVal = (totalBytes / divisor).toFixed(1);
  return `${usedVal} / ${totalVal} ${unit}`;
}

export function formatMemoryUsage(percent?: number, totalBytes?: number): string {
  if (!validMetric(percent)) return "—";
  const total = totalBytes ?? 2 * 1024 * 1024 * 1024;
  const usedBytes = (percent / 100) * total;
  return formatCapacityPair(usedBytes, total);
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
  return formatCapacityPair(usedBytes, total);
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

export type IncidentHandlingMode = "auto" | "manual";

export interface IncidentHandlingInfo {
  mode: IncidentHandlingMode;
  detectorType: string | null;
  label: string;
  reason: string;
}

const POLICY_ACTION_SHORT_LABELS: Record<string, string> = {
  BLOCK_IP_NFTABLES: "Khóa IP tường lửa",
  ADAPTIVE: "Tự động tối ưu",
  RESTART_SERVICE: "Khởi động lại dịch vụ",
  CLEAR_OS_CACHE: "Giải phóng bộ nhớ đệm",
  RATE_LIMIT: "Giới hạn tốc độ",
};

export function inferIncidentDetector(
  incident: Pick<Incident, "title" | "summary">,
  explicitDetector?: string | null,
): string | null {
  if (explicitDetector) return explicitDetector;
  const title = incident.title.toLowerCase();
  const summary = (incident.summary || "").toLowerCase();
  if (title.includes("syn") || summary.includes("syn:")) return "syn_flood_detector";
  if (title.includes("quét cổng") || title.includes("port scan")) return "port_scan_detector";
  if (title.includes("udp") || title.includes("lưu lượng") || title.includes("traffic")) {
    return "traffic_spike_detector";
  }
  if (title.includes("cpu") || summary.startsWith("cpu:")) return "cpu_threshold_detector";
  if (title.includes("ram") || title.includes("memory") || summary.startsWith("ram:")) {
    return "memory_exhaustion_detector";
  }
  if (title.includes("đĩa") || title.includes("disk") || summary.includes("ổ đĩa")) {
    return "disk_saturation_detector";
  }
  return null;
}

export function classifyIncidentHandling(
  incident: Pick<Incident, "status" | "title" | "summary" | "attacker_ip">,
  policies: DefensePolicy[],
  explicitDetector?: string | null,
): IncidentHandlingInfo {
  const detectorType = inferIncidentDetector(incident, explicitDetector);

  const lowerSummary = (incident.summary || "").toLowerCase();
  if (incident.status === "MITIGATING" || lowerSummary.includes("nftables:")) {
    if (lowerSummary.includes("os-cache:")) {
      return {
        mode: "auto",
        detectorType,
        label: "Tự động · Giải phóng bộ nhớ đệm",
        reason: "Đã kích hoạt giải phóng bộ nhớ đệm hệ điều hành",
      };
    }
    if (
      lowerSummary.includes("service:") ||
      detectorType === "cpu_threshold_detector" ||
      detectorType === "memory_exhaustion_detector"
    ) {
      return {
        mode: "auto",
        detectorType,
        label: "Tự động · Khởi động lại dịch vụ",
        reason: "Đã kích hoạt lệnh khởi động lại dịch vụ gây quá tải",
      };
    }
    return {
      mode: "auto",
      detectorType,
      label: "Tự động · nftables",
      reason: "Đã kích hoạt lệnh chặn tự động qua tường lửa nftables",
    };
  }

  const matching = detectorType
    ? policies.filter((p) => p.event_type === detectorType)
    : [];
  const activePolicy = matching.find((p) => p.is_active);

  if (!activePolicy) {
    return {
      mode: "manual",
      detectorType,
      label: "Chỉ báo cáo",
      reason:
        matching.length > 0
          ? "Chính sách tự động đang tắt — cần xử lý thủ công"
          : "Chưa có chính sách tự động — cần xử lý thủ công",
    };
  }

  if (activePolicy.action_type === "ALERT_ONLY" || !activePolicy.is_auto_execute) {
    return {
      mode: "manual",
      detectorType,
      label: "Chỉ báo cáo",
      reason:
        activePolicy.action_type === "ALERT_ONLY"
          ? "Chính sách chỉ ghi nhận cảnh báo — cần xử lý thủ công"
          : "Chính sách tắt tự động thực thi — cần xử lý thủ công",
    };
  }

  if (activePolicy.action_type === "BLOCK_IP_NFTABLES" && !incident.attacker_ip) {
    return {
      mode: "manual",
      detectorType,
      label: "Chỉ báo cáo",
      reason: "Thiếu IP nguồn tấn công để chặn tự động — cần xử lý thủ công",
    };
  }

  const actionLabel =
    POLICY_ACTION_SHORT_LABELS[activePolicy.action_type] ?? activePolicy.action_type;
  return {
    mode: "auto",
    detectorType,
    label: `Tự động · ${actionLabel}`,
    reason: `Chính sách "${activePolicy.name}" tự động thực thi`,
  };
}

export function isDeliveryFailureMessage(errorMessage?: string | null): boolean {
  if (!errorMessage) return false;
  const lower = errorMessage.toLowerCase();
  return (
    lower.includes("advertise support") ||
    lower.includes("expired") ||
    lower.includes("delivery attempts exhausted")
  );
}

export function resolveIncidentDefenseFailure(
  incident: Pick<Incident, "id" | "status" | "summary" | "defense_status">,
  defenseActions?: DefenseAction[],
): IncidentDefenseStatus | null {
  if (incident.status !== "DETECTED") return null;
  if (
    incident.defense_status === "DELIVERY_FAILED" ||
    incident.defense_status === "EXECUTION_FAILED"
  ) {
    return incident.defense_status;
  }
  const summary = incident.summary || "";
  if (summary.includes("lỗi tải lệnh:")) return "DELIVERY_FAILED";
  if (summary.includes("lỗi kích hoạt:")) return "EXECUTION_FAILED";
  if (defenseActions && defenseActions.length > 0) {
    const related = defenseActions
      .filter((a) => a.incident_id === incident.id && a.action_type !== "UNBLOCK_IP_NFTABLES")
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    const latest = related[0];
    if (latest) {
      if (
        latest.status === "EXPIRED" ||
        (latest.status === "FAILED" && isDeliveryFailureMessage(latest.error_message))
      ) {
        return "DELIVERY_FAILED";
      }
      if (latest.status === "FAILED") {
        return "EXECUTION_FAILED";
      }
    }
  }
  return null;
}

interface ParsedIp {
  family: 4 | 6;
  parts: number[];
}

function parseIPv4(raw: string): ParsedIp | null {
  const match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(raw);
  if (!match) return null;
  const octets: number[] = [];
  for (let i = 1; i <= 4; i++) {
    const seg = match[i];
    if (seg.length > 1 && seg.startsWith("0")) return null;
    const val = Number(seg);
    if (!Number.isInteger(val) || val < 0 || val > 255) return null;
    octets.push(val);
  }
  return { family: 4, parts: octets };
}

function parseIPv6(raw: string): ParsedIp | null {
  if (!raw.includes(":") || raw.includes("%")) return null;
  const doubleColonParts = raw.split("::");
  if (doubleColonParts.length > 2) return null;

  const parseSide = (side: string, allowIpv4Tail: boolean): number[] | null => {
    if (!side) return [];
    const tokens = side.split(":");
    const out: number[] = [];
    for (let i = 0; i < tokens.length; i++) {
      const tok = tokens[i];
      if (!tok) return null;
      if (tok.includes(".")) {
        if (!allowIpv4Tail || i !== tokens.length - 1) return null;
        const v4 = parseIPv4(tok);
        if (!v4) return null;
        out.push((v4.parts[0] << 8) | v4.parts[1], (v4.parts[2] << 8) | v4.parts[3]);
      } else {
        if (!/^[0-9a-fA-F]{1,4}$/.test(tok)) return null;
        out.push(Number.parseInt(tok, 16));
      }
    }
    return out;
  };

  if (doubleColonParts.length === 1) {
    const groups = parseSide(raw, true);
    if (!groups || groups.length !== 8) return null;
    return { family: 6, parts: groups };
  }

  const head = parseSide(doubleColonParts[0], false);
  const tail = parseSide(doubleColonParts[1], true);
  if (!head || !tail) return null;
  const missing = 8 - head.length - tail.length;
  if (missing < 1) return null;
  return { family: 6, parts: [...head, ...Array<number>(missing).fill(0), ...tail] };
}

function parseIp(raw: string): ParsedIp | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  return parseIPv4(trimmed) ?? parseIPv6(trimmed);
}

function sameParsedIp(a: ParsedIp, b: ParsedIp): boolean {
  return a.family === b.family && a.parts.every((val, idx) => val === b.parts[idx]);
}

function ipMatchesCidr(ip: ParsedIp, cidrRaw: string): boolean {
  const trimmed = cidrRaw.trim();
  const slashIdx = trimmed.indexOf("/");
  const baseStr = slashIdx >= 0 ? trimmed.slice(0, slashIdx) : trimmed;
  const network = parseIp(baseStr);
  if (!network || network.family !== ip.family) return false;

  const bitsPerPart = ip.family === 4 ? 8 : 16;
  const maxPrefix = ip.family === 4 ? 32 : 128;
  const prefix = slashIdx >= 0 ? Number(trimmed.slice(slashIdx + 1)) : maxPrefix;
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > maxPrefix) return false;

  let remaining = prefix;
  for (let i = 0; i < ip.parts.length && remaining > 0; i++) {
    const bits = Math.min(bitsPerPart, remaining);
    const shift = bitsPerPart - bits;
    if (ip.parts[i] >> shift !== network.parts[i] >> shift) {
      return false;
    }
    remaining -= bits;
  }
  return true;
}

export interface ManualIpCheckResult {
  status: "empty" | "valid" | "invalid";
  valid: boolean;
  message: string;
}

export function validateManualBlockIp(
  rawIp: string,
  node: Node | undefined,
  whitelist: IPWhitelist[],
  existingActions: DefenseAction[],
): ManualIpCheckResult {
  const trimmed = rawIp.trim();
  if (!trimmed) {
    return {
      status: "empty",
      valid: false,
      message: "Nhập địa chỉ IPv4 hoặc IPv6; hệ thống tự kiểm tra hợp lệ trước khi kích hoạt.",
    };
  }

  const parsed = parseIp(trimmed);
  if (!parsed) {
    return {
      status: "invalid",
      valid: false,
      message: "Định dạng IP không hợp lệ (ví dụ: 203.0.113.195 hoặc 2001:db8::1).",
    };
  }

  if (parsed.family === 4) {
    const [o0, o1] = parsed.parts;
    if (o0 === 127) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ loopback nội bộ (127.0.0.0/8).",
      };
    }
    if (o0 === 0) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ không xác định (0.0.0.0/8).",
      };
    }
    if (o0 === 169 && o1 === 254) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ link-local nội bộ (169.254.0.0/16).",
      };
    }
    if (o0 >= 224) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn dải IP multicast hoặc dải dành riêng.",
      };
    }
  } else {
    const isAllZero = parsed.parts.every((p) => p === 0);
    const isLoopback6 = parsed.parts.slice(0, 7).every((p) => p === 0) && parsed.parts[7] === 1;
    if (isLoopback6) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ loopback IPv6 (::1).",
      };
    }
    if (isAllZero) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ không xác định IPv6 (::).",
      };
    }
    if ((parsed.parts[0] & 0xffc0) === 0xfe80) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ link-local IPv6 (fe80::/10).",
      };
    }
    if ((parsed.parts[0] & 0xff00) === 0xff00) {
      return {
        status: "invalid",
        valid: false,
        message: "Từ chối: Không thể chặn địa chỉ multicast IPv6 (ff00::/8).",
      };
    }
  }

  if (node?.ip_address) {
    const nodeParsed = parseIp(node.ip_address);
    if (nodeParsed && sameParsedIp(parsed, nodeParsed)) {
      return {
        status: "invalid",
        valid: false,
        message: `Từ chối: Trùng địa chỉ IP của chính máy chủ đang chọn (${node.ip_address}).`,
      };
    }
  }

  for (const entry of whitelist) {
    if (entry.cidr && ipMatchesCidr(parsed, entry.cidr)) {
      return {
        status: "invalid",
        valid: false,
        message: `Từ chối: IP thuộc Danh sách an toàn (${entry.cidr})${
          entry.description ? ` — ${entry.description}` : ""
        }.`,
      };
    }
  }

  const activeDup = existingActions.find((act) => {
    if (node && act.node_id !== node.id) return false;
    if (act.action_type !== "BLOCK_IP_NFTABLES") return false;
    if (act.status !== "PENDING" && act.status !== "SENT" && act.status !== "APPLIED") return false;
    if (!act.target_ip) return false;
    const actParsed = parseIp(act.target_ip);
    return actParsed ? sameParsedIp(parsed, actParsed) : false;
  });
  if (activeDup) {
    return {
      status: "invalid",
      valid: false,
      message: "IP này đang bị chặn hoặc đang chờ áp dụng trên máy chủ đã chọn.",
    };
  }

  return {
    status: "valid",
    valid: true,
    message: node
      ? `IP hợp lệ — sẵn sàng chặn trên ${node.hostname}.`
      : "IP hợp lệ — sẵn sàng chặn.",
  };
}

export interface WhitelistCheckResult {
  status: "empty" | "valid" | "invalid";
  valid: boolean;
  normalized: string;
  message: string;
}

export function validateWhitelistCidr(
  rawInput: string,
  existingWhitelist: IPWhitelist[] = [],
): WhitelistCheckResult {
  const trimmed = rawInput.trim();
  if (!trimmed) {
    return {
      status: "empty",
      valid: false,
      normalized: "",
      message: "Nhập IP lẻ hoặc dải CIDR (ví dụ: 192.168.1.0/24 hoặc 2001:db8::/48).",
    };
  }

  const slashIdx = trimmed.indexOf("/");
  const baseStr = slashIdx >= 0 ? trimmed.slice(0, slashIdx).trim() : trimmed;
  const parsedBase = parseIp(baseStr);
  if (!parsedBase || !baseStr) {
    return {
      status: "invalid",
      valid: false,
      normalized: trimmed,
      message: "Định dạng IP hoặc CIDR không hợp lệ (ví dụ: 192.168.1.0/24 hoặc 10.0.0.5).",
    };
  }

  if (slashIdx >= 0) {
    const prefixStr = trimmed.slice(slashIdx + 1).trim();
    const maxPrefix = parsedBase.family === 4 ? 32 : 128;
    if (!/^\d{1,3}$/.test(prefixStr)) {
      return {
        status: "invalid",
        valid: false,
        normalized: trimmed,
        message: `Độ dài tiền tố CIDR không hợp lệ (cần từ 0 đến ${maxPrefix}).`,
      };
    }
    const prefix = Number(prefixStr);
    if (!Number.isInteger(prefix) || prefix < 0 || prefix > maxPrefix) {
      return {
        status: "invalid",
        valid: false,
        normalized: trimmed,
        message: `Tiền tố CIDR phải nằm trong khoảng 0..${maxPrefix}.`,
      };
    }
  }

  const normalized = trimmed;
  const dup = existingWhitelist.find((entry) => entry.cidr.trim().toLowerCase() === normalized.toLowerCase());
  if (dup) {
    return {
      status: "invalid",
      valid: false,
      normalized,
      message: `Mục ${dup.cidr} đã tồn tại trong Danh sách an toàn.`,
    };
  }

  return {
    status: "valid",
    valid: true,
    normalized,
    message: slashIdx >= 0 ? "Dải mạng CIDR hợp lệ — sẵn sàng bảo vệ." : "Địa chỉ IP hợp lệ — sẵn sàng bảo vệ.",
  };
}

export function formatPolicyDuration(seconds: number): string {
  if (seconds <= 0) return "Theo chính sách";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins >= 60) {
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return remMins > 0 ? `${hours} giờ ${remMins} phút` : `${hours} giờ`;
  }
  if (mins > 0) {
    return secs > 0 ? `${mins} phút ${secs} giây` : `${mins} phút`;
  }
  return `${secs} giây`;
}
