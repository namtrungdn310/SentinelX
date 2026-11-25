import type { LBAlgorithmType, ProjectLBConfig } from "../types";

export function ProjectLBTechnicalFields({
  idPrefix,
  value,
  onChange,
  currentAlgorithm,
  disabled = false,
}: {
  idPrefix: string;
  value: ProjectLBConfig;
  onChange: (next: ProjectLBConfig) => void;
  currentAlgorithm?: LBAlgorithmType;
  disabled?: boolean;
}) {
  return (
    <div className="lb-advanced-panel">
      <div className="form-group">
        <label id={`${idPrefix}-lb-algo-label`}>Thuật toán chia tải</label>
        <div
          className="lb-algo-segmented lb-algo-segmented-full"
          role="group"
          aria-labelledby={`${idPrefix}-lb-algo-label`}
        >
          <button
            type="button"
            className={value.algorithm === "round_robin" ? "active" : ""}
            aria-pressed={value.algorithm === "round_robin"}
            onClick={() => onChange({ ...value, algorithm: "round_robin" })}
            disabled={disabled}
          >
            {currentAlgorithm === "round_robin"
              ? "Round Robin (hiện tại)"
              : "Round Robin"}
          </button>
          <button
            type="button"
            className={value.algorithm === "least_in_flight" ? "active" : ""}
            aria-pressed={value.algorithm === "least_in_flight"}
            onClick={() => onChange({ ...value, algorithm: "least_in_flight" })}
            disabled={disabled}
          >
            {currentAlgorithm === "least_in_flight"
              ? "Least In-Flight (hiện tại)"
              : "Least In-Flight"}
          </button>
        </div>
      </div>

      <div className="lb-fields-grid">
        <div className="form-group">
          <label htmlFor={`${idPrefix}-lb-url`}>Endpoint LB</label>
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
          <label htmlFor={`${idPrefix}-lb-health-path`}>Health Check</label>
          <input
            id={`${idPrefix}-lb-health-path`}
            type="text"
            className="form-input font-mono"
            value={value.health_path}
            onChange={(e) =>
              onChange({ ...value, health_path: e.target.value })
            }
            onBlur={(e) => {
              const cleaned = e.target.value.trim();
              if (!cleaned) {
                onChange({ ...value, health_path: "/health" });
              } else if (!cleaned.startsWith("/")) {
                onChange({ ...value, health_path: `/${cleaned}` });
              }
            }}
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
          <label htmlFor={`${idPrefix}-lb-fail`}>Ngưỡng eject</label>
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
          <label htmlFor={`${idPrefix}-lb-succ`}>Ngưỡng hồi phục</label>
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
