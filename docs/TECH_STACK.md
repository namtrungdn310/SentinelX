# SentinelX — Locked Tech Stack

## 1. Core Stack

| Area | Decision |
|---|---|
| Primary CORE language | Python 3.12 |
| Controller architecture | Modular Monolith |
| Agent | Python Linux daemon/service |
| Controller | FastAPI + asyncio |
| Validation/contracts | Pydantic |
| ORM | SQLAlchemy 2.x |
| PostgreSQL async driver | asyncpg |
| DB migrations | Alembic |
| Frontend | React + Vite + TypeScript |
| Agent → Controller | REST/JSON Push |
| Telemetry transport | Batched |
| Controller → Dashboard | REST + WebSocket |
| Database | PostgreSQL |
| Resource monitoring | psutil + `/proc`, `/sys` when needed |
| Network collection | Scapy/libpcap |
| Network persistence model | aggregated NetworkFeature, not raw PCAP |
| Custom LB | Python + aiohttp |
| LB type | HTTP Reverse Proxy |
| CORE algorithms | Round Robin + Least In-Flight |
| Health checking | Active HTTP health check |
| Firewall | nftables |
| PBL environment | Docker + Docker Compose |
| Python tests | pytest + pytest-asyncio |
| Lint/format | Ruff |
| Type checking | mypy |
| Version control | Git + GitHub |
| Package & Environment Manager | **`uv`** (`uv.lock`, `uv run`, `uv sync`) |

---

## 2. Technology explicitly NOT in CORE

Không thêm nếu chưa có ADR:

- Next.js
- Microservices
- Kafka
- RabbitMQ
- Redis Streams
- Kubernetes
- TimescaleDB
- InfluxDB
- eBPF
- Isolation Forest
- Adaptive Load Balancer
- generic TCP proxy
- production TLS termination
- enterprise RBAC/HA

---

## 3. Frontend Decision

Dashboard là authenticated admin SPA.

CORE dùng:

```text
React + Vite + TypeScript
```

Không cần Next.js/SSR/SEO.

---

## 4. Database Decision

CORE dùng **PostgreSQL**.

Không khóa vào Supabase.

Supabase có thể là một hosting/deployment option sau này nhưng không phải architectural dependency của SentinelX CORE.

---

## 5. Network Decision

CORE:
```text
packet observation
    ↓
window aggregation
    ↓
NetworkFeature
    ↓
Controller
```

Không lưu toàn bộ raw packet/PCAP vào DB.

---

## 6. Load Balancer Decision

CORE dùng HTTP reverse proxy vì:
- request tracking rõ;
- active/in-flight tracking dễ;
- health check dễ;
- latency measurement dễ;
- demo rõ;
- phù hợp Adaptive LB phase 2.

---

## 7. Agent Concurrency

Không khóa toàn Agent vào "threading".

Agent là background daemon/service.

Concurrency model có thể kết hợp:
- asyncio cho I/O orchestration;
- thread cho blocking collector khi thực sự cần.

Chi tiết quyết định ở Agent implementation milestone.
