# SentinelX — AI Coding Instructions

## 1. Mandatory Reading Order

Trước khi sửa hoặc sinh code, AI PHẢI đọc theo thứ tự:

1. `AGENTS.md`
2. `docs/PROJECT_OVERVIEW.md`
3. `docs/PBL4_ALIGNMENT.md`
4. `docs/ARCHITECTURE.md`
5. `docs/TECH_STACK.md`
6. `docs/REPOSITORY_STRUCTURE.md`
7. `docs/DOMAIN_BOUNDARIES.md`
8. `docs/FOUNDATION_ROADMAP.md`
9. `docs/CODING_STANDARDS.md`
10. `docs/TESTING_STRATEGY.md`
11. `docs/SECURITY_SAFETY.md`
12. `docs/API_CONTRACTS.md`
13. `docs/DEFINITION_OF_DONE.md`
14. ADR liên quan trong `docs/adr/`

Không được code dựa trên suy đoán nếu documentation đã quy định.

---

## 2. SentinelX Definition

SentinelX là:

> Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng Linux server/backend tập trung.

SentinelX KHÔNG phải:

- desktop Task Manager;
- PC monitoring product cho end-user;
- website thông thường;
- SDK nhúng vào source code khách hàng;
- một IDS đơn lẻ;
- một Load Balancer đơn lẻ;
- hệ thống microservices enterprise.

Primary user:
- System Administrator;
- DevOps Engineer;
- Infrastructure Administrator;
- Developer/Owner tự quản lý Linux infrastructure.

Managed target:
- Linux physical server;
- Linux VM/cloud VM/VPS;
- Linux PC/laptop đang đóng vai server;
- Docker/container lab node.

---

## 3. Locked Technical Decisions

Không tự ý thay đổi:

- Primary CORE language: **Python 3.12**
- Controller: **Modular Monolith**
- Agent: **Python Linux daemon/service**
- Controller framework: **FastAPI + asyncio**
- Frontend: **React + Vite + TypeScript**
- Agent → Controller: **REST/JSON Push + Batched Telemetry**
- Controller → Dashboard: **REST + WebSocket**
- Database: **PostgreSQL**
- ORM: **SQLAlchemy 2.x**
- DB driver: **asyncpg**
- Migrations: **Alembic**
- Resource monitoring: **psutil + /proc + /sys when needed**
- Network collection: **Scapy/libpcap → aggregated NetworkFeature**
- Custom LB: **Python + aiohttp HTTP reverse proxy**
- CORE algorithms: **Round Robin + Least In-Flight**
- Health check: **Active HTTP health check**
- Firewall: **nftables**
- Defense boundary: **Controller decides, Agent executes**
- PBL environment: **Docker + Docker Compose**
- Internal Controller communication: **public interfaces/direct calls + bounded in-process async events**
- Testing: **pytest + pytest-asyncio**
- Lint/format: **Ruff**
- Type checking: **mypy**

Không thêm Microservices/Kafka/RabbitMQ/Redis/Kubernetes/TimescaleDB/InfluxDB/eBPF/Isolation Forest/Adaptive LB trước khi có ADR và approval.

---

## 4. Mandatory Multi-Host Rule

SentinelX là một networked multi-host system.

AI KHÔNG ĐƯỢC giả định:

```text
Controller == Agent Host
LB == Backend Host
All services == localhost
All nodes == one Docker host
```

Các network values phải configurable:

- Controller bind host;
- Controller port;
- Agent Controller URL;
- LB listen host/port;
- backend host/IP;
- backend port.

`localhost` chỉ được dùng như development default.

Không được hard-code:

```python
CONTROLLER_URL = "http://localhost:8000"
```

nếu giá trị đó là runtime architecture setting.

Code phải có khả năng chuyển từ local development sang LAN/multi-host bằng config, không sửa source code.

---

## 5. Architecture Principles

### Foundation before business logic

Trước `FOUNDATION FREEZE`, không triển khai thật:

- resource anomaly rules;
- Port Scan detector;
- SYN Flood detector;
- Isolation Forest;
- Adaptive LB;
- real destructive firewall actions;
- advanced self-healing;
- eBPF.

### No over-engineering

Không tự thêm:
- microservices;
- CQRS framework;
- external message broker;
- Kubernetes;
- generic plugin system;
- enterprise DI container.

### Module boundary

Controller dùng package-by-feature.

Một module không import internal repository/ORM/private service của module khác.

Cross-module communication qua:
- public/application interface;
- domain/application event khi phù hợp.

### `sentinelx_common` is not a dumping ground

Allowed:
- wire contracts;
- common IDs/enums;
- config primitives;
- observability primitives;
- truly shared helpers.

Forbidden:
- ORM;
- repositories;
- Detection logic;
- Agent collectors;
- LB algorithm.

---

## 6. PBL4 Technical Priority

Implementation và demo phải thể hiện rõ:

### Operating Systems
- Linux resources;
- process/service;
- concurrency;
- daemon/service;
- OS/network interfaces;
- local execution/privilege.

### Computer Networks
- IP;
- ports;
- TCP/HTTP;
- connections;
- traffic;
- health checks;
- reverse proxy;
- load balancing.

### Network Programming
- remote Agent ↔ Controller;
- REST/HTTP;
- WebSocket;
- retry/reconnect;
- concurrent network I/O;
- remote backend health check;
- custom proxy.

Dashboard/UI không được lấn át phần OS/network.

---

## 7. Development Milestones

Chỉ code milestone hiện tại:

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
F14 Multi-Host Acceptance
FOUNDATION FREEZE
```

Không tự làm milestone kế tiếp.

---

## 8. Required AI Output per Coding Task

Mỗi lần triển khai:

### A. Milestone
Tên + mục tiêu.

### B. Scope
- In scope
- Out of scope

### C. Repository Inspection
Đọc tree/file hiện có trước khi sửa.

### D. Files
Table:
| File | Action | Responsibility |

### E. Architecture Notes
Giải thích boundary/dependency.

### F. Implementation
Code chạy được, không pseudo-code nếu file cần thực thi.

### G. Commands
Install/run/lint/typecheck/tests.

### H. Expected Result
Endpoint/output/test mong đợi.

### I. Checkpoint
PASS/FAIL.

### J. Stop
Không làm milestone kế tiếp.

---

## 9. Quality Gate

Mỗi milestone:

```bash
ruff check src tests
mypy src
pytest -q
```

Nếu milestone có DB/Docker/LB:
- integration test tương ứng;
- smoke test tương ứng.

Không xóa assertion hợp lệ để làm test xanh.

---

## 10. Security/Safety

Không:
- chạy destructive firewall mặc định;
- block localhost;
- block Controller IP;
- block management IP;
- block node own IP;
- block whitelist/protected CIDR;
- attack public Internet;
- commit secret;
- log credential;
- yêu cầu Controller chạy root nếu không cần.

Defense thật phải có safe/no-op mode trước.

---

## 11. When Information Is Missing

Nếu uncertainty chỉ là local implementation detail:
- chọn giải pháp đơn giản;
- ghi assumption.

Nếu ảnh hưởng:
- public contract;
- DB schema;
- security;
- architecture;
- deployment;
- tech stack;

AI phải dừng và xin quyết định.

---

## 12. Foundation End State

Foundation phải chứng minh:

```text
Remote/Mock Agent
      ↓
REST/JSON MetricBatch
      ↓
Controller
      ↓
Validation
      ↓
PostgreSQL
      ↓
REST + WebSocket
      ↓
Dashboard
```

và:

```text
Client
  ↓
SentinelX LB
  ↓
Remote Backend01/02/03
```

plus backend health ejection/re-add.

Foundation cuối cùng phải PASS multi-host acceptance test.
