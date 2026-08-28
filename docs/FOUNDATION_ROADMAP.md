# SentinelX — Foundation Implementation Roadmap

## Nguyên tắc

Làm theo thứ tự.
Không skip milestone.
Không triển khai business logic trước `FOUNDATION FREEZE`.

---

# F0 — Architecture Freeze

Deliverables:
- `AGENTS.md`
- architecture docs
- tech stack
- ADRs

Done khi:
- các decision lớn đã khóa;
- AI biết boundary và scope.

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
- contracts validation tests PASS;
- invalid units/ranges/timestamps bị reject phù hợp.

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
- re-use token được xử lý rõ.

---

# F7 — Mock Agent + Heartbeat

Deliverables:
- `sentinelx_agent` runtime skeleton;
- Agent settings;
- local identity persistence;
- Controller client;
- heartbeat loop;
- retry/backoff baseline;
- `last_seen`.

Không dùng psutil thật.

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

Agent placement cho demo được quyết định ở đây dựa trên visibility tests.

Done khi:
- clean clone/start;
- services healthy;
- sample backends reachable.

---

# F12 — Load Balancer Skeleton

Deliverables:
- aiohttp HTTP listener;
- configurable backend pool;
- reverse proxy;
- Round Robin;
- request/in-flight tracking foundation.

Không Adaptive LB.

Done khi:
```text
Client -> LB -> backend01/02/03
```
route ổn định.

---

# F13 — Health Check Foundation

Deliverables:
- active HTTP `/health` probing;
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

# FOUNDATION FREEZE

Foundation được freeze khi:
- Mock Agent → Controller → PostgreSQL → Dashboard realtime chạy;
- LB → 3 backends chạy;
- health eject/re-add chạy;
- tests/smoke tests PASS;
- README từ clean clone chạy được.

---

# Sau Foundation

Thứ tự tiếp theo:

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
- Adaptive LB;
- advanced statistics;
- eBPF;
- tc/cgroups;
- specialized TSDB;
- distributed deployment.
