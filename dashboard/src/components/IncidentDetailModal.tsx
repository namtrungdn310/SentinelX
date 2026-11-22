import { useId, useState, useEffect } from "react";
import {
  Activity,
  Check,
  CheckCircle2,
  Copy,
  Cpu,
  Globe,
  HardDrive,
  ShieldAlert,
  X,
} from "lucide-react";
import type { DefensePolicy, Incident, IncidentDetail, Node } from "../types";
import { fetchIncidentDetail, updateIncident } from "../api";
import { MOCK_INCIDENT_DETAILS, MOCK_POLICIES } from "../mockData";
import {
  classifyIncidentHandling,
  formatBytes,
  formatPortRanges,
  severityLabel,
} from "../presentation";
import { Modal } from "./Modal";

interface Props {
  incident: Incident | null;
  isOpen: boolean;
  onClose: () => void;
  onIncidentUpdated?: (updated: Incident) => void;
  isDemoMode: boolean;
  nodes?: Node[];
  policies?: DefensePolicy[];
}

export function IncidentDetailModal({
  incident,
  isOpen,
  onClose,
  onIncidentUpdated,
  isDemoMode,
  nodes,
  policies,
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
  const [copiedId, setCopiedId] = useState(false);
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
        summary: detail.summary ? `${detail.summary} · Thủ công: Đã giải quyết` : "Thủ công: Đã giải quyết",
      });
      setDetail((prev) => (prev ? { ...prev, ...updated } : null));
      onIncidentUpdated?.(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi giải quyết sự cố");
    } finally {
      setResolving(false);
    }
  };

  const firstEvent = detail?.events?.[0];
  const handling = classifyIncidentHandling(
    incident,
    policies ?? (isDemoMode ? MOCK_POLICIES : []),
    firstEvent?.detector_name,
  );

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
        ? "Đang ngăn chặn"
        : incident.status === "DETECTED"
          ? handling.mode === "auto"
            ? "Đang chờ Agent tải lệnh"
            : "Đang diễn ra"
          : incident.status;

  const severityTone =
    incident.severity === "CRITICAL"
      ? "crit"
      : incident.severity === "HIGH"
        ? "warn"
        : "medium";
  const incidentNode = nodes?.find(
    (n) => n.id === (incident.node_id || firstEvent?.node_id)
  );
  const targetedPorts =
    incident.targeted_ports ||
    (Array.isArray(firstEvent?.details?.targeted_ports)
      ? (firstEvent.details.targeted_ports as number[])
      : undefined);
  const attackerIp = incident.attacker_ip || firstEvent?.attacker_ip || null;
  const statusSubtext =
    incident.status === "MITIGATING"
      ? attackerIp
        ? `Kích hoạt lệnh chặn IP ${attackerIp}`
        : "Kích hoạt lệnh bảo vệ"
      : incident.status === "RESOLVED"
        ? handling.mode === "auto"
          ? "Xử lý tự động · Đã hoàn tất"
          : "Xử lý thủ công · Đã đóng"
        : null;

  return (
    <Modal onClose={onClose} labelledBy={`${id}-title`} className="incident-modal">
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            <ShieldAlert size={15} /> Sự cố an ninh
            {incidentNode && (
              <span style={{ marginLeft: 6, fontWeight: 500 }}>
                · Máy chủ <strong>{incidentNode.hostname}</strong> ({incidentNode.ip_address})
              </span>
            )}
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
          <div className="meta-card meta-card-id">
            <div className="id-card-header">
              <span className="meta-label">Mã sự cố</span>
              <span className="id-card-time font-mono">
                {new Date(incident.started_at).toLocaleTimeString("vi-VN")} · {new Date(incident.started_at).toLocaleDateString("vi-VN")}
              </span>
            </div>
            <div className="id-row">
              <span className="meta-value font-mono">{incident.id}</span>
              <button
                type="button"
                className="btn-copy-id"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(incident.id);
                    setCopiedId(true);
                    setTimeout(() => setCopiedId(false), 1800);
                  } catch {
                    // clipboard fallback
                  }
                }}
                title="Sao chép mã sự cố"
              >
                {copiedId ? <Check size={12} /> : <Copy size={12} />}
                <span>{copiedId ? "Đã sao chép" : "Sao chép"}</span>
              </button>
            </div>
          </div>
          <div className="meta-card">
            <span className="meta-label">Mức độ</span>
            <span className={`severity-badge ${severityTone}`} style={{ width: "fit-content" }}>
              {severityLabel(incident.severity)}
            </span>
          </div>
          <div className="meta-card">
            <span className="meta-label">Trạng thái</span>
            <span className={`status-badge ${statusTone}`}>
              <i />
              {statusLabel}
            </span>
            {statusSubtext && (
              <small className="text-muted" style={{ fontSize: 11.5, lineHeight: 1.35 }}>
                {statusSubtext}
              </small>
            )}
          </div>
          <div className="meta-card">
            <span className="meta-label">Cổng sự cố</span>
            <span className="meta-value font-mono" style={{ wordBreak: "break-all" }}>
              {formatPortRanges(targetedPorts)}
            </span>
          </div>
        </div>

        {incident.summary && (
          <div className="incident-summary-panel">
            <strong>Tóm tắt:</strong>
            <p>{incident.summary}</p>
          </div>
        )}

        <div className="incident-events-section">
          <div className="section-header">
            <h3>Sự kiện ({detail?.events?.length ?? incident.event_count})</h3>
            {loading && <span className="loading-indicator">Đang tải...</span>}
          </div>

          <div className="incident-events-list">
            {detail?.events && detail.events.length > 0 ? (
              detail.events.map((ev) => {
                const hasResourceInfo = Boolean(
                  ev.details?.process_name ||
                  ev.details?.pid ||
                  ev.details?.current_value !== undefined ||
                  ev.details?.cpu_percent !== undefined
                );

                return (
                  <div key={ev.id} className="incident-event-item">
                    <div className="event-item-top">
                      <div className="event-top-left">
                        <span className="event-detector-tag">{ev.detector_name}</span>
                      </div>
                      <span className="event-time font-mono">
                        {new Date(ev.detected_at).toLocaleTimeString("vi-VN")}
                      </span>
                    </div>

                    <div className="event-item-body">
                      {ev.attacker_ip && (
                        <div className="event-highlight-row">
                          <div className="event-ip">
                            <Globe size={14} />
                            <span>IP nguồn: <strong className="font-mono">{ev.attacker_ip}</strong></span>
                          </div>

                          <div className="event-metrics-right">
                            {(ev.detector_name === "syn_flood_detector" ||
                              ev.details?.attack_type === "SYN_FLOOD" ||
                              ev.details?.syn_count !== undefined) ? (
                              (ev.details?.metric_ratio !== undefined || ev.details?.syn_count !== undefined) && (
                                <div className="event-metric-tag">
                                  <span>
                                    Tỷ lệ SYN/ACK:{" "}
                                    <strong className="font-mono">
                                      {ev.details?.metric_ratio !== undefined
                                        ? String(ev.details.metric_ratio)
                                        : (
                                            Number(ev.details?.syn_count || 0) /
                                            Math.max(Number(ev.details?.ack_count || 1), 1)
                                          ).toFixed(1)}
                                    </strong>
                                  </span>
                                </div>
                              )
                            ) : (ev.detector_name === "port_scan_detector" ||
                              ev.details?.attack_type === "PORT_SCAN" ||
                              incident.title.toLowerCase().includes("quét cổng")) ? (
                              (ev.details?.scanned_port_count !== undefined ||
                                Array.isArray(ev.details?.targeted_ports) ||
                                Array.isArray(ev.details?.destination_ports)) && (
                                <div className="event-metric-tag">
                                  <span>
                                    Số cổng quét:{" "}
                                    <strong className="font-mono">
                                      {String(
                                        ev.details?.scanned_port_count ??
                                          (Array.isArray(ev.details?.targeted_ports)
                                            ? ev.details.targeted_ports.length
                                            : Array.isArray(ev.details?.destination_ports)
                                              ? ev.details.destination_ports.length
                                              : 0)
                                      )}{" "}
                                      cổng
                                    </strong>
                                  </span>
                                </div>
                              )
                            ) : (
                              <>
                                {ev.details?.packet_rate_pps !== undefined && (
                                  <div className="event-metric-tag">
                                    <span>Tốc độ: <strong className="font-mono">{String(ev.details.packet_rate_pps)} pps</strong></span>
                                  </div>
                                )}
                                {(ev.details?.byte_rate_mbps !== undefined || ev.details?.bytes_per_second !== undefined) && (
                                  <div className="event-metric-tag">
                                    <span>Băng thông: <strong className="font-mono">{ev.details.byte_rate_mbps !== undefined ? `${ev.details.byte_rate_mbps} MB/s` : `${formatBytes(Number(ev.details.bytes_per_second))}/s`}</strong></span>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      )}

                      {hasResourceInfo && (
                        <div className="event-highlight-row resource-highlight">
                          {ev.details?.process_name ? (
                            <div className="event-proc">
                              <Cpu size={14} />
                              <strong className="font-mono">{String(ev.details.process_name)}</strong>

                              {(ev.details.pid || Number(ev.details.process_count || 1) > 1) && (
                                <span className="text-muted font-mono">
                                  {`(${ev.details.pid ? `PID: ${String(ev.details.pid)}` : ""}${
                                    ev.details.pid && Number(ev.details.process_count || 1) > 1 ? ", " : ""
                                  }${
                                    Number(ev.details.process_count || 1) > 1
                                      ? `${String(ev.details.process_count)} workers`
                                      : ""
                                  })`}
                                </span>
                              )}

                              {(ev.details?.process_percent !== undefined || ev.details?.process_cpu_percent !== undefined) ? (
                                <span className="process-share-tag">
                                  ·{" "}
                                  <strong className="font-mono">
                                    {String(ev.details.process_percent ?? ev.details.process_cpu_percent)}%
                                    {ev.details?.current_value !== undefined || ev.details?.cpu_percent !== undefined
                                      ? ` / ${String(ev.details.current_value ?? ev.details.cpu_percent)}%`
                                      : ""}{" "}
                                    {String(ev.details?.metric_name || "").includes("memory") ? "RAM" : "CPU"}
                                  </strong>
                                </span>
                              ) : (
                                (ev.details?.current_value !== undefined || ev.details?.cpu_percent !== undefined) && (
                                  <span className="process-share-tag">
                                    ·{" "}
                                    <strong className="font-mono">
                                      {String(ev.details.current_value ?? ev.details.cpu_percent)}%{" "}
                                      {String(ev.details?.metric_name || "").includes("memory") ? "RAM" : "CPU"}
                                    </strong>
                                  </span>
                                )
                              )}
                            </div>
                          ) : (
                            <div className="event-proc">
                              {String(ev.details?.metric_name || "").includes("disk") ? (
                                <HardDrive size={14} />
                              ) : (
                                <Activity size={14} />
                              )}
                              <span>
                                Mức đo {String(ev.details?.metric_name || "").includes("memory") ? "RAM" : String(ev.details?.metric_name || "").includes("disk") ? "Đĩa" : "CPU"}:{" "}
                                <strong className="font-mono">{String(ev.details?.current_value ?? ev.details?.cpu_percent)}%</strong>
                                {Boolean(ev.details?.mount_point) && (
                                  <span className="text-muted font-mono" style={{ marginLeft: 6 }}>
                                    (phân vùng {String(ev.details?.mount_point)})
                                  </span>
                                )}
                              </span>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="event-details-text font-mono">
                        {JSON.stringify(ev.details, null, 2)}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="empty-subtext">
                {loading ? "Đang lấy danh sách sự kiện..." : "Không có sự kiện chi tiết nào."}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="modal-actions">
        <button
          type="button"
          className="btn btn-outline"
          onClick={onClose}
          disabled={resolving}
        >
          Đóng
        </button>
        {incident.status !== "RESOLVED" && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleResolve}
            disabled={resolving || loading}
          >
            <CheckCircle2 size={16} />
            {resolving ? "Đang cập nhật..." : "Đánh dấu đã giải quyết"}
          </button>
        )}
      </div>
    </Modal>
  );
}
