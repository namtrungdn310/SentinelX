# SentinelX — Repository Structure

## 1. Monorepo Layout

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
│
├── configs/
│   ├── controller.yaml
│   ├── agent.example.yaml
│   └── lb.example.yaml
│
├── src/
│   ├── sentinelx_common/
│   │   ├── contracts/
│   │   ├── config/
│   │   ├── observability/
│   │   └── utils/
│   │
│   ├── sentinelx_controller/
│   │   ├── api/
│   │   ├── modules/
│   │   │   ├── system/
│   │   │   ├── projects/
│   │   │   ├── nodes/
│   │   │   ├── telemetry/
│   │   │   ├── detection/
│   │   │   ├── incidents/
│   │   │   ├── policy/
│   │   │   ├── defense/
│   │   │   └── recovery/
│   │   └── infrastructure/
│   │       ├── database/
│   │       ├── events/
│   │       └── realtime/
│   │
│   ├── sentinelx_agent/
│   │   ├── runtime/
│   │   ├── collectors/
│   │   ├── aggregation/
│   │   ├── transport/
│   │   ├── buffering/
│   │   └── executors/
│   │
│   └── sentinelx_lb/
│       ├── proxy/
│       ├── algorithms/
│       ├── registry/
│       ├── health/
│       └── admin/
│
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
    ├── adr/
    ├── architecture/
    └── demo/
```

---

## 2. Folder Responsibilities

### `src/sentinelx_common`
Only cross-runtime shared code.

Allowed:
- Pydantic wire contracts;
- shared enums/IDs;
- config loader primitives;
- logging/correlation primitives.

Forbidden:
- ORM;
- repositories;
- detection business logic;
- Agent collector;
- LB selector logic.

### `src/sentinelx_controller`
Central control plane.

### `src/sentinelx_agent`
Linux node runtime.

### `src/sentinelx_lb`
HTTP reverse proxy/load balancer runtime.

### `dashboard`
React/Vite/TypeScript SPA.

### `tests`
- unit: isolated logic;
- integration: components with real boundaries where useful;
- e2e: full flow.

### `lab`
PBL-only simulation components:
- sample backends;
- traffic generator;
- attack simulator.

### `deploy`
Production-oriented deployment artifacts:
- Docker;
- systemd.

### `docs`
Human + AI architecture memory.

---

## 3. Package-by-feature rule

Controller modules are grouped by business capability, not global technical layers.

Preferred:

```text
modules/nodes/
modules/telemetry/
modules/detection/
```

Avoid a global structure like:

```text
controllers/
services/
repositories/
models/
```

for the entire application.

---

## 4. Module growth rule

Không tạo domain/application/infrastructure subfolder quá sớm nếu module chỉ có 1–2 files.

Khi module đủ lớn, refactor thành:

```text
module/
├── domain/
├── application/
├── infrastructure/
├── router.py
└── public.py
```

Giữ architecture rõ nhưng tránh ceremony.
