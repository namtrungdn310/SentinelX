import { useState } from "react";
import {
  ArrowDownUp,
  ArrowDown,
  ArrowUp,
  ChevronRight,
  LayoutGrid,
  List,
  Server,
} from "lucide-react";
import type { Node } from "../types";
import { nodeHealthLabel, nodeHealth, formatPercent, validMetric } from "../presentation";
export interface HostTableState {
  view: "table" | "grid";
  sort: { key: "hostname" | "latestCpu" | "latestMemory"; ascending: boolean } | null;
}
interface Props {
  state?: HostTableState;
  onStateChange?: (state: HostTableState) => void;
  nodes: Node[];
  selectedNodeId: string | null;
  onSelectNode: (node: Node) => void;
  isLoading: boolean;
  onOpenDetail?: (node: Node) => void;
}
export function NodeMatrix({
  nodes,
  selectedNodeId,
  onSelectNode,
  isLoading,
  onOpenDetail,
  state,
  onStateChange,
}: Props) {
  const [localState, setLocalState] = useState<HostTableState>({ view: "table", sort: null });
  const { view, sort } = state ?? localState;
  const update = (next: HostTableState) => onStateChange ? onStateChange(next) : setLocalState(next);
  const setView = (view: HostTableState["view"]) => update({ view, sort });
  const sorted = sort
    ? [...nodes].sort((a, b) => {
        const left = a[sort.key];
        const right = b[sort.key];
        if (left === undefined) return right === undefined ? 0 : 1;
        if (right === undefined) return -1;
        const result =
          typeof left === "string" && typeof right === "string"
            ? left.localeCompare(right)
            : Number(left) - Number(right);
        return sort.ascending ? result : -result;
      })
    : nodes;
  const toggleSort = (key: "hostname" | "latestCpu" | "latestMemory") =>
    update({ view, sort: { key, ascending: sort?.key === key ? !sort.ascending : key === "hostname" } });
  const sortDirection = (key: string) =>
    sort?.key === key
      ? sort.ascending
        ? ("ascending" as const)
        : ("descending" as const)
      : ("none" as const);
  return (
    <section
      className="panel fleet-panel"
      id="host-fleet"
      aria-busy={isLoading}
    >
      <div className="panel-heading">
        <div>
          <h2>
            Máy chủ <span className="count-badge">{nodes.length}</span>
          </h2>

        </div>
        <div className="segmented">
          <button
            aria-label="Xem bảng máy chủ"
            aria-pressed={view === "table"}
            className={view === "table" ? "active" : ""}
            onClick={() => setView("table")}
          >
            <List size={16} />
          </button>
          <button
            aria-label="Xem lưới máy chủ"
            aria-pressed={view === "grid"}
            className={view === "grid" ? "active" : ""}
            onClick={() => setView("grid")}
          >
            <LayoutGrid size={16} />
          </button>
        </div>
      </div>
      {isLoading ? (
        <div className="panel-empty">Đang tải máy chủ…</div>
      ) : !nodes.length ? (
        <div className="panel-empty">
          <Server size={28} />
          <strong>Chưa tìm thấy máy chủ</strong>
          <p>Thử đổi từ khóa hoặc xóa bộ lọc hiện tại.</p>
        </div>
      ) : view === "table" ? (
        <div className="table-scroll">
          <table className="host-table">
            <thead>
              <tr>
                <th aria-sort={sortDirection("hostname")}>
                  <button
                    className="table-sort"
                    onClick={() => toggleSort("hostname")}
                  >
                    Hostname / IP {sort?.key === "hostname" ? (sort.ascending ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowDownUp size={13} />}
                  </button>
                </th>
                <th>Trạng thái</th>
                <th aria-sort={sortDirection("latestCpu")}>
                  <button
                    className="table-sort"
                    onClick={() => toggleSort("latestCpu")}
                  >
                    CPU {sort?.key === "latestCpu" ? (sort.ascending ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowDownUp size={13} />}
                  </button>
                </th>
                <th aria-sort={sortDirection("latestMemory")}>
                  <button
                    className="table-sort"
                    onClick={() => toggleSort("latestMemory")}
                  >
                    RAM {sort?.key === "latestMemory" ? (sort.ascending ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowDownUp size={13} />}
                  </button>
                </th>
                <th>
                  <span className="sr-only">Chi tiết</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((node) => (
                <tr
                  key={node.id}
                  className={selectedNodeId === node.id ? "selected" : ""}
                >
                  <td>
                    <button
                      className="host-select"
                      onClick={() => onSelectNode(node)}
                      aria-pressed={selectedNodeId === node.id}
                    >
                      <span className="server-icon">
                        <Server size={16} />
                      </span>
                      <span>
                        <strong>{node.hostname}</strong>
                        <small>
                          {node.ip_address}
                        </small>
                      </span>
                    </button>
                  </td>
                  <td>
                    <span className={`status-badge ${nodeHealth(node)}`}>
                      <i />
                      {nodeHealthLabel(node)}
                    </span>
                  </td>
                  <td>
                    <Metric value={node.latestCpu} />
                  </td>
                  <td>
                    <Metric value={node.latestMemory} memory />
                  </td>
                  <td>
                    <button
                      className="icon-button detail-button"
                      aria-label={`Chi tiết ${node.hostname}`}
                      onClick={() => onOpenDetail?.(node)}
                    >
                      <ChevronRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="host-grid">
          {sorted.map((node) => (
            <article
              className={`host-tile ${selectedNodeId === node.id ? "selected" : ""}`}
              key={node.id}
            >
              <button
                className="tile-select"
                onClick={() => onSelectNode(node)}
                aria-pressed={selectedNodeId === node.id}
              >
                <Server size={19} />
                <strong>{node.hostname}</strong>
                <span className={`status-badge ${nodeHealth(node)}`}>
                  {nodeHealthLabel(node)}
                </span>
                <small>
                  {node.ip_address}
                </small>
                <span className="tile-metrics">
                  <span>
                    CPU <b>{formatPercent(node.latestCpu)}</b>
                  </span>
                  <span>
                    RAM <b>{formatPercent(node.latestMemory)}</b>
                  </span>
                </span>
              </button>
              <button
                className="tile-detail"
                onClick={() => onOpenDetail?.(node)}
              >
                Chi tiết máy chủ <ChevronRight size={14} />
              </button>
            </article>
          ))}
        </div>
      )}
      <div className="panel-foot">
        <span>Hiển thị {nodes.length} máy chủ</span>
        <span>
          Chọn host để xem telemetry <ChevronRight size={12} />
        </span>
      </div>
    </section>
  );
}
function Metric({
  value,
  memory = false,
}: {
  value?: number;
  memory?: boolean;
}) {
  return (
    <div className="table-metric">
      <span>{formatPercent(value)}</span>
      <span className="micro-meter">
        <i
          className={
            validMetric(value) && value > (memory ? 85 : 75)
              ? "warning"
              : memory
                ? "memory"
                : ""
          }
          style={{ width: `${validMetric(value) ? Math.min(100, value) : 0}%` }}
        />
      </span>
    </div>
  );
}
