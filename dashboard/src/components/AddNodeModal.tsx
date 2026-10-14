import { useState } from 'react';
import { X, Check, Copy } from 'lucide-react';
import type { Project, Node } from '../types';
import { createNode, createEnrollmentToken } from '../api';

interface AddNodeModalProps {
  projects: Project[];
  selectedProjectId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onNodeCreated: (node: Node) => void;
}

export const AddNodeModal: React.FC<AddNodeModalProps> = ({
  projects,
  selectedProjectId,
  isOpen,
  onClose,
  onNodeCreated,
}) => {
  const [projectId, setProjectId] = useState<string>(selectedProjectId || (projects[0]?.id || ''));
  const [hostname, setHostname] = useState('');
  const [ipAddress, setIpAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Success step with token & command
  const [createdNode, setCreatedNode] = useState<Node | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !hostname || !ipAddress) {
      setError('Vui lòng điền đầy đủ thông tin máy chủ');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const node = await createNode(projectId, hostname.trim(), ipAddress.trim());
      const rawToken = await createEnrollmentToken(node.id, 24);
      setCreatedNode(node);
      setToken(rawToken);
      onNodeCreated(node);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Lỗi khi đăng ký node');
    } finally {
      setLoading(false);
    }
  };

  const agentCommand = createdNode && token
    ? `export SENTINELX_CONTROLLER_URL="http://${window.location.hostname}:8000"\nexport SENTINELX_NODE_ID="${createdNode.id}"\nexport SENTINELX_ENROLLMENT_TOKEN="${token}"\nuv run sentinelx-agent`
    : '';

  const handleCopy = () => {
    if (agentCommand) {
      navigator.clipboard.writeText(agentCommand);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    setCreatedNode(null);
    setToken(null);
    setHostname('');
    setIpAddress('');
    setError(null);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="text-title" style={{ fontSize: '16px' }}>
            {createdNode ? 'Khởi Tạo Agent Thành Công' : 'Đăng Ký Máy Chủ Mới (Node)'}
          </h3>
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '4px', borderRadius: '50%' }}
            onClick={handleClose}
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: '10px 14px',
              backgroundColor: 'var(--status-critical-bg)',
              color: 'var(--status-critical)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        {!createdNode ? (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="text-label">Dự án quản lý:</label>
              <select
                className="form-input"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="text-label">Tên Máy Chủ (Hostname):</label>
              <input
                className="form-input"
                type="text"
                placeholder="vd: server-backend-01"
                value={hostname}
                onChange={(e) => setHostname(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="text-label">Địa chỉ IP:</label>
              <input
                className="form-input font-mono"
                type="text"
                placeholder="vd: 192.168.1.15 hoặc 10.0.0.5"
                value={ipAddress}
                onChange={(e) => setIpAddress(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '24px' }}>
              <button type="button" className="btn btn-outline" onClick={handleClose}>
                Hủy bỏ
              </button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? 'Đang tạo...' : 'Tiếp tục & Cấp Token'}
              </button>
            </div>
          </form>
        ) : (
          <div>
            <p className="text-body" style={{ fontSize: '13px' }}>
              Máy chủ <strong>{createdNode.hostname}</strong> đã được tạo. Chạy lệnh sau trên máy chủ Linux mục tiêu để Agent kích hoạt:
            </p>

            <div className="code-box">
              <pre>{agentCommand}</pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
              <button className="btn btn-outline btn-sm" onClick={handleCopy}>
                {copied ? <Check size={14} style={{ color: 'var(--status-online)' }} /> : <Copy size={14} />}
                <span>{copied ? 'Đã sao chép' : 'Sao chép lệnh bash'}</span>
              </button>

              <button className="btn btn-primary btn-sm" onClick={handleClose}>
                Hoàn tất
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
