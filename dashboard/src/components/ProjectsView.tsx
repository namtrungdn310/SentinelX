import type { Project } from "../types";

interface Props {
  projects: Project[];
  onSelectProject: (projectId: string) => void;
  onOpenCreateModal: () => void;
}

export function ProjectsView({
  projects,
  onSelectProject,
  onOpenCreateModal,
}: Props) {
  return (
    <div className="projects-view">
      <div className="page-heading">
        <div>
          <h1>Dự án hạ tầng</h1>
          <div className="page-heading-context">
            <p>
              Chọn dự án bạn muốn làm việc để vào không gian giám sát và quản trị riêng biệt.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onOpenCreateModal}
        >
          + Tạo dự án mới
        </button>
      </div>

      <div className="projects-grid">
        {projects.map((project) => (
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
              <h3 className="project-card-title">{project.name}</h3>
              <p className="project-card-desc">
                {project.description || "Chưa có mô tả cho dự án này."}
              </p>
            </div>

            <div className="project-card-meta">
              <span className="font-mono project-card-id">{project.id}</span>
              <span className="project-card-date">
                Tạo ngày {new Date(project.created_at).toLocaleDateString("vi-VN")}
              </span>
            </div>

            <div className="project-card-footer">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectProject(project.id);
                }}
              >
                Vào dự án
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
