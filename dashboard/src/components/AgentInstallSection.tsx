import { useEffect, useId, useRef, useState } from "react";
import { Check, Copy, Download, Terminal } from "lucide-react";
import type { AgentBundleInfo } from "../types";
import {
  type AgentInstallMode,
  buildDevUvCommand,
  buildLinuxBundleCommand,
  formatBundleSize,
} from "../agentInstall";

interface Props {
  nodeId: string;
  token: string;
  controllerUrl: string;
  onControllerUrlChange?: (nextUrl: string) => void;
  bundleInfo: AgentBundleInfo | null;
  bundleLoading?: boolean;
}

export function AgentInstallSection({
  nodeId,
  token,
  controllerUrl,
  onControllerUrlChange,
  bundleInfo,
  bundleLoading = false,
}: Props) {
  const id = useId();
  const [mode, setMode] = useState<AgentInstallMode>("bundle");
  const [copiedTarget, setCopiedTarget] = useState<"command" | "token" | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
    };
  }, []);

  const command =
    mode === "bundle"
      ? buildLinuxBundleCommand({ controllerUrl, nodeId, bundleInfo })
      : buildDevUvCommand({ controllerUrl, nodeId, token });

  const downloadPath = bundleInfo?.download_path || "/api/v1/system/agent-bundle/download";

  const copyText = async (value: string, target: "command" | "token") => {
    try {
      await navigator.clipboard.writeText(value);
      setCopyError(null);
      setCopiedTarget(target);
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
      copyTimerRef.current = window.setTimeout(() => {
        setCopiedTarget(null);
        copyTimerRef.current = null;
      }, 2000);
    } catch {
      setCopyError("Không truy cập được clipboard. Chọn nội dung bên dưới để sao chép thủ công.");
    }
  };

  return (
    <div className="agent-install-section">
      {onControllerUrlChange && (
        <div className="form-group">
          <label htmlFor={`${id}-controller-url`}>Controller URL cho máy Linux</label>
          <input
            id={`${id}-controller-url`}
            className="form-input font-mono"
            type="url"
            value={controllerUrl}
            onChange={(event) => onControllerUrlChange(event.target.value)}
            required
          />
          <small className="field-hint">
            Đổi sang IP LAN của máy Controller nếu cài Agent từ máy chủ Linux khác.
          </small>
        </div>
      )}

      <div
        className="lb-algo-segmented lb-algo-segmented-full install-mode-tabs"
        role="tablist"
        aria-label="Phương thức cài đặt Agent"
      >
        <button
          type="button"
          role="tab"
          aria-selected={mode === "bundle"}
          className={mode === "bundle" ? "active" : ""}
          onClick={() => setMode("bundle")}
        >
          Cài chuẩn Linux (systemd)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "dev"}
          className={mode === "dev" ? "active" : ""}
          onClick={() => setMode("dev")}
        >
          Chạy nhanh (uv run)
        </button>
      </div>

      {copyError && (
        <p className="form-error" role="alert">
          {copyError}
        </p>
      )}

      {mode === "bundle" ? (
        <div className="install-mode-panel" role="tabpanel" aria-label="Cài chuẩn Linux">
          {bundleLoading ? (
            <p className="field-hint">Đang kiểm tra gói cài đặt Agent trên Controller…</p>
          ) : bundleInfo?.available && bundleInfo.filename ? (
            <div className="bundle-meta-bar">
              <div className="bundle-meta-info">
                <span className="bundle-meta-title font-mono">
                  {bundleInfo.filename}
                </span>
                <span className="bundle-meta-sub font-mono">
                  {formatBundleSize(bundleInfo.size_bytes)}
                  {bundleInfo.sha256 ? ` · sha256:${bundleInfo.sha256.slice(0, 12)}…` : ""}
                </span>
              </div>
              <a
                className="btn btn-outline btn-sm"
                href={downloadPath}
                download={bundleInfo.filename}
              >
                <Download size={14} />
                Tải gói .tar.gz
              </a>
            </div>
          ) : bundleInfo && !bundleInfo.available ? (
            <p className="field-hint install-bundle-warning">
              Controller chưa có sẵn gói bundle. Chạy{" "}
              <code className="font-mono">uv run python scripts/build_agent_bundle.py --allow-existing</code>{" "}
              trên Controller hoặc dùng tab “Chạy nhanh (uv run)”.
            </p>
          ) : null}

          <p className="text-body">
            Chạy trên máy Linux (đã cài <code className="font-mono">uv</code>, <code className="font-mono">curl</code> và <code className="font-mono">systemd</code>). Token có hiệu lực 24 giờ:
          </p>
          <div className="code-box">
            <pre>{command}</pre>
          </div>
          <div className="install-actions-row">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => void copyText(command, "command")}
            >
              {copiedTarget === "command" ? <Check size={15} /> : <Copy size={15} />}
              {copiedTarget === "command" ? "Đã sao chép lệnh" : "Sao chép lệnh cài đặt"}
            </button>
          </div>

          <div className="install-token-panel">
            <div className="install-token-header">
              <span>Token đăng ký 1 lần (dán khi <code className="font-mono">manage.py enroll</code> hỏi)</span>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                aria-label="Sao chép token đăng ký"
                onClick={() => void copyText(token, "token")}
              >
                {copiedTarget === "token" ? <Check size={14} /> : <Copy size={14} />}
                {copiedTarget === "token" ? "Đã sao chép token" : "Sao chép token"}
              </button>
            </div>
            <div className="code-box install-token-box">
              <code className="font-mono">{token}</code>
            </div>
          </div>
        </div>
      ) : (
        <div className="install-mode-panel" role="tabpanel" aria-label="Chạy nhanh uv run">
          <p className="text-body install-dev-lead">
            <Terminal size={15} aria-hidden="true" />
            <span>
              Dùng trên máy thử nghiệm đã clone sẵn mã nguồn SentinelX và cài{" "}
              <code className="font-mono">uv</code>:
            </span>
          </p>
          <div className="code-box">
            <pre>{command}</pre>
          </div>
          <div className="install-actions-row">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => void copyText(command, "command")}
            >
              {copiedTarget === "command" ? <Check size={15} /> : <Copy size={15} />}
              {copiedTarget === "command" ? "Đã sao chép lệnh" : "Sao chép lệnh chạy Agent"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
