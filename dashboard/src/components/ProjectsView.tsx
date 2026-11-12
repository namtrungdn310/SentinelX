import type { Project, Node } from "../types";
import { nodeHealth, validMetric } from "../presentation";

interface Props {
  projects: Project[];
  nodes: Node[];
  onSelectProject: (projectId: string | null) => void;
  onOpenCreateModal: () => void;
}

export function ProjectsView({
  projects,
  nodes,
  onSelectProject,
  onOpenCreateModal,
}: Props) {
  const totalNodesCount = nodes.length;
  const onlineTotalCount = nodes.filter(
    (n) => n.status === "online" || n.status === "degraded",
  ).length;

  return (
    <div className="projects-view">
      <div className="page-heading">
        <div>
          <h1>Dự án hạ tầng</h1>
          <div className="page-heading-context">
            <p>
              Chọn một dự án để vào không gian giám sát, phát hiện sự cố và cấu hình tường lửa chuyên biệt.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onOpenCreateModal}
        >
          Tạo dự án mới
        </button>
      </div>

      <div className="projects-grid">
        {projects.map((project) => {
          const projectNodes = nodes.filter((n) => n.project_id === project.id);
          const onlineCount = projectNodes.filter(
            (n) => n.status === "online" || n.status === "degraded",
          ).length;

          const cpuNodes = projectNodes.filter((n) => validMetric(n.latestCpu));
          const memNodes = projectNodes.filter((n) => validMetric(n.latestMemory));
          const avgCpu = cpuNodes.length
            ? Math.round(
                cpuNodes.reduce((sum, n) => sum + n.latestCpu!, 0) /
                  cpuNodes.length,
              )
            : null;
          const avgMem = memNodes.length
            ? Math.round(
                memNodes.reduce((sum, n) => sum + n.latestMemory!, 0) /
                  memNodes.length,
              )
            : null;

          const hasOffline = projectNodes.some((n) => n.status === "offline");
          const hasWarn = projectNodes.some((n) => nodeHealth(n) === "warn");
          const statusTone = hasOffline
            ? "crit"
            : hasWarn
              ? "warn"
              : projectNodes.length > 0
                ? "ok"
                : "unenrolled";

          const statusText = hasOffline
            ? "Có máy chủ ngoại tuyến"
            : hasWarn
              ? "Cảnh báo tải cao"
              : projectNodes.length > 0
                ? "Hoạt động ổn định"
                : "Chưa có máy chủ";

          return (
            <article
              key={project.id}
              className="project-card"
              onClick={() => onSelectProject(project.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectProject(project.id);
                }
              }}
            >
              <div className="project-card-header">
                <div>
                  <h3 className="project-card-title">{project.name}</h3>
                  <p className="project-card-desc">
                    {project.description || "Chưa có mô tả cho dự án này."}
                  </p>
                </div>
                <span className={`status-badge ${statusTone}`}>
                  <i />
                  <span>{statusText}</span>
                </span>
              </div>

              <div className="project-card-metrics">
                <div className="project-metric-item">
                  <span className="project-metric-label">Máy chủ</span>
                  <strong className="project-metric-value font-mono">
                    {onlineCount} / {projectNodes.length}
                  </strong>
                </div>
                <div className="project-metric-item">
                  <span className="project-metric-label">CPU trung bình</span>
                  <strong className="project-metric-value font-mono">
                    {avgCpu !== null ? `${avgCpu}%` : "—"}
                  </strong>
                </div>
                <div className="project-metric-item">
                  <span className="project-metric-label">RAM trung bình</span>
                  <strong className="project-metric-value font-mono">
                    {avgMem !== null ? `${avgMem}%` : "—"}
                  </strong>
                </div>
              </div>

              <div className="project-card-footer">
                <span className="project-card-hint">
                  {projectNodes.length} máy chủ thuộc phạm vi
                </span>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectProject(project.id);
                  }}
                >
                  Vào quản trị
                </button>
              </div>
            </article>
          );
        })}

        {/* Thẻ xem toàn bộ hạ tầng (Toàn cụm) dành cho Super Admin */}
        <article
          className="project-card project-card-all"
          onClick={() => onSelectProject(null)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onSelectProject(null);
            }
          }}
        >
          <div className="project-card-header">
            <div>
              <h3 className="project-card-title">Toàn bộ hạ tầng (Tất cả dự án)</h3>
              <p className="project-card-desc">
                Chế độ xem gộp toàn bộ {projects.length} dự án dành cho quản trị viên cấp cao.
              </p>
            </div>
            <span className="status-badge ok">
              <i />
              <span>Toàn cụm</span>
            </span>
          </div>

          <div className="project-card-metrics">
            <div className="project-metric-item">
              <span className="project-metric-label">Tổng dự án</span>
              <strong className="project-metric-value font-mono">
                {projects.length}
              </strong>
            </div>
            <div className="project-metric-item">
              <span className="project-metric-label">Tổng máy chủ</span>
              <strong className="project-metric-value font-mono">
                {onlineTotalCount} / {totalNodesCount}
              </strong>
            </div>
            <div className="project-metric-item">
              <span className="project-metric-label">Phạm vi</span>
              <strong className="project-metric-value">Toàn bộ</strong>
            </div>
          </div>

          <div className="project-card-footer">
            <span className="project-card-hint">Xem báo cáo tổng hợp</span>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={(e) => {
                e.stopPropagation();
                onSelectProject(null);
              }}
            >
              Xem toàn cụm
            </button>
          </div>
        </article>
      </div>
    </div>
  );
}
