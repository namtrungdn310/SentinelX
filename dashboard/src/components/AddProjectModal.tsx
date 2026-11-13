import { useState, useId } from "react";
import { X } from "lucide-react";
import { Modal } from "./Modal";
import type { Project } from "../types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onCreateProject: (name: string, description: string) => Promise<Project | void>;
}

export function AddProjectModal({
  isOpen,
  onClose,
  onCreateProject,
}: Props) {
  const id = useId();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await onCreateProject(name.trim(), description.trim());
      setName("");
      setDescription("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tạo dự án");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      onClose={() => {
        if (!loading) onClose();
      }}
      labelledBy={`${id}-title`}
      className="add-project-modal"
    >
      <div className="modal-header">
        <div>
          <h2 id={`${id}-title`}>Tạo dự án mới</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Đóng biểu mẫu tạo dự án"
          onClick={onClose}
          disabled={loading}
        >
          <X size={16} />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="project-form">
        {error && (
          <div className="feedback-banner feedback-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        <div className="form-group">
          <label htmlFor={`${id}-name`}>Tên dự án *</label>
          <input
            id={`${id}-name`}
            type="text"
            className="form-input"
            placeholder="VD: Payment Service, Staging Cluster..."
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading}
            data-autofocus
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor={`${id}-desc`}>Mô tả dự án</label>
          <textarea
            id={`${id}-desc`}
            className="form-input"
            rows={3}
            placeholder="Mô tả mục đích và phạm vi hạ tầng của dự án..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            disabled={loading}
          >
            Hủy bỏ
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !name.trim()}
          >
            {loading ? "Đang tạo..." : "Tạo dự án"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
