import { useState } from 'react';
import { X, Server, Key, Check, Copy } from 'lucide-react';
import type { Node } from '../types';
import { createEnrollmentToken } from '../api';

interface NodeDetailModalProps {
  node: Node | null;
  isOpen: boolean;
  onClose: () => void;
}

export const NodeDetailModal: React.FC<NodeDetailModalProps> = ({ node, isOpen, onClose }) => {
  const [token, setToken] = useState<string | null>(null);
  const [loadingToken, setLoadingToken] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!isOpen || !node) return null;

  const handleGenerateToken = async () => {
    try {
      setLoadingToken(true);
      const rawToken = await createEnrollmentToken(node.id, 24);
      setToken(rawToken);
    } catch {
      alert('Không thể cấp token lúc này');
    } finally {
      setLoadingToken(false);
    }
  };

  const handleCopy = () => {
    if (token) {
      navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} style={{ color: 'var(--primary)' }} />
            <h3 className="text-title" style={{ fontSize: '16px' }}>
              Chi Tiết Máy Chủ: {node.hostname}
            </h3>
          </div>
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '4px', borderRadius: '50%' }}
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        {/* Node Properties Table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-label">Node UUID</span>
            <span className="font-mono" style={{ fontSize: '12px' }}>{node.id}</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-label">Địa chỉ IP</span>
            <span className="font-mono">{node.ip_address}</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-label">Trạng thái</span>
            <span className={`status-badge ${node.status}`}>
              {node.status === 'online' ? 'Trực tuyến' : node.status === 'unenrolled' ? 'Chưa đăng ký' : 'Mất kết nối'}
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-label">Lần cuối phản hồi</span>
            <span className="font-mono" style={{ fontSize: '12px' }}>
              {node.last_seen ? new Date(node.last_seen).toLocaleString() : 'Chưa có dữ liệu'}
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-label">CPU / RAM hiện thời</span>
            <span className="font-mono">
              {node.latestCpu !== undefined ? `${node.latestCpu}% CPU` : '--'} •{' '}
              {node.latestMemory !== undefined ? `${node.latestMemory}% RAM` : '--'}
            </span>
          </div>
        </div>

        {/* Token Issuance Section */}
        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span className="text-label">Cấp Mã Enrollment Token Mới</span>
            <button
              className="btn btn-outline btn-sm"
              onClick={handleGenerateToken}
              disabled={loadingToken}
            >
              <Key size={13} />
              <span>{loadingToken ? 'Đang tạo...' : 'Tạo Token'}</span>
            </button>
          </div>

          {token && (
            <div style={{ marginTop: '8px' }}>
              <div className="code-box" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ wordBreak: 'break-all' }}>{token}</span>
                <button
                  className="btn btn-outline btn-sm"
                  style={{ marginLeft: '8px', color: '#fff', borderColor: '#475569' }}
                  onClick={handleCopy}
                >
                  {copied ? <Check size={13} style={{ color: 'var(--status-online)' }} /> : <Copy size={13} />}
                </button>
              </div>
              <p className="text-body" style={{ fontSize: '11px', marginTop: '4px' }}>
                Token này có hiệu lực trong 24 giờ để Agent thực hiện handshake enrollment ban đầu.
              </p>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button className="btn btn-primary btn-sm" onClick={onClose}>
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
