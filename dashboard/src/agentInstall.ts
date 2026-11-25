import type { AgentBundleInfo } from "./types";

export type AgentInstallMode = "bundle" | "dev";

export function getDefaultAgentControllerUrl(): string {
  if (import.meta.env.VITE_AGENT_CONTROLLER_URL) {
    return import.meta.env.VITE_AGENT_CONTROLLER_URL;
  }
  const protocol = typeof window !== "undefined" ? window.location.protocol : "http:";
  const hostname = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
  return `${protocol}//${hostname}:8000`;
}

export function normalizeControllerBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export function shellQuote(value: string): string {
  return "'" + value.replaceAll("'", "'\\''") + "'";
}

export function formatBundleSize(sizeBytes: number | null): string {
  if (sizeBytes === null || sizeBytes <= 0) return "";
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  const kb = sizeBytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

export function buildLinuxBundleCommand(params: {
  controllerUrl: string;
  nodeId: string;
  bundleInfo: AgentBundleInfo | null;
}): string {
  const baseUrl = normalizeControllerBaseUrl(params.controllerUrl);
  const downloadPath = params.bundleInfo?.download_path || "/api/v1/system/agent-bundle/download";
  const downloadUrl = `${baseUrl}${downloadPath.startsWith("/") ? "" : "/"}${downloadPath}`;

  const lines: string[] = [];
  if (
    params.bundleInfo?.available &&
    params.bundleInfo.filename &&
    params.bundleInfo.sha256 &&
    params.bundleInfo.release
  ) {
    const filename = params.bundleInfo.filename;
    const extractedDir = `sentinelx-agent-${params.bundleInfo.release}`;
    lines.push(
      `curl -fSLo ${shellQuote(filename)} ${shellQuote(downloadUrl)}`,
      `echo ${shellQuote(`${params.bundleInfo.sha256}  ${filename}`)} | sha256sum -c -`,
      `tar -xzf ${shellQuote(filename)} && cd ${shellQuote(extractedDir)}`,
    );
  } else {
    lines.push(
      `curl -fSLo 'sentinelx-agent.tar.gz' ${shellQuote(downloadUrl)}`,
      "tar -xzf 'sentinelx-agent.tar.gz' && cd sentinelx-agent-*",
    );
  }

  lines.push(
    "sudo python3 manage.py install \\",
    `  --controller-url ${shellQuote(baseUrl)} \\`,
    `  --node-id ${shellQuote(params.nodeId)} \\`,
    '  --uv "$(command -v uv)" --no-start',
    "sudo python3 manage.py enroll",
    "sudo python3 manage.py restart",
  );
  return lines.join("\n");
}

export function buildDevUvCommand(params: {
  controllerUrl: string;
  nodeId: string;
  token: string;
}): string {
  const baseUrl = normalizeControllerBaseUrl(params.controllerUrl);
  return [
    `export SENTINELX_CONTROLLER_URL=${shellQuote(baseUrl)}`,
    `export SENTINELX_NODE_ID=${shellQuote(params.nodeId)}`,
    `export SENTINELX_ENROLLMENT_TOKEN=${shellQuote(params.token)}`,
    "uv run python -m sentinelx_agent.main",
  ].join("\n");
}
