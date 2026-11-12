import { useEffect } from "react";
import { ArrowRight, Flame, ShieldAlert, X } from "lucide-react";

export interface SecurityToastPayload {
  id: string;
  type: "incident" | "defense" | "recovery";
  title: string;
  message: string;
  attackerIp?: string | null;
  severity?: string;
  targetView: "incidents" | "defense";
}

interface Props {
  toast: SecurityToastPayload | null;
  onClose: () => void;
  onNavigate: (view: string) => void;
}

export function SecurityToast({ toast, onClose, onNavigate }: Props) {
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => {
      onClose();
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const isDefense = toast.type === "defense";

  return (
    <div
      className={`security-toast ${isDefense ? "toast-defense" : "toast-incident"}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="toast-icon-wrap">
        {isDefense ? (
          <Flame size={20} className="toast-icon pulse-flame" />
        ) : (
          <ShieldAlert size={20} className="toast-icon pulse-alert" />
        )}
      </div>

      <div className="toast-content">
        <div className="toast-header">
          <strong>{toast.title}</strong>
          {toast.severity && (
            <span className="toast-severity-badge font-mono">{toast.severity}</span>
          )}
        </div>
        <p className="toast-message">{toast.message}</p>
        {toast.attackerIp && (
          <div className="toast-meta">
            <span>Mục tiêu IP:</span>
            <code className="font-mono ip-pill-toast">{toast.attackerIp}</code>
          </div>
        )}
        <div className="toast-actions">
          <button
            type="button"
            className="toast-link-btn"
            onClick={() => {
              onNavigate(toast.targetView);
              onClose();
            }}
          >
            <span>{isDefense ? "Xem bảng tường lửa" : "Xem chi tiết sự cố"}</span>
            <ArrowRight size={13} />
          </button>
        </div>
      </div>

      <button
        type="button"
        className="toast-close-btn"
        aria-label="Đóng thông báo cảnh báo"
        onClick={onClose}
      >
        <X size={15} />
      </button>
    </div>
  );
}

