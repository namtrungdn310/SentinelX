# SentinelX — Foundation Implementation Roadmap

## Nguyên tắc

- Làm theo thứ tự.
- Không skip milestone.
- Không triển khai business logic trước `FOUNDATION FREEZE`.
- Mỗi milestone phải PASS quality gate trước khi sang bước tiếp theo.
- Foundation phải kết thúc bằng một **multi-host acceptance test**, không chỉ single-host Docker.

---

# F0 — Architecture Freeze

Deliverables:

- `AGENTS.md`
- `docs/PROJECT_OVERVIEW.md`
- `docs/PBL4_ALIGNMENT.md`
- `docs/ARCHITECTURE.md`
- `docs/TECH_STACK.md`
- `docs/REPOSITORY_STRUCTURE.md`
- `docs/DOMAIN_BOUNDARIES.md`
- `docs/FOUNDATION_ROADMAP.md`
- `docs/CODING_STANDARDS.md`
- `docs/TESTING_STRATEGY.md`
- `docs/SECURITY_SAFETY.md`
- `docs/API_CONTRACTS.md`
- `docs/DEFINITION_OF_DONE.md`
- ADRs

Done khi:
- product scope rõ;
- primary user rõ;
- multi-host requirement đã khóa;
- tech stack đã khóa;
- module boundary đã khóa;
- AI coding rules rõ.

---

# F1 — Repository Bootstrap

Deliverables:

- root monorepo;
- `pyproject.toml`;
- `.gitignore`;
- `.editorconfig`;
- `.env.example`;
- `Makefile`;
- package skeleton;
- test skeleton.

Quality gate:
- package install được;
- Ruff/mypy/pytest chạy.

---

# F2 — Config + Logging + Controller Application Skeleton

Deliverables:

- generic YAML loader;
- Controller settings;
- structured JSON logging;
- correlation ID;
- FastAPI app factory;
- versioned router;
- `/api/v1/system/health`;
- unit tests.

Multi-host requirement:
- Controller bind host configurable;
- default development bind có thể là `0.0.0.0`;
- không hard-code architecture vào localhost.

Done khi:

```text
GET /api/v1/system/health -> 200
X-Correlation-ID exists
ruff PASS
mypy PASS
pytest PASS
```

---

# F3 — Shared Contracts + ID/Time Foundation

Chỉ tạo contract cần cho vertical slice đầu tiên.

Deliverables:

- typed IDs/UUID strategy;
- UTC timestamp helpers;
- Project/Node API contracts;
- Agent enrollment request/response;
- heartbeat request/response;
- `MetricSample`;
- `MetricBatch`.

Không tạo toàn bộ future models nếu chưa dùng.

Done khi:
- contract validation tests PASS;
- invalid ranges/timestamps bị reject phù hợp.

---

# F4 — PostgreSQL Foundation

Add:

- SQLAlchemy 2.x;
- asyncpg;
- Alembic.

Deliverables:

- async engine/session lifecycle;
- DB settings;
- migration setup;
- health/readiness DB path;
- test database strategy.

Không dùng shared ORM.

Done khi:
- migration upgrade chạy;
- app connect/disconnect sạch;
- integration test DB PASS.

---

# F5 — Project + Node Registry

Deliverables:

- Projects module;
- Nodes module;
- domain/application/repository boundaries;
- create/list/get project;
- create/register node record;
- node persistence.

Không làm Agent thực tế.

Done khi:
- API + DB integration tests PASS.

---

# F6 — Agent Enrollment Foundation

Deliverables:

- enrollment token concept;
- Agent enrollment endpoint;
- node credential output;
- token invalidation/expiry baseline;
- idempotency strategy.

Chưa làm production mTLS.

Done khi:
- valid enrollment PASS;
- invalid/expired token FAIL;
- reuse token được xử lý rõ.

---

# F7 — Mock Agent + Heartbeat

Deliverables:

- `sentinelx_agent` runtime skeleton;
- Agent settings;
- configurable Controller URL;
- local identity persistence;
- Controller client;
- heartbeat loop;
- retry/backoff baseline;
- `last_seen`.

Không dùng psutil thật.

Multi-host rule:
- Agent không giả định Controller chạy localhost;
- Controller URL lấy từ config/env.

Done khi:

```text
Mock Agent starts
 -> enrolls/loads identity
 -> heartbeats
 -> node appears ONLINE
```

---

# F8 — Fake Metrics Vertical Slice

Deliverables:

- fake metric generator;
- batching;
- telemetry endpoint;
- validation;
- storage;
- metrics query API.

Flow:

```text
Mock Agent
  -> MetricBatch
  -> Controller
  -> validation
  -> PostgreSQL
  -> REST query
```

Done khi integration test end-to-end PASS.

---

# F9 — Realtime Foundation

Deliverables:

- Controller realtime hub;
- WebSocket endpoint;
- bounded fan-out strategy;
- fake metrics → websocket event;
- reconnect-friendly protocol baseline.

Done khi test client nhận realtime update.

---

# F10 — Dashboard Skeleton

Deliverables:

- React + Vite + TypeScript;
- app routing;
- API client;
- WebSocket client;
- Overview page;
- Nodes page;
- fake CPU/RAM chart.

Không polish UI quá sớm.

Done khi:
- dashboard load;
- REST initial data;
- realtime update;
- reconnect baseline.

---

# F11 — Docker PBL Lab

Deliverables:

- PostgreSQL container;
- Controller container/process;
- backend01/02/03;
- network setup;
- repeatable startup;
- reset script.

Docker là development/integration lab, không phải deployment assumption.

Agent placement cho demo được quyết định dựa trên visibility tests.

Done khi:
- clean clone/start;
- services healthy;
- sample backends reachable.

---

# F12 — Load Balancer Skeleton

Deliverables:

- aiohttp HTTP listener;
- configurable listen address;
- configurable backend pool;
- reverse proxy;
- Round Robin;
- request/in-flight tracking foundation.

Không Adaptive LB.

Không hard-code backend thành localhost.

Done khi:

```text
Client -> LB -> backend01/02/03
```

route ổn định.

---

# F13 — Health Check Foundation

Deliverables:

- active HTTP `/health` probing;
- configurable remote backend address;
- health state;
- routing state;
- failure threshold;
- success threshold;
- ejection;
- re-add;
- flapping protection baseline.

Done khi:

```text
stop backend02
 -> eject
 -> traffic continues 01/03

start backend02
 -> recovering
 -> re-add
```

---

# F14 — Multi-Host Acceptance

## Mục tiêu

Chứng minh Foundation không phụ thuộc single-host Docker hoặc localhost.

## Topology tối thiểu

```text
Machine A
├── Controller
├── Dashboard
└── Load Balancer

Machine B
├── Backend01
└── SentinelX Agent
```

Khuyến nghị có Machine C:

```text
Machine C
├── Backend02
└── SentinelX Agent
```

## Acceptance Criteria

- Agent B kết nối Controller A qua LAN/IP network.
- Agent B enroll/heartbeat thành công.
- Agent B gửi telemetry tới Controller A.
- Dashboard A hiển thị remote Node B.
- LB A route request tới Backend B bằng remote IP/port.
- Nếu có C, LB route qua B/C.
- Backend remote failure được health check phát hiện.
- Backend remote recovery được re-add.
- Chuyển local → LAN không cần sửa source code.
- Chỉ thay config/network address.

Done khi toàn bộ acceptance PASS và được ghi lại trong demo notes.

---

# FOUNDATION FREEZE

Foundation được freeze khi:

```text
Remote/Mock Agent
  -> Controller
  -> PostgreSQL
  -> Dashboard realtime
```

chạy ổn định và:

```text
Client
  -> Custom LB
  -> Remote Backend(s)
```

hoạt động với health eject/re-add.

Required:
- tests PASS;
- smoke tests PASS;
- multi-host acceptance PASS;
- README cho phép thành viên thứ hai clone/run;
- không có architectural localhost dependency.

---

# Sau Foundation

Thứ tự business implementation:

```text
M1 Real Resource Monitoring
M2 Network Collection + Aggregation
M3 Resource Detection
M4 Network Detection
M5 Incident + Policy
M6 Defense Command Pipeline
M7 nftables Executor
M8 Recovery/Cooldown
CORE FREEZE
```

Phase 2 sau CORE:

- Isolation Forest;
- Adaptive Load Balancing;
- advanced statistics;
- eBPF;
- tc/cgroups;
- specialized TSDB;
- distributed deployment.
