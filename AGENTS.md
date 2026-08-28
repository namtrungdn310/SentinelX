# SentinelX — AI Coding Instructions & System Prompt

## 1. Mandatory Session Bootstrap (Bắt buộc chạy đầu mỗi session/task)

Mỗi khi nhận một task mới, AI **PHẢI TỰ ĐỘNG ĐỌC VÀ HIỂU LẠI TOÀN BỘ THÔNG TIN DỰ ÁN** theo đúng thứ tự sau trước khi sinh code:

1. `AGENTS.md` (File này)
2. `docs/PROJECT_OVERVIEW.md` (Bản chất sản phẩm, phạm vi hạ tầng Linux)
3. `docs/PBL4_ALIGNMENT.md` (3 trụ cột PBL4: Hệ điều hành, Mạng máy tính, Lập trình mạng)
4. `docs/ARCHITECTURE.md` (Modular Monolith Controller, 4 runtimes, data flow, multi-host)
5. `docs/TECH_STACK.md` (Tech stack đã khóa, cấm microservices/Kafka/Redis/ML)
6. `docs/REPOSITORY_STRUCTURE.md` (Layout Monorepo, trách nhiệm từng thư mục)
7. `docs/DOMAIN_BOUNDARIES.md` (Ranh giới module, Contract vs Domain vs ORM)
8. `docs/FOUNDATION_ROADMAP.md` (Lộ trình chi tiết F0 -> F14 -> M1 -> M8)
9. `docs/GIT_WORKFLOW.md` & `docs/DEV_SETUP.md` (Quy chuẩn phân nhánh Git & `uv`)
10. `docs/CODING_STANDARDS.md` (Tiêu chuẩn code Python 3.12, typing, logging, async)
11. `docs/TESTING_STRATEGY.md` (Chiến lược kiểm thử và Quality Gate)
12. `docs/SECURITY_SAFETY.md` (Nguyên tắc an toàn phòng thủ, whitelist, noop mode)
13. `docs/API_CONTRACTS.md` (Quy ước REST API, correlation ID, time UTC, UUID)
14. `docs/DEFINITION_OF_DONE.md` (Checklist hoàn thành milestone)
15. `docs/adr/` (Các quyết định kiến trúc đã khóa ADR 0001 -> 0006)

> **CẤM**: Không suy đoán, không code dựa trên trí nhớ mơ hồ nếu tài liệu đã quy định rõ.

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

**Người dùng chính (Primary User)**:
- System Administrator, DevOps Engineer, Infrastructure Operator.

**Hạ tầng quản lý (Managed Target)**:
- Linux physical server, Linux VM, Cloud VM, VPS, Docker lab node.

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
