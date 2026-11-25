import { useId, useMemo, useState } from "react";
import { CheckCircle2, ShieldAlert, ShieldCheck, X } from "lucide-react";
import type { IPWhitelist } from "../types";
import { createWhitelist } from "../api";
import { validateWhitelistCidr } from "../presentation";
import { Modal } from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  existingWhitelist?: IPWhitelist[];
  onWhitelistCreated: (item: IPWhitelist) => void;
}

export function AddWhitelistModal({
  isOpen,
  onClose,
  projectId,
  existingWhitelist = [],
  onWhitelistCreated,
}: Props) {
  const id = useId();
  const [cidr, setCidr] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cidrCheck = useMemo(
    () => validateWhitelistCidr(cidr, existingWhitelist),
    [cidr, existingWhitelist],
  );

  if (!isOpen) return null;

  const resetAndClose = () => {
    setCidr("");
    setDescription("");
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cidrCheck.valid) {
      setError(cidrCheck.message);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await createWhitelist(
        projectId,
        cidrCheck.normalized,
        description.trim() || undefined,
      );
      onWhitelistCreated(res);
      resetAndClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi thêm IP an toàn");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClose={resetAndClose} labelledBy={`${id}-title`} className="whitelist-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <ShieldCheck size={15} style={{ color: "var(--status-ok)" }} /> Danh sách an toàn
          </span>
          <h2 id={`${id}-title`}>Thêm IP an toàn</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng biểu mẫu thêm IP an toàn"
          onClick={resetAndClose}
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
            <label htmlFor={`${id}-cidr`}>IP hoặc CIDR (IPv4 / IPv6)</label>
            <input
              id={`${id}-cidr`}
              type="text"
              className="font-mono"
              placeholder="ví dụ: 192.168.1.0/24 hoặc 10.0.0.5"
              value={cidr}
              onChange={(e) => {
                setCidr(e.target.value);
                if (error) setError(null);
              }}
              aria-invalid={cidrCheck.status === "invalid"}
              disabled={loading}
              data-autofocus
            />
            {cidrCheck.status === "empty" ? (
              <small className="field-hint">
                Các địa chỉ IP này được bảo vệ tuyệt đối — hệ thống sẽ không bao giờ chặn qua tường lửa.
              </small>
            ) : (
              <div
                className={`ip-check-feedback ${cidrCheck.valid ? "is-valid" : "is-invalid"}`}
                role={cidrCheck.valid ? "status" : "alert"}
              >
                {cidrCheck.valid ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
                <span>{cidrCheck.message}</span>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor={`${id}-desc`}>Mô tả</label>
            <input
              id={`${id}-desc`}
              type="text"
              placeholder="ví dụ: VPN kỹ thuật, máy chủ DNS, gateway..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={resetAndClose}
            disabled={loading}
          >
            Hủy bỏ
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !projectId || !cidrCheck.valid}
          >
            <ShieldCheck size={16} />
            {loading ? "Đang lưu..." : "Thêm vào danh sách an toàn"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

