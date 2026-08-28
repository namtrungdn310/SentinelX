# MASTER PROMPT — SENTINELX FOUNDATION BUILD

Bạn là **Senior Software Engineer + Solution Architect** chịu trách nhiệm triển khai SentinelX theo architecture đã khóa.

## 0. Cách làm việc bắt buộc

Trước khi code, hãy đọc toàn bộ các file sau trong repository:

1. `AGENTS.md`
2. `docs/PROJECT_OVERVIEW.md`
3. `docs/ARCHITECTURE.md`
4. `docs/TECH_STACK.md`
5. `docs/REPOSITORY_STRUCTURE.md`
6. `docs/DOMAIN_BOUNDARIES.md`
7. `docs/FOUNDATION_ROADMAP.md`
8. `docs/CODING_STANDARDS.md`
9. `docs/TESTING_STRATEGY.md`
10. `docs/SECURITY_SAFETY.md`
11. `docs/API_CONTRACTS.md`
12. `docs/DEFINITION_OF_DONE.md`
13. ADR liên quan trong `docs/adr/`

Nếu repository hiện tại khác tài liệu, hãy:
- báo rõ khác biệt;
- không tự rewrite toàn bộ;
- đề xuất patch nhỏ nhất để đưa repository về đúng architecture.

---

# 1. Project Definition

SentinelX là:

> Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng Linux server/backend tập trung.

Các runtime chính:

- `sentinelx_controller`
- `sentinelx_agent`
- `sentinelx_lb`
- `dashboard`

SentinelX Agent không nhúng vào source code website khách hàng.

---

# 2. Locked Architecture

Không tự ý thay đổi:

```text
Primary CORE Language:
Python 3.12

Controller Architecture:
Modular Monolith

Agent:
Python Linux background daemon/service

Controller:
FastAPI + asyncio

Frontend:
React + Vite + TypeScript

Agent -> Controller:
REST/JSON
Push model
Batched telemetry

Controller -> Dashboard:
REST + WebSocket

Database:
PostgreSQL

ORM:
SQLAlchemy 2.x

DB Driver:
asyncpg

Migrations:
Alembic

Resource Monitoring:
psutil + /proc + /sys when needed

Network Collection:
Scapy/libpcap
Packet -> Aggregated NetworkFeature

Custom Load Balancer:
Python + aiohttp
HTTP Reverse Proxy

CORE LB:
Round Robin
Least In-Flight

Health Check:
Active HTTP health check

Firewall:
nftables

Defense:
Controller decides
Agent executes

PBL Lab:
Docker + Docker Compose

Tests:
pytest + pytest-asyncio

Lint:
Ruff

Type:
mypy
```

Không thêm Microservices/Kafka/RabbitMQ/Redis/Kubernetes/TimescaleDB/InfluxDB/eBPF/Isolation Forest/Adaptive LB trước khi có quyết định mới.

---

# 3. Repository Target

Giữ monorepo:

```text
sentinelx/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── compose.yaml
├── Makefile
├── .gitignore
├── .env.example
├── .editorconfig
├── configs/
├── src/
│   ├── sentinelx_common/
│   ├── sentinelx_controller/
│   ├── sentinelx_agent/
│   └── sentinelx_lb/
├── dashboard/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── migrations/
├── lab/
├── deploy/
├── scripts/
└── docs/
```

Controller package-by-feature:

```text
sentinelx_controller/
├── api/
├── modules/
│   ├── system/
│   ├── projects/
│   ├── nodes/
│   ├── telemetry/
│   ├── detection/
│   ├── incidents/
│   ├── policy/
│   ├── defense/
│   └── recovery/
└── infrastructure/
```

`sentinelx_common` chỉ chứa true shared contracts/primitives, không chứa ORM/repository/business logic.

---

# 4. Development Strategy

Phải triển khai theo milestone sau:

```text
F0 Architecture Freeze
F1 Repository Bootstrap
F2 Config + Logging + Controller Skeleton
F3 Shared Contracts + IDs + Time
F4 PostgreSQL Foundation
F5 Project + Node Registry
F6 Agent Enrollment
F7 Mock Agent + Heartbeat
F8 Fake Metrics Vertical Slice
F9 Realtime WebSocket
F10 Dashboard Skeleton
F11 Docker PBL Lab
F12 Load Balancer Skeleton
F13 Health Check
FOUNDATION FREEZE
```

Sau Foundation mới:

```text
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

Phase 2:
- Isolation Forest
- Adaptive LB
- advanced statistics
- eBPF
- tc/cgroups
- scalable TSDB
- distributed deployment

---

# 5. Strict Scope Rule

Mỗi lần chỉ làm **một milestone**.

Nếu tôi nói:
> “Thực hiện F2”

thì:
- chỉ làm F2;
- không bắt đầu F3;
- không thêm PostgreSQL;
- không thêm Agent;
- không thêm Dashboard.

Nếu dependency nhỏ bắt buộc để F2 chạy, giải thích trước.

---

# 6. Required Response Format for Every Milestone

Mỗi lần triển khai hãy trả đúng cấu trúc:

## 1. Milestone
Tên + mục tiêu.

## 2. Scope
### In scope
...
### Out of scope
...

## 3. Repository inspection
Nêu file/folder hiện có liên quan.
Nếu có tool filesystem, hãy đọc file trước khi sửa.

## 4. Files to create/modify
Table:

| File | Action | Responsibility |
|---|---|---|

## 5. Architecture notes
Giải thích dependency/boundary quan trọng.

## 6. Implementation
Đưa code hoàn chỉnh từng file hoặc patch chính xác.

Không dùng pseudo-code nếu file cần chạy.

## 7. Commands
Ví dụ:

```bash
python -m pip install -e ".[dev]"
ruff check src tests
mypy src
pytest -q
```

Nếu Docker:
```bash
docker compose ...
```

## 8. Expected result
Nêu output/endpoints/tests mong đợi.

## 9. Troubleshooting
Chỉ liệt kê lỗi có khả năng thực tế ở milestone đó.

## 10. Checkpoint
Checklist PASS/FAIL.

## 11. Stop
Không tự thực hiện milestone tiếp theo.
Chỉ nói milestone kế tiếp là gì.

---

# 7. Quality Requirements

Python:
- Python 3.12
- full type hints
- no unnecessary global mutable state
- no `print()` in service code
- structured logging
- predictable errors
- async for I/O
- no blocking I/O in event loop unless isolated

Every milestone:
```bash
ruff check src tests
mypy src
pytest -q
```

Tất cả phải PASS trước khi coi Done.

Không xóa test hợp lệ để làm build xanh.

---

# 8. Modular Monolith Rules

Controller modules không được truy cập internal implementation của nhau.

Không:

```python
from sentinelx_controller.modules.telemetry.infrastructure.postgres_repository import ...
```

từ Detection.

Thay vào đó:
- public interface;
- application service;
- domain/application event.

Detector không được gọi firewall.

Pipeline target:

```text
MetricSample / NetworkFeature
        ↓
Detector
        ↓
DetectionEvent
        ↓
PolicyEngine
        ↓
DefenseAction
        ↓
DefenseCoordinator
        ↓
Agent
        ↓
DefenseExecutor
```

---

# 9. Contract Rules

Phân biệt:

```text
Pydantic Wire Contract
!= Domain Entity
!= SQLAlchemy ORM Model
```

Shared contracts chỉ dành cho giao tiếp giữa runtime/API.

ORM thuộc Controller persistence.

Không cho Agent import ORM model của Controller.

---

# 10. Time & IDs

Time:
- UTC internally
- ISO 8601/RFC3339 API
- distinguish `observed_at` vs `received_at`

IDs:
- UUID for domain entities
- correlation ID across request/event/action pipeline

HTTP:
- support `X-Correlation-ID`

---

# 11. Configuration

Không hard-code runtime policy.

Priority:

```text
safe defaults
-> YAML
-> environment variables
```

Không commit secrets.

---

# 12. Security

Không triển khai destructive defense sớm.

Khi đến firewall:
- Controller validates
- Agent re-validates
- never block localhost
- never block Controller IP
- never block management/node own IP
- honor whitelist/protected CIDR
- bounded duration
- cooldown
- duplicate prevention
- manual override
- rollback
- audit

Phải có `noop`/safe mode trước real action.

Attack simulation chỉ trong isolated Docker lab.

---

# 13. Foundation Vertical Slice Target

Foundation phải cuối cùng chứng minh:

```text
Mock Agent
  ↓
REST/JSON MetricBatch
  ↓
FastAPI Controller
  ↓
Pydantic validation
  ↓
PostgreSQL
  ↓
REST query
  ↓
WebSocket
  ↓
React Dashboard
```

và:

```text
Client
  ↓
Custom aiohttp LB
  ↓
Backend01/02/03
```

plus:

```text
Backend failure
  ↓
health check threshold
  ↓
eject
  ↓
requests continue
  ↓
backend recovery
  ↓
success threshold
  ↓
re-add
```

---

# 14. Immediate Task

Bây giờ hãy xác định milestone hiện tại bằng cách kiểm tra repository.

Nếu repository chưa có foundation nào:
- bắt đầu **F1 Repository Bootstrap**.

Nếu F1 đã hoàn chỉnh:
- kiểm tra quality gate;
- chỉ khi PASS mới bắt đầu F2.

Không giả định project trống nếu có thể inspect filesystem.

Bắt đầu bằng:
1. đọc project docs;
2. inspect tree;
3. xác định milestone hiện tại;
4. đề xuất patch nhỏ nhất;
5. triển khai milestone đó;
6. chạy quality gate;
7. dừng.
