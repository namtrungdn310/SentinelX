# SentinelX — AI Coding Instructions & System Prompt

## 1. Smart Session Bootstrap & Selective Reading (Tối ưu Token)

Để **tiết kiệm token tối đa** nhưng vẫn **đảm bảo chất lượng và độ chính xác 100%**, AI **KHÔNG ĐƯỢC đọc tràn lan toàn bộ tài liệu**. Thay vào đó, AI phân loại task và đọc chọn lọc theo ma trận sau:

### 1.1 Luôn đọc (Base Context - Siêu ngắn)
1. `AGENTS.md` (File này — nắm vững locked stack, ranh giới và multi-host rule).
2. Mục milestone tương ứng trong `docs/FOUNDATION_ROADMAP.md`.

### 1.2 Đọc theo chuyên môn của từng Task (Task-Specific Routing)

| Phân loại Task | Tài liệu cần đọc bổ sung |
|---|---|
| **API, Wire Contracts, DTO, Enums** | `docs/API_CONTRACTS.md`, `docs/DOMAIN_BOUNDARIES.md` |
| **Database, ORM, Migrations, Repositories** | `docs/DOMAIN_BOUNDARIES.md`, `docs/adr/0004-postgresql-core-storage.md` |
| **Agent Daemon, Metric Collection, Linux OS** | `docs/ARCHITECTURE.md`, `docs/SECURITY_SAFETY.md`, `docs/PBL4_ALIGNMENT.md` |
| **Load Balancer, Reverse Proxy, Health Check** | `docs/ARCHITECTURE.md`, `docs/adr/0005-http-load-balancer.md` |
| **Detection, Policy, Defense Pipeline, Firewall** | `docs/SECURITY_SAFETY.md`, `docs/DOMAIN_BOUNDARIES.md`, `docs/adr/0006-*.md` |
| **Frontend Dashboard (React/Vite)** | `docs/API_CONTRACTS.md`, `docs/TECH_STACK.md` |
| **Testing, Quality Gate, CI** | `docs/TESTING_STRATEGY.md`, `docs/DEV_SETUP.md` |
| **Git, Phân nhánh, Đồng bộ môi trường** | `docs/GIT_WORKFLOW.md`, `docs/DEV_SETUP.md` |
| **Multi-Host Setup, Demo, Acceptance** | `docs/PBL4_ALIGNMENT.md`, `docs/DEMO_PLAN.md` |

---

## 2. SentinelX Product Definition

SentinelX là:

> **Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng Linux server/backend tập trung.**

SentinelX **KHÔNG PHẢI**:
- Task Manager cho desktop;
- Ứng dụng theo dõi PC cho end-user;
- Website thông thường;
- SDK nhúng vào source code ứng dụng của khách hàng;
- Một IDS đơn lẻ hay Load Balancer đơn lẻ;
- Hệ thống microservices enterprise phức tạp.

**Người dùng chính**: System Administrator, DevOps Engineer, Infrastructure Operator.  
**Hạ tầng quản lý**: Linux physical server, Linux VM, Cloud VM, VPS, Docker lab node.

---

## 3. Quyết định kỹ thuật đã khóa (Locked Stack)

| Thành phần | Quyết định kỹ thuật |
|---|---|
| Ngôn ngữ CORE | **Python 3.12** |
| Package & Env Manager | **`uv`** (sử dụng `uv.lock`, `uv run`, `uv sync`) |
| Controller Architecture | **Modular Monolith** (Package-by-feature) |
| Controller Framework | **FastAPI + asyncio** |
| Agent | **Python Linux background daemon/service** |
| Frontend Dashboard | **React + Vite + TypeScript** (Authenticated SPA) |
| Agent → Controller | **REST/JSON Push Model + Batched Telemetry** |
| Controller → Dashboard | **REST (query) + WebSocket (realtime)** |
| Database Storage | **PostgreSQL** (SQLAlchemy 2.x async, asyncpg, Alembic) |
| Resource Monitoring | **psutil + `/proc`, `/sys`** |
| Network Collection | **Scapy/libpcap → Aggregated `NetworkFeature`** (không lưu raw PCAP) |
| Custom Load Balancer | **Python + aiohttp HTTP Reverse Proxy** (Round Robin + Least In-Flight) |
| Health Check | **Active HTTP health check** (Ejection & Re-add) |
| Firewall & Defense | **nftables** (Controller ra quyết định $\rightarrow$ Agent thực thi cục bộ) |
| PBL Environment | **Docker + Docker Compose** |
| Quality Gate | **Ruff + mypy (strict) + pytest** |

> **CẤM TỰ Ý THÊM**: Microservices, Kafka, RabbitMQ, Redis, Kubernetes, TimescaleDB, InfluxDB, eBPF, Isolation Forest, Adaptive LB trước khi có ADR và phê duyệt chính thức.

---

## 4. Ràng buộc Multi-Host bắt buộc (Mandatory Multi-Host Rule)

SentinelX là một networked multi-host system.

AI **TUYỆT ĐỐI KHÔNG ĐƯỢC GIẢ ĐỊNH**:
```text
Controller Host == Agent Host
LB Host == Backend Host
All services == localhost
All nodes == one Docker host
```

**Nguyên tắc**:
- Mọi địa chỉ mạng (Controller bind host/port, Agent Controller URL, LB listen host/port, backend IP/port) **phải cấu hình được qua YAML / biến môi trường**.
- `localhost` chỉ là default lúc dev. Không được hard-code `localhost` trong code logic.
- Code phải chuyển từ chạy local sang chạy mạng LAN nhiều máy **chỉ bằng config, không sửa source code**.

---

## 5. Kỷ luật phân tầng & Ranh giới (Modular Boundaries)

1. **Controller Package-by-Feature**:
   - `modules/`: `system`, `projects`, `nodes`, `telemetry`, `detection`, `incidents`, `policy`, `defense`, `recovery`.
   - Một module **không được import trực tiếp** repository/ORM/private service của module khác. Giao tiếp qua public interface hoặc domain/application event.
2. **`sentinelx_common` không phải thùng rác**:
   - Chỉ chứa: wire contracts, common IDs/enums, config primitives, logging primitives, shared helpers.
   - Không chứa: ORM models, repositories, detection logic, collector, LB algorithms.
3. **Phân biệt Contract vs Domain vs ORM**:
   - Pydantic Wire Contract $\neq$ Domain Entity $\neq$ SQLAlchemy ORM Model.
   - Agent **tuyệt đối không import** ORM model của Controller.
4. **Luồng phòng thủ an toàn (Defense Pipeline)**:
   - Detector phát hiện $\rightarrow$ phát `DetectionEvent`.
   - Detector **không được gọi trực tiếp firewall**. Controller ra quyết định ủy quyền $\rightarrow$ Agent xác thực an toàn cục bộ $\rightarrow$ thực thi nftables.

---

## 6. Lộ trình phát triển & Kỷ luật Milestone (Strict Scope)

Mỗi lần chỉ triển khai **đúng một milestone**. Không làm trước milestone kế tiếp.

```text
F0  Architecture Freeze (DONE)
F1  Repository Bootstrap (DONE)
F2  Config + Logging + Controller Skeleton (DONE)
F3  Shared Contracts + IDs + Time (HIỆN TẠI)
F4  PostgreSQL Foundation
F5  Project + Node Registry
F6  Agent Enrollment
F7  Mock Agent + Heartbeat
F8  Fake Metrics Vertical Slice
F9  Realtime WebSocket
F10 Dashboard Skeleton
F11 Docker PBL Lab
F12 Load Balancer Skeleton
F13 Health Check
F14 Multi-Host Acceptance
FOUNDATION FREEZE

M1 Real Resource Monitoring
M2 Network Collection
M3 Resource Detection
M4 Network Detection
M5 Incident + Policy
M6 Defense Command Pipeline
M7 nftables
M8 Recovery
CORE FREEZE
```

---

## 7. Quy chuẩn Git & Phân nhánh (Git Workflow with `uv`)

1. **Nhánh `main`**: Chỉ nhận PR từ `dev`. Không commit trực tiếp.
2. **Nhánh `dev`**: Nhánh tích hợp chính. Không commit trực tiếp.
3. **Nhánh làm việc**: Luôn tạo nhánh riêng từ `dev` (ví dụ `milestone/f3-shared-contracts` hoặc `feat/...`).
4. **Môi trường**: Luôn dùng `uv sync --all-extras` và `uv run <command>`.

---

## 8. Cấu trúc phản hồi bắt buộc cho mỗi Coding Task

Mỗi lần triển khai, AI phải trả lời đầy đủ 12 mục:

1. **## 1. Milestone**: Tên & mục tiêu.
2. **## 2. Scope**: In scope / Out of scope rõ ràng.
3. **## 3. Repository inspection**: File/folder hiện có liên quan.
4. **## 4. Files to create/modify**: Bảng (File | Action | Responsibility).
5. **## 5. Architecture notes**: Phân tích ranh giới & phụ thuộc.
6. **## 6. Implementation**: Code hoàn chỉnh, không pseudo-code.
7. **## 7. Commands**: Lệnh chạy và test bằng `uv`.
8. **## 8. Expected result**: Output mong đợi.
9. **## 9. Troubleshooting**: Dự phòng lỗi thực tế.
10. **## 10. Checkpoint**: Checklist PASS/FAIL.
11. **## 11. Stop**: Dừng lại, không tự làm milestone tiếp theo.

---

## 9. Quality Gate bắt buộc

Trước khi coi một milestone hoàn thành:

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
```

Tất cả phải **PASS 100%** (0 errors, 0 linter warnings).
