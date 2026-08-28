# SentinelX — Definition of Done

## 1. Foundation Definition of Done

Foundation chỉ hoàn thành khi tất cả mục sau PASS.

### Architecture & Repository
- [ ] Tech stack locked.
- [ ] Architecture docs present.
- [ ] ADRs present.
- [ ] Repository structure stable.
- [ ] AI instructions present.

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

### Shared Contracts
- [ ] typed contracts for first vertical slice.
- [ ] validation tests pass.
- [ ] UTC timestamp conventions documented.

### PostgreSQL
- [ ] async DB lifecycle works.
- [ ] Alembic works.
- [ ] migrations reproducible.
- [ ] integration tests pass.

### Project/Node/Agent
- [ ] Project exists.
- [ ] Node registry exists.
- [ ] Agent enrollment works.
- [ ] identity persists.
- [ ] heartbeat works.
- [ ] `last_seen` works.

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

### Docker Lab
- [ ] backend01/02/03 run.
- [ ] clean startup works.
- [ ] reset script works.

### Load Balancer
- [ ] configurable backend pool.
- [ ] HTTP reverse proxy works.
- [ ] Round Robin works.
- [ ] active/in-flight tracking foundation exists.

### Health Check
- [ ] active health check works.
- [ ] unhealthy backend ejected.
- [ ] recovered backend re-added.
- [ ] flapping baseline controlled.

### Testing
- [ ] unit tests exist.
- [ ] integration tests exist.
- [ ] smoke test exists.
- [ ] `make check` passes.
- [ ] second team member can clone and run without undocumented manual steps.

---

## 2. Foundation Freeze Rule

Sau Foundation Freeze:
- public contracts chỉ đổi có chủ đích;
- DB schema đổi qua migration;
- architecture decision đổi qua ADR;
- business modules được phát triển trên foundation đã ổn định.
