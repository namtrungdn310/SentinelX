import { useId, useState, useEffect } from "react";
import { CheckCircle2, Clock, Globe, ShieldAlert, X } from "lucide-react";
import type { Incident, IncidentDetail } from "../types";
import { fetchIncidentDetail, updateIncident } from "../api";
import { MOCK_INCIDENT_DETAILS } from "../mockData";
import { Modal } from "./Modal";

interface Props {
  incident: Incident | null;
  isOpen: boolean;
  onClose: () => void;
  onIncidentUpdated?: (updated: Incident) => void;
  isDemoMode: boolean;
}

export function IncidentDetailModal({
  incident,
  isOpen,
  onClose,
  onIncidentUpdated,
  isDemoMode,
}: Props) {
  const id = useId();
  const [detail, setDetail] = useState<IncidentDetail | null>(() => {
    if (isDemoMode && incident) {
      return MOCK_INCIDENT_DETAILS[incident.id] || { ...incident, events: [] };
    }
    return null;
  });
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isDemoMode || !incident) return;
    let isMounted = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      void fetchIncidentDetail(incident.id)
        .then((data) => {
          if (isMounted) setDetail(data);
        })
        .catch((err: unknown) => {
          if (isMounted) setError(err instanceof Error ? err.message : "Lỗi tải chi tiết sự cố");
        })
        .finally(() => {
          if (isMounted) setLoading(false);
        });
    }, 0);

    return () => {
      isMounted = false;
      window.clearTimeout(timer);
    };
  }, [incident, isDemoMode]);

  if (!isOpen || !incident) return null;

  const handleResolve = async () => {
    if (!detail) return;
    try {
      setResolving(true);
      if (isDemoMode) {
        const updated: Incident = {
          ...incident,
          status: "RESOLVED",
          resolved_at: new Date().toISOString(),
        };
        setDetail((prev) => (prev ? { ...prev, ...updated } : null));
        onIncidentUpdated?.(updated);
        return;
      }
      const updated = await updateIncident(incident.id, {
        status: "RESOLVED",
        summary: detail.summary ? `${detail.summary} (Đã xử lý thủ công qua Dashboard)` : "Đã xử lý qua Dashboard",
      });
      setDetail((prev) => (prev ? { ...prev, ...updated } : null));
      onIncidentUpdated?.(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi giải quyết sự cố");
    } finally {
      setResolving(false);
    }
  };

  const statusTone =
    incident.status === "RESOLVED"
      ? "ok"
      : incident.status === "MITIGATING"
        ? "warn"
        : "crit";

  const statusLabel =
    incident.status === "RESOLVED"
      ? "Đã giải quyết"
      : incident.status === "MITIGATING"
        ? "Đang phòng thủ"
        : incident.status === "DETECTED"
          ? "Đang diễn ra"
          : incident.status;

  const severityTone =
    incident.severity === "CRITICAL"
      ? "crit"
      : incident.severity === "HIGH"
        ? "warn"
        : "ok";

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="incident-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <ShieldAlert size={15} /> Sự cố an ninh
          </span>
          <h2 id={`${id}-title`}>{incident.title}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng chi tiết sự cố"
          onClick={onClose}
          disabled={resolving}
        >
          <X size={18} />
        </button>
      </div>

      <div className="modal-body">
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <div className="incident-meta-grid">
          <div className="meta-card">
            <span className="meta-label">Mã định danh (ID)</span>
            <span className="meta-value font-mono">{incident.id.slice(0, 8)}...</span>
          </div>
          <div className="meta-card">
            <span className="meta-label">Mức độ nghiêm trọng</span>
            <span className={`status-badge ${severityTone}`}>
              <i />
              {incident.severity}
            </span>
          </div>
          <div className="meta-card">
            <span className="meta-label">Trạng thái vòng đời</span>
            <span className={`status-badge ${statusTone}`}>
              <i />
              {statusLabel}
            </span>
          </div>
          <div className="meta-card">
            <span className="meta-label">Bắt đầu ghi nhận</span>
            <span className="meta-value font-mono">
              <Clock size={13} style={{ display: "inline", marginRight: 4 }} />
              {new Date(incident.started_at).toLocaleTimeString("vi-VN")} · {new Date(incident.started_at).toLocaleDateString("vi-VN")}
            </span>
          </div>
        </div>

        {incident.summary && (
          <div className="incident-summary-panel">
            <strong>Tóm tắt diễn biến:</strong>
            <p>{incident.summary}</p>
          </div>
        )}

        <div className="incident-events-section">
          <div className="section-header">
            <h3>Chuỗi sự kiện bất thường ({detail?.events?.length ?? incident.event_count})</h3>
            {loading && <span className="loading-indicator">Đang tải...</span>}
          </div>

          <div className="incident-events-list">
            {detail?.events && detail.events.length > 0 ? (
              detail.events.map((ev) => (
                <div key={ev.id} className="incident-event-item">
                  <div className="event-item-top">
                    <span className="event-detector-tag">{ev.detector_name}</span>
                    <span className="event-time font-mono">
                      {new Date(ev.detected_at).toLocaleTimeString("vi-VN")}
                    </span>
                  </div>
                  <div className="event-item-body">
                    {ev.attacker_ip && (
                      <div className="event-ip">
                        <Globe size={13} />
                        Kẻ tấn công: <strong className="font-mono">{ev.attacker_ip}</strong>
                      </div>
                    )}
                    <div className="event-details-text font-mono">
                      {JSON.stringify(ev.details, null, 2)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-subtext">
                {loading ? "Đang lấy danh sách sự kiện..." : "Không có sự kiện chi tiết nào."}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="modal-footer">
        {incident.status !== "RESOLVED" && (
          <button
            className="btn btn-primary"
            onClick={handleResolve}
            disabled={resolving || loading}
          >
            <CheckCircle2 size={16} />
            {resolving ? "Đang cập nhật..." : "Đánh dấu Đã giải quyết"}
          </button>
        )}
        <button className="btn btn-outline" onClick={onClose} disabled={resolving}>
          Đóng
        </button>
      </div>
    </Modal>
  );
}
