# SentinelX — Definition of Done

## 1. Foundation Definition of Done

Foundation chỉ hoàn thành khi tất cả mục phù hợp dưới đây PASS.

### Architecture & Repository

- [ ] Tech stack locked.
- [ ] Architecture docs present.
- [ ] PBL4 alignment documented.
- [ ] Multi-host requirement documented.
- [ ] ADRs present.
- [ ] Repository structure stable.
- [ ] AI coding instructions present.

### Tooling

- [ ] Python 3.12 environment reproducible.
- [ ] Ruff works.
- [ ] mypy works.
- [ ] pytest works.
- [ ] `.env.example` exists.
- [ ] README allows second developer to start.

### Controller

- [ ] FastAPI app factory exists.
- [ ] `/api/v1/system/health` works.
- [ ] structured logging works.
- [ ] correlation ID works.
- [ ] Controller bind host/port configurable.
- [ ] Controller can listen on an interface usable by another LAN host.

### Shared Contracts

- [ ] typed contracts for first vertical slice.
- [ ] validation tests pass.
- [ ] UUID conventions documented.
- [ ] UTC timestamp conventions documented.
- [ ] `observed_at` and `received_at` semantics clear where applicable.

### PostgreSQL

- [ ] async DB lifecycle works.
- [ ] Alembic works.
- [ ] migrations reproducible.
- [ ] integration tests pass.

### Project / Node / Agent

- [ ] Project exists.
- [ ] Node registry exists.
- [ ] Agent enrollment works.
- [ ] Agent Controller URL configurable.
- [ ] identity persists.
- [ ] heartbeat works.
- [ ] `last_seen` works.
- [ ] no Agent architecture dependency on Controller localhost.

### Telemetry

- [ ] Mock Agent sends fake metrics.
- [ ] Controller validates MetricBatch.
- [ ] invalid metrics rejected.
- [ ] metrics stored.
- [ ] metrics queryable.
- [ ] retry/buffer baseline exists.

### Realtime

- [ ] WebSocket endpoint works.
- [ ] realtime fake metric update works.
- [ ] reconnect baseline works.

### Dashboard

- [ ] React/Vite/TypeScript app runs.
- [ ] nodes displayed.
- [ ] fake CPU/RAM displayed.
- [ ] realtime update visible.
- [ ] dashboard can connect to configured Controller address.

### Docker Lab

- [ ] backend01/02/03 run.
- [ ] clean startup works.
- [ ] reset script works.
- [ ] Docker lab is documented as development/test profile, not architecture limitation.

### Load Balancer

- [ ] configurable LB listen host/port.
- [ ] configurable backend pool.
- [ ] remote backend host/IP supported.
- [ ] HTTP reverse proxy works.
- [ ] Round Robin works.
- [ ] active/in-flight tracking foundation exists.

### Health Check

- [ ] active health check works.
- [ ] remote backend can be checked.
- [ ] unhealthy backend ejected.
- [ ] recovered backend re-added.
- [ ] flapping baseline controlled.

### Multi-Host Capability

- [ ] Controller and Agent can run on different machines.
- [ ] Agent enrollment/heartbeat works across LAN.
- [ ] telemetry transfers across LAN.
- [ ] Dashboard shows a remote node.
- [ ] LB can route to backend on another machine.
- [ ] remote backend failure is detected.
- [ ] remote backend recovery is detected.
- [ ] moving local → multi-host requires config changes only.
- [ ] no source-code edit is required to replace localhost with remote IP.

### Testing

- [ ] unit tests exist.
- [ ] integration tests exist.
- [ ] smoke test exists.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` passes.
- [ ] `pytest -q` passes.
- [ ] multi-host acceptance has been manually demonstrated/documented.
- [ ] second team member can clone and run without undocumented manual steps.

---

## 2. Foundation Freeze Rule

Sau Foundation Freeze:

- public contracts chỉ đổi có chủ đích;
- DB schema đổi qua migration;
- architecture decision đổi qua ADR;
- multi-host compatibility không được phá;
- business modules được phát triển trên foundation đã ổn định.

---

## 3. CORE Definition of Done

CORE chỉ được coi là hoàn thành khi foundation đã freeze và có ít nhất:

- real Linux resource monitoring;
- process/service health;
- baseline network collection;
- baseline resource detection;
- ít nhất một network anomaly detector hoạt động chắc chắn;
- alert/incident flow;
- policy boundary;
- một automated defense path an toàn;
- một recovery path;
- custom LB + health failover;
- multi-host demonstration;
- report/demo evidence.
