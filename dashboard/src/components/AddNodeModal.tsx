import { useId, useState } from "react";
import { ArrowRight, Check, Copy, Server, X } from "lucide-react";
import type { Project, Node } from "../types";
import { createNode, createEnrollmentToken } from "../api";
import { Modal } from "./Modal";

interface Props {
  projects: Project[];
  selectedProjectId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onNodeCreated: (node: Node) => void;
  isDemoMode: boolean;
}
export function AddNodeModal({
  projects,
  selectedProjectId,
  isOpen,
  onClose,
  onNodeCreated,
  isDemoMode,
}: Props) {
  const id = useId();
  const [projectId, setProjectId] = useState(
    selectedProjectId || projects[0]?.id || "",
  );
  const [hostname, setHostname] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [controllerUrl, setControllerUrl] = useState(
    import.meta.env.VITE_AGENT_CONTROLLER_URL || window.location.origin,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdNode, setCreatedNode] = useState<Node | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  if (!isOpen) return null;
  const close = () => {
    if (!loading) onClose();
  };
  const issueToken = async (nodeId: string) => {
    try {
      setLoading(true);
      setError(null);
      setToken(await createEnrollmentToken(nodeId, 24));
    } catch {
      setError(
        "Máy chủ đã được tạo nhưng chưa cấp được token. Bấm “Thử cấp token” để tiếp tục.",
      );
    } finally {
      setLoading(false);
    }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!hostname.trim() || !ipAddress.trim() || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const node: Node = isDemoMode
        ? {
            id: crypto.randomUUID(),
            project_id: projectId,
            hostname: hostname.trim(),
            ip_address: ipAddress.trim(),
            status: "unenrolled",
            last_seen: null,
            created_at: new Date().toISOString(),
          }
        : await createNode(projectId, hostname.trim(), ipAddress.trim());
      setCreatedNode(node);
      onNodeCreated(node);
      if (!isDemoMode) await issueToken(node.id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa thể đăng ký máy chủ. Kiểm tra kết nối và thử lại.",
      );
    } finally {
      setLoading(false);
    }
  };
  const shellQuote = (value: string) =>
    "'" + value.replaceAll("'", "'\\''") + "'";
  const command =
    createdNode && token
      ? [
          `export SENTINELX_CONTROLLER_URL=${shellQuote(controllerUrl)}`,
          `export SENTINELX_NODE_ID=${shellQuote(createdNode.id)}`,
          `export SENTINELX_ENROLLMENT_TOKEN=${shellQuote(token)}`,
          "uv run sentinelx-agent",
        ].join("\n")
      : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
    } catch {
      setError(
        "Không truy cập được clipboard. Bạn có thể chọn và sao chép lệnh bên dưới.",
      );
    }
  };

  return (
    <Modal onClose={close} labelledBy={`${id}-title`}>
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <Server size={15} /> {createdNode ? "Bước 2 · Kết nối Agent" : "Bước 1 · Thông tin máy chủ"}
          </span>
          <h2 id={`${id}-title`}>
            {createdNode ? "Đã đăng ký máy chủ" : "Đăng ký máy chủ"}
          </h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng đăng ký máy chủ"
          onClick={close}
          disabled={loading}
        >
          <X size={19} />
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!createdNode ? (
        <form onSubmit={submit}>
          <p className="text-body">
            {isDemoMode
              ? "Tạo máy chủ mẫu để khám phá giao diện. Agent thật và enrollment token chỉ khả dụng khi kết nối Controller."
              : "Đăng ký máy chủ Linux, sau đó kích hoạt Agent bằng enrollment token."}
          </p>
          <div className="form-group">
            <label htmlFor={`${id}-project`}>
              Dự án quản lý <span aria-hidden="true">*</span>
            </label>
            <select
              data-autofocus
              id={`${id}-project`}
              className="form-input"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              required
              disabled={loading}
            >
              <option value="" disabled>
                Chọn một dự án
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor={`${id}-hostname`}>
              Hostname <span aria-hidden="true">*</span>
            </label>
            <input
              id={`${id}-hostname`}
              className="form-input"
              placeholder="backend-01"
              value={hostname}
              onChange={(event) => setHostname(event.target.value)}
              required
              pattern={".*\\S.*"}
              maxLength={253}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label htmlFor={`${id}-ip`}>
              Địa chỉ IP <span aria-hidden="true">*</span>
            </label>
            <input
              id={`${id}-ip`}
              className="form-input font-mono"
              placeholder="192.168.1.15"
              value={ipAddress}
              onChange={(event) => setIpAddress(event.target.value)}
              required
              pattern={".*\\S.*"}
              disabled={loading}
            />
            <small className="field-hint">
              Địa chỉ máy chủ mà Controller có thể truy cập.
            </small>
          </div>
          {!isDemoMode && (
            <div className="form-group">
              <label htmlFor={`${id}-url`}>Controller URL</label>
              <input
                id={`${id}-url`}
                className="form-input font-mono"
                type="url"
                value={controllerUrl}
                onChange={(event) => setControllerUrl(event.target.value)}
                required
                disabled={loading}
              />
              <small className="field-hint">
                URL mà Agent trên máy Linux sẽ dùng để gửi dữ liệu.
              </small>
            </div>
          )}
          {!projects.length && (
            <p className="form-error">
              Workspace chưa có dự án. Tạo dự án trên Controller trước khi thêm
              máy chủ.
            </p>
          )}
          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-outline"
              onClick={close}
              disabled={loading}
            >
              Hủy
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !projects.length}
            >
              {loading
                ? "Đang đăng ký…"
                : isDemoMode
                  ? "Tạo máy chủ mẫu"
                  : "Đăng ký & cấp token"}
              <ArrowRight size={15} />
            </button>
          </div>
        </form>
      ) : (
        <div className="modal-body">
          <div className="success-note">
            <Check size={20} />
            <div>
              <strong>{createdNode.hostname}</strong>
              <p>
                {isDemoMode
                  ? "Máy chủ mẫu đã được thêm vào workspace."
                  : "Đã đăng ký máy chủ với Controller."}
              </p>
            </div>
          </div>
          {command && (
            <>
              <p className="text-body">
                Chạy lệnh sau trên máy Linux đích. Token có hiệu lực 24 giờ.
              </p>
              <div className="code-box">
                <pre>{command}</pre>
              </div>
              <button className="btn btn-outline" onClick={copy}>
                {copied ? <Check size={15} /> : <Copy size={15} />}
                {copied ? "Đã sao chép" : "Sao chép lệnh cài Agent"}
              </button>
            </>
          )}
          {!token && !isDemoMode && (
            <button
              className="btn btn-outline"
              onClick={() => void issueToken(createdNode.id)}
              disabled={loading}
            >
              {loading ? "Đang cấp token…" : "Thử cấp token"}
            </button>
          )}
          <div className="modal-actions">
            <button
              className="btn btn-primary"
              onClick={close}
              disabled={loading}
            >
              Hoàn tất <Check size={15} />
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
