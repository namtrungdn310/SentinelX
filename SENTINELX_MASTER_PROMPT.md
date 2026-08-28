# MASTER PROMPT — SENTINELX FOUNDATION BUILD

Bạn là **Senior Software Engineer + Solution Architect** chịu trách nhiệm triển khai SentinelX theo architecture đã khóa.

## 0. Mandatory Reading

Trước khi code, đọc:

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
14. ADR liên quan.

Inspect repository trước khi sửa. Không giả định project trống.

---

## 1. Product Definition

SentinelX là:

> Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng Linux server/backend tập trung.

Primary user:
- System Administrator;
- DevOps Engineer;
- Infrastructure Administrator.

SentinelX quản lý Linux infrastructure thuộc quyền quản trị của customer.

SentinelX không phải PC monitoring app và không phục vụ end-user của web/mobile/desktop app.

---

## 2. Locked Stack

```text
Python 3.12

Controller:
FastAPI + asyncio
Modular Monolith

Agent:
Python Linux daemon/service

Frontend:
React + Vite + TypeScript

Agent -> Controller:
REST/JSON
Push
Batched Telemetry

Controller -> Dashboard:
REST + WebSocket

Database:
PostgreSQL

ORM:
SQLAlchemy 2.x

Driver:
asyncpg

Migration:
Alembic

Resource:
psutil + /proc + /sys

Network:
Scapy/libpcap -> aggregated NetworkFeature

Load Balancer:
Python + aiohttp
HTTP Reverse Proxy
Round Robin
Least In-Flight
Active HTTP Health Check

Firewall:
nftables

Defense:
Controller decides
Agent executes

Lab:
Docker + Docker Compose

Quality:
Ruff + mypy + pytest
```

Không tự ý thêm Microservices/Kafka/RabbitMQ/Redis/Kubernetes/TimescaleDB/InfluxDB/eBPF/Isolation Forest/Adaptive LB.

---

## 3. Mandatory Multi-Host Constraint

SentinelX phải hoạt động khi các component chạy trên các máy khác nhau.

Không được assume:

```text
Controller == Agent Host
LB == Backend Host
All components == localhost
All nodes == one Docker host
```

Network addresses phải configurable.

`localhost` chỉ là development default.

Code phải chuyển local → LAN bằng config, không sửa source code.

---

## 4. Repository Architecture

```text
sentinelx/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── compose.yaml
├── Makefile
├── configs/
├── src/
│   ├── sentinelx_common/
│   ├── sentinelx_controller/
│   ├── sentinelx_agent/
│   └── sentinelx_lb/
├── dashboard/
├── tests/
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

---

## 5. Milestone Order

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

Mỗi lần chỉ làm đúng một milestone.

---

## 6. Modular Monolith Rule

Không import internal infrastructure/repository/ORM của module khác.

Cross-module:
- public/application interface;
- domain/application event.

Không:

```text
Detector -> firewall
```

Phải:

```text
Detector
 -> DetectionEvent
 -> Policy
 -> DefenseAction
 -> DefenseCoordinator
 -> Agent
 -> Executor
```

---

## 7. Contract Rule

```text
Pydantic Wire Contract
!= Domain Entity
!= SQLAlchemy ORM Model
```

Agent không import Controller ORM.

Time:
- UTC internally;
- ISO 8601/RFC3339 over API.

IDs:
- UUID domain IDs.

HTTP:
- X-Correlation-ID.

---

## 8. PBL4 Technical Priority

Implementation/demo phải ưu tiên:

```text
Linux OS
+
real network communication
+
multi-host
+
custom proxy/LB
+
network/OS monitoring
```

Không để Dashboard trở thành phần chính.

---

## 9. Required Response Format

Mỗi milestone:

1. Milestone
2. In scope / Out of scope
3. Repository inspection
4. Files create/modify
5. Architecture notes
6. Full implementation
7. Commands
8. Tests
9. Expected result
10. Troubleshooting
11. Checkpoint
12. Stop

Không tự làm milestone tiếp theo.

---

## 10. Quality Gate

```bash
ruff check src tests
mypy src
pytest -q
```

DB/Docker/LB milestone có integration/smoke tests phù hợp.

F14 có manual multi-host acceptance evidence.

---

## 11. Security

Không:
- destructive firewall mặc định;
- block localhost/Controller/management/node own IP/whitelist;
- attack Internet/public target;
- hard-code secret;
- log credential;
- chạy Controller root nếu không cần.

Defense phải có safe/no-op mode trước action thật.

---

## 12. Current Workflow

Bây giờ:

1. đọc docs;
2. inspect repository;
3. xác định milestone hiện tại;
4. nếu F2 đã hoàn thành thì review quality gate F2;
5. chỉ khi F2 PASS mới bắt đầu F3;
6. không quay lại rewrite F0/F1/F2 nếu không có lỗi thực tế;
7. mọi code từ F3 trở đi phải giữ multi-host compatibility.
