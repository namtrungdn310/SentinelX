import { useEffect } from "react";
import { CheckCircle2, X } from "lucide-react";
import { severityLabel } from "../presentation";

export interface SecurityToastPayload {
  id: string;
  type: "incident" | "defense" | "recovery" | "settings";
  title: string;
  message: string;
  attackerIp?: string | null;
  severity?: string;
  targetView?: "incidents" | "defense" | "settings";
}

interface Props {
  toasts: SecurityToastPayload[];
  onClose: (id: string) => void;
  onNavigate: (view: string) => void;
}

function SecurityToastItem({
  toast,
  onClose,
  onNavigate,
}: {
  toast: SecurityToastPayload;
  onClose: (id: string) => void;
  onNavigate: (view: string) => void;
}) {
  useEffect(() => {
    const duration = toast.type === "settings" || toast.type === "recovery" ? 4500 : 8000;
    const timer = window.setTimeout(() => {
      onClose(toast.id);
    }, duration);
    return () => window.clearTimeout(timer);
  }, [toast.id, toast.type, onClose]);

  const isDefense = toast.type === "defense";
  const isSettings = toast.type === "settings";
  const isRecovery = toast.type === "recovery";
  const variantClass = isSettings
    ? "toast-settings"
    : isRecovery
      ? "toast-recovery"
      : isDefense
        ? "toast-defense"
        : "toast-incident";

  return (
    <div
      className={`security-toast ${variantClass}`}
      role={isSettings || isRecovery ? "status" : "alert"}
      aria-live={isSettings || isRecovery ? "polite" : "assertive"}
    >
      <div className="toast-content">
        <div className="toast-header">
          <div className="toast-title-row">
            {(isSettings || isRecovery) && (
              <CheckCircle2 size={15} className="toast-icon-ok" aria-hidden="true" />
            )}
            <strong>{toast.title}</strong>
          </div>
          {!isDefense && !isSettings && !isRecovery && toast.severity && (
            <span className="toast-severity-badge font-mono">
              {severityLabel(toast.severity)}
            </span>
          )}
        </div>
        <p className="toast-message">{toast.message}</p>
        {toast.attackerIp && (
          <div className="toast-meta">
            <span>IP mục tiêu:</span>
            <code className="font-mono ip-pill-toast">{toast.attackerIp}</code>
          </div>
        )}
        {toast.targetView && (
          <div className="toast-actions">
            <button
              type="button"
              className="toast-link-btn"
              onClick={() => {
                onNavigate(toast.targetView!);
                onClose(toast.id);
              }}
            >
              <span>
                {isDefense
                  ? "Xem bảng tường lửa"
                  : isSettings
                    ? "Mở thiết lập cấu hình"
                    : "Xem chi tiết sự cố"}
              </span>
              <span aria-hidden="true" className="toast-link-arrow">&rarr;</span>
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        className="toast-close-btn"
        aria-label="Đóng thông báo"
        onClick={() => onClose(toast.id)}
      >
        <X size={15} />
      </button>
    </div>
  );
}

export function SecurityToast({ toasts, onClose, onNavigate }: Props) {
  if (!toasts.length) return null;

  return (
    <div className="security-toast-stack">
      {toasts.map((toast) => (
        <SecurityToastItem
          key={toast.id}
          toast={toast}
          onClose={onClose}
          onNavigate={onNavigate}
        />
      ))}
    </div>
  );
}

