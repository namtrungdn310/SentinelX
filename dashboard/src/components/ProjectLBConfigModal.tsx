import { useId, useState } from "react";
import { ArrowLeftRight, Settings2, X } from "lucide-react";
import { defaultProjectLBConfig } from "../api";
import type { Project, ProjectLBConfig } from "../types";
import { Modal } from "./Modal";
import { ProjectLBTechnicalFields } from "./ProjectLBFields";

interface Props {
  isOpen: boolean;
  project: Project | null;
  mode?: "lb" | "project";
  onClose: () => void;
  onSave: (
    projectId: string,
    payload: {
      name?: string;
      description?: string | null;
      load_balancer?: ProjectLBConfig;
    },
  ) => Promise<void>;
}

export function ProjectLBConfigModal({
  isOpen,
  project,
  mode = "lb",
  onClose,
  onSave,
}: Props) {
  const id = useId();
  const [name, setName] = useState(project?.name ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [lbConfig, setLbConfig] = useState<ProjectLBConfig>(
    () => project?.load_balancer ?? defaultProjectLBConfig(),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !project) return null;

  const isProjectMode = mode === "project";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isProjectMode && !name.trim()) return;
    setSaving(true);
    setError(null);
    const trimmedUrl = (lbConfig.lb_url ?? "").trim();
    const rawHealthPath = lbConfig.health_path.trim();
    const normalizedHealthPath = !rawHealthPath
      ? "/health"
      : rawHealthPath.startsWith("/")
        ? rawHealthPath
        : `/${rawHealthPath}`;
    try {
      if (isProjectMode) {
        await onSave(project.id, {
          name: name.trim(),
          description: description.trim() ? description.trim() : null,
        });
      } else {
        await onSave(project.id, {
          load_balancer: {
            ...lbConfig,
            lb_url: trimmedUrl ? trimmedUrl : null,
            health_path: normalizedHealthPath,
          },
        });
      }
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không lưu được cấu hình",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      onClose={() => {
        if (!saving) onClose();
      }}
      labelledBy={`${id}-title`}
      className="add-project-modal"
    >
      <div className="modal-header">
        <div>
          <span className="modal-eyebrow">
            {isProjectMode ? (
              <>
                <Settings2 size={15} /> Thông tin dự án
              </>
            ) : (
              <>
                <ArrowLeftRight size={15} /> Cấu hình kỹ thuật Load Balancer
              </>
            )}
          </span>
          <h2 id={`${id}-title`}>{project.name}</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Đóng cấu hình"
          onClick={onClose}
          disabled={saving}
        >
          <X size={16} />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="project-form">
        <div className="modal-body">
          {error && (
            <div className="feedback-banner feedback-error" role="alert">
              <span>{error}</span>
            </div>
          )}

          {isProjectMode ? (
            <>
              <div className="form-group">
                <label htmlFor={`${id}-edit-name`}>Tên dự án *</label>
                <input
                  id={`${id}-edit-name`}
                  type="text"
                  className="form-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={saving}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor={`${id}-edit-desc`}>Mô tả</label>
                <textarea
                  id={`${id}-edit-desc`}
                  className="form-input"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={saving}
                />
              </div>
            </>
          ) : (
            <ProjectLBTechnicalFields
              idPrefix={id}
              value={lbConfig}
              onChange={setLbConfig}
              currentAlgorithm={project.load_balancer?.algorithm ?? "round_robin"}
              disabled={saving}
            />
          )}
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            disabled={saving}
          >
            Hủy bỏ
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving || (isProjectMode && !name.trim())}
          >
            {saving ? "Đang lưu…" : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
