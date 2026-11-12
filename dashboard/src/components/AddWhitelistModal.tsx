import { useId, useState } from "react";
import { ShieldCheck, ShieldAlert, X } from "lucide-react";
import type { IPWhitelist } from "../types";
import { createWhitelist } from "../api";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onWhitelistCreated: (item: IPWhitelist) => void;
  isDemoMode: boolean;
}

export function AddWhitelistModal({
  isOpen,
  onClose,
  projectId,
  onWhitelistCreated,
  isDemoMode,
}: Props) {
  const id = useId();
  const [cidr, setCidr] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedCidr = cidr.trim();
    if (!trimmedCidr) {
      setError("Vui lòng nhập dải IP hoặc định dạng CIDR");
      return;
    }

    // Basic CIDR / IP validation
    const cidrRegex = /^([0-9]{1,3}\.){3}[0-9]{1,3}(\/([0-9]|[1-2][0-9]|3[0-2]))?$/;
    const isIpv6 = trimmedCidr.includes(":");
    if (!isIpv6 && !cidrRegex.test(trimmedCidr)) {
      setError("Định dạng CIDR không hợp lệ (ví dụ: 192.168.1.0/24 hoặc 10.0.0.1/32)");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        const mockItem: IPWhitelist = {
          id: `wl-${Date.now()}`,
          project_id: projectId,
          cidr: trimmedCidr.includes("/") ? trimmedCidr : `${trimmedCidr}/32`,
          description: description.trim() || null,
          created_at: new Date().toISOString(),
        };
        onWhitelistCreated(mockItem);
        onClose();
        return;
      }

      const res = await createWhitelist(
        projectId,
        trimmedCidr.includes("/") ? trimmedCidr : `${trimmedCidr}/32`,
        description.trim() || undefined
      );
      onWhitelistCreated(res);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi thêm IP an toàn");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="whitelist-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <ShieldCheck size={15} style={{ color: "var(--status-ok)" }} /> Danh sách loại trừ an toàn
          </span>
          <h2 id={`${id}-title`}>Thêm Dải IP An Toàn (Whitelist)</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng biểu mẫu thêm IP an toàn"
          onClick={onClose}
          disabled={loading}
        >
          <X size={18} />
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="modal-body">
          {error && (
            <div className="form-error" role="alert">
              <ShieldAlert size={15} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label htmlFor={`${id}-cidr`}>Dải IP hoặc CIDR (IPv4 / IPv6)</label>
            <input
              id={`${id}-cidr`}
              type="text"
              className="font-mono"
              placeholder="ví dụ: 192.168.1.0/24 hoặc 10.0.0.5/32"
              value={cidr}
              onChange={(e) => setCidr(e.target.value)}
              disabled={loading}
              data-autofocus
            />
            <small className="form-hint">
              Các IP trong dải này sẽ được bảo vệ tuyệt đối — Controller và Agent sẽ không bao giờ kích hoạt DROP tại tường lửa.
            </small>
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-desc`}>Mô tả mục đích sử dụng</label>
            <input
              id={`${id}-desc`}
              type="text"
              placeholder="ví dụ: Dải mạng VPN kỹ thuật, IP máy chủ DNS, Gateway..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            <ShieldCheck size={16} />
            {loading ? "Đang lưu..." : "Thêm vào danh sách an toàn"}
          </button>
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            disabled={loading}
          >
            Hủy bỏ
          </button>
        </div>
      </form>
    </Modal>
  );
}

