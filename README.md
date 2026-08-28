# SentinelX

> Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng máy chủ Linux/backend tập trung.

Dự án PBL4 — Hệ điều hành & Mạng máy tính.

---

## 1. Runtimes chính

- **`sentinelx_controller`**: Control plane trung tâm (FastAPI + asyncio, Modular Monolith).
- **`sentinelx_agent`**: Daemon/service chạy nền trên các Linux node quản lý (Python background service).
- **`sentinelx_lb`**: Custom HTTP reverse proxy / load balancer (Python + aiohttp).
- **`dashboard`**: Web Management Dashboard (React + Vite + TypeScript).

---

## 2. Quyết định kỹ thuật đã khóa (Locked Architecture)

- **Ngôn ngữ CORE**: Python 3.12 (Strict typing, async I/O, structured logging).
- **Controller**: Modular Monolith (Package-by-feature: `system`, `projects`, `nodes`, `telemetry`, `detection`, `incidents`, `policy`, `defense`, `recovery`).
- **Database**: PostgreSQL (SQLAlchemy 2.x, asyncpg, Alembic).
- **Giao tiếp Agent → Controller**: REST/JSON Push model, batched telemetry.
- **Giao tiếp Controller → Dashboard**: REST + WebSocket realtime.
- **Network Collection**: Scapy/libpcap → Aggregated `NetworkFeature` (không lưu raw PCAP đại trà).
- **Load Balancer**: Python + aiohttp HTTP Reverse Proxy (Round Robin + Least In-Flight, Active HTTP health check).
- **Firewall & Automated Defense**: nftables. Controller quyết định (policy/defense action) → Agent thực thi (local safety validation & execution).
- **PBL Environment**: Docker + Docker Compose.
- **Tooling & Quality Gate**: Ruff, mypy, pytest + pytest-asyncio.

---

## 3. Cấu trúc Monorepo

```text
sentinelx/
├── AGENTS.md               # Hướng dẫn bắt buộc cho AI coding assistants
├── README.md               # Giới thiệu dự án và quickstart
├── pyproject.toml          # Cấu hình dependencies, build, Ruff, mypy, pytest
├── compose.yaml            # Docker Compose setup cho lab & local test
├── Makefile                # Command shortcuts (make check, make test, etc.)
├── .gitignore
├── .env.example
├── .editorconfig
├── configs/                # Cấu hình runtime (YAML)
├── src/
│   ├── sentinelx_common/       # Shared wire contracts, config/logging primitives
│   ├── sentinelx_controller/   # Central control plane (Modular Monolith)
│   ├── sentinelx_agent/        # Linux node agent daemon
│   └── sentinelx_lb/           # Custom HTTP reverse proxy / load balancer
├── dashboard/              # React + Vite + TypeScript SPA
├── tests/                  # unit, integration, e2e tests
├── migrations/             # Alembic database migrations
├── lab/                    # PBL traffic/attack simulation lab
├── deploy/                 # Dockerfile & systemd artifacts
├── scripts/                # Utility & demo reset scripts
└── docs/                   # Toàn bộ tài liệu kiến trúc & ADRs
```

---

## 4. Lộ trình phát triển (Roadmap)

### Foundation Milestones
- **F0 — Architecture Freeze**
- **F1 — Repository Bootstrap**
- **F2 — Config + Logging + Controller Skeleton**
- **F3 — Shared Contracts + IDs + Time**
- **F4 — PostgreSQL Foundation**
- **F5 — Project + Node Registry**
- **F6 — Agent Enrollment**
- **F7 — Mock Agent + Heartbeat**
- **F8 — Fake Metrics Vertical Slice**
- **F9 — Realtime WebSocket**
- **F10 — Dashboard Skeleton**
- **F11 — Docker PBL Lab**
- **F12 — Load Balancer Skeleton**
- **F13 — Health Check**
- **F14 — Multi-Host Acceptance**
- **FOUNDATION FREEZE**

### Core Business Logic Milestones (Sau Foundation Freeze)
- **M1 — Real Resource Monitoring**
- **M2 — Network Collection + Aggregation**
- **M3 — Resource Detection**
- **M4 — Network Detection**
- **M5 — Incident + Policy**
- **M6 — Defense Command Pipeline**
- **M7 — nftables Executor**
- **M8 — Recovery / Cooldown**
- **CORE FREEZE**

---

## 5. Tài liệu chi tiết

Mời đọc các tài liệu tại thư mục [`docs/`](docs/):
- [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md)
- [`docs/PBL4_ALIGNMENT.md`](docs/PBL4_ALIGNMENT.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/TECH_STACK.md`](docs/TECH_STACK.md)
- [`docs/REPOSITORY_STRUCTURE.md`](docs/REPOSITORY_STRUCTURE.md)
- [`docs/DOMAIN_BOUNDARIES.md`](docs/DOMAIN_BOUNDARIES.md)
- [`docs/FOUNDATION_ROADMAP.md`](docs/FOUNDATION_ROADMAP.md)
- [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md)
- [`docs/TESTING_STRATEGY.md`](docs/TESTING_STRATEGY.md)
- [`docs/SECURITY_SAFETY.md`](docs/SECURITY_SAFETY.md)
- [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md)
- [`docs/DEFINITION_OF_DONE.md`](docs/DEFINITION_OF_DONE.md)
- [`docs/DEMO_PLAN.md`](docs/DEMO_PLAN.md)
- [`docs/DEV_SETUP.md`](docs/DEV_SETUP.md)
- [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md)
- [`docs/AI_WORKFLOW.md`](docs/AI_WORKFLOW.md)
- [`docs/adr/`](docs/adr/) (ADR 0001 -> 0006)
