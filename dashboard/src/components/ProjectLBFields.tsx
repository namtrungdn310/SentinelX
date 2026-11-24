import type { ProjectLBConfig } from "../types";

export function ProjectLBTechnicalFields({
  idPrefix,
  value,
  onChange,
  disabled = false,
}: {
  idPrefix: string;
  value: ProjectLBConfig;
  onChange: (next: ProjectLBConfig) => void;
  disabled?: boolean;
}) {
  return (
    <div className="lb-advanced-panel">
      <div className="lb-fields-grid">
        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-url`}>
            Endpoint LB riêng (Tùy chọn)
          </label>
          <input
            id={`${idPrefix}-lb-url`}
            type="url"
            className="form-input font-mono"
            placeholder="Mặc định theo hệ thống"
            value={value.lb_url ?? ""}
            onChange={(e) => onChange({ ...value, lb_url: e.target.value })}
            disabled={disabled}
          />
        </div>

        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-health-path`}>
            Đường dẫn Health Check
          </label>
          <input
            id={`${idPrefix}-lb-health-path`}
            type="text"
            className="form-input font-mono"
            value={value.health_path}
            onChange={(e) =>
              onChange({ ...value, health_path: e.target.value || "/health" })
            }
            placeholder="/health"
            disabled={disabled}
          />
        </div>
      </div>

      <div className="lb-fields-grid lb-fields-grid-3">
        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-interval`}>
            Chu kỳ probe (giây)
          </label>
          <input
            id={`${idPrefix}-lb-interval`}
            type="number"
            className="form-input font-mono"
            min={0.5}
            max={300}
            step={0.5}
            value={value.health_interval_seconds}
            onChange={(e) =>
              onChange({
                ...value,
                health_interval_seconds: Math.max(
                  0.5,
                  Number(e.target.value) || 3,
                ),
              })
            }
            disabled={disabled}
          />
        </div>

        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-fail`}>Ngưỡng eject (lỗi)</label>
          <input
            id={`${idPrefix}-lb-fail`}
            type="number"
            className="form-input font-mono"
            min={1}
            max={20}
            value={value.failure_threshold}
            onChange={(e) =>
              onChange({
                ...value,
                failure_threshold: Math.max(1, Number(e.target.value) || 3),
              })
            }
            disabled={disabled}
          />
        </div>

        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-succ`}>Ngưỡng hồi phục (OK)</label>
          <input
            id={`${idPrefix}-lb-succ`}
            type="number"
            className="form-input font-mono"
            min={1}
            max={20}
            value={value.success_threshold}
            onChange={(e) =>
              onChange({
                ...value,
                success_threshold: Math.max(1, Number(e.target.value) || 2),
              })
            }
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  );
}
