import { ArrowLeftRight, Settings2 } from "lucide-react";
import type { Project } from "../types";

interface Props {
  projects: Project[];
  onSelectProject: (projectId: string) => void;
  onOpenCreateModal: () => void;
  onEditProject?: (project: Project) => void;
}

export function ProjectsView({
  projects,
  onSelectProject,
  onOpenCreateModal,
  onEditProject,
}: Props) {
  return (
    <div className="projects-view">
      <div className="page-heading">
        <h1 className="sr-only">Dự án hạ tầng</h1>
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginLeft: "auto" }}
          onClick={onOpenCreateModal}
        >
          + Tạo dự án mới
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="panel-empty">
          <p>Không tìm thấy dự án nào phù hợp.</p>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map((project) => {
            const lbEnabled = Boolean(project.load_balancer?.enabled);
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
                  <div className="project-card-top">
                    <h3 className="project-card-title">{project.name}</h3>
                    <div className="project-card-actions">
                      <span className="project-card-date">
                        {new Date(project.created_at).toLocaleDateString("vi-VN")}
                      </span>
                      {onEditProject && (
                        <button
                          type="button"
                          className="icon-button project-edit-btn"
                          aria-label={`Cấu hình dự án ${project.name}`}
                          title="Chỉnh sửa dự án & Load Balancer"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditProject(project);
                          }}
                        >
                          <Settings2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="project-card-desc">
                    {project.description || "Chưa có mô tả cho dự án này."}
                  </p>
                </div>

                <div className="project-card-meta">
                  <span className="font-mono project-card-id" title={project.id}>
                    {project.id}
                  </span>
                  {lbEnabled && (
                    <span className="project-lb-pill">
                      <ArrowLeftRight size={12} />
                      LB ·{" "}
                      {project.load_balancer?.algorithm === "least_in_flight"
                        ? "Least In-Flight"
                        : "Round Robin"}
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
