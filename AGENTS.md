# SentinelX — AI Coding Instructions

## 1. Mục đích của file này

Đây là **entry point bắt buộc** cho mọi AI coding assistant làm việc với repository SentinelX.

Trước khi sửa hoặc sinh code, AI PHẢI đọc theo thứ tự:

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
11. `docs/DEFINITION_OF_DONE.md`
12. ADR liên quan trong `docs/adr/`

Không được code dựa trên suy đoán nếu các file trên đã quy định.

---

## 2. SentinelX là gì?

SentinelX là:

> Nền tảng quản trị, giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng Linux server/backend tập trung.

SentinelX KHÔNG phải:

- desktop Task Manager;
- website thông thường;
- SDK nhúng vào source code của website khách hàng;
- một IDS đơn lẻ;
- một load balancer đơn lẻ;
- hệ thống microservices enterprise.

Các runtime chính:

- `sentinelx_controller`: control plane trung tâm;
- `sentinelx_agent`: daemon/service chạy trên từng Linux node;
- `sentinelx_lb`: custom HTTP reverse proxy/load balancer;
- `dashboard`: Web Management Dashboard.

---

## 3. Quyết định kỹ thuật đã khóa

Không tự ý thay đổi các quyết định sau:

- Primary CORE language: **Python 3.12**
- Controller architecture: **Modular Monolith**
- Agent: **Python Linux background daemon/service**
- Controller: **FastAPI + asyncio**
- Frontend: **React + Vite + TypeScript**
- Agent → Controller: **REST/JSON, Push, Batched Telemetry**
- Controller → Dashboard: **REST + WebSocket**
- Database: **PostgreSQL**
- Network collection CORE: **Scapy/libpcap → aggregated NetworkFeature**
- Custom Load Balancer: **Python + aiohttp, HTTP reverse proxy**
- LB algorithms CORE: **Round Robin + Least In-Flight**
- Health check: **Active HTTP health check**
- Defense firewall: **nftables**
- Defense boundary: **Controller decides, Agent executes**
- PBL environment: **Docker + Docker Compose**
- Internal communication: **direct interfaces + bounded in-process async events**
- CORE không dùng Kafka/RabbitMQ/Redis broker
- CORE không dùng microservices
- CORE không dùng specialized TSDB
- CORE không dùng ML/eBPF/Adaptive LB trước khi baseline hoàn thành

Nếu cần thay đổi một quyết định đã khóa, phải:
1. dừng implementation;
2. giải thích lý do;
3. tạo ADR mới hoặc cập nhật ADR;
4. chờ con người phê duyệt.

---

## 4. Nguyên tắc phát triển

### 4.1 Làm theo milestone, không big-bang

Chỉ code milestone hiện tại trong `docs/FOUNDATION_ROADMAP.md`.

Không tự động triển khai milestone kế tiếp dù đã "tiện tay".

### 4.2 Foundation trước business logic

Trước `FOUNDATION FREEZE`, KHÔNG triển khai thật:

- CPU anomaly rules;
- Port Scan algorithm;
- SYN Flood algorithm;
- Isolation Forest;
- Adaptive Load Balancing;
- firewall blocking thật;
- self-healing restart thật;
- advanced traffic shaping;
- eBPF.

### 4.3 Không over-engineer

Không thêm:
- microservices;
- CQRS framework;
- Kafka;
- RabbitMQ;
- Redis Streams;
- service mesh;
- Kubernetes;
- TimescaleDB/InfluxDB;
- generic plugin framework;
- generic dependency injection container;

trừ khi có ADR được duyệt.

### 4.4 Không hard-code policy/rule

Không hard-code các giá trị như:
- CPU > 90;
- PORT_COUNT > 20;
- BLOCK = 60s.

Các rule/runtime tunables phải đi qua config khi đến đúng milestone.

### 4.5 Không phá module boundary

Controller là Modular Monolith package-by-feature.

Một module không được import trực tiếp:
- repository implementation;
- ORM internals;
- private service;
- database table;

của module khác.

Giao tiếp module qua:
- public interface;
- application service được expose;
- domain/application event khi phù hợp.

### 4.6 `sentinelx_common` không phải thùng rác

Chỉ đặt ở `sentinelx_common`:
- wire/API contracts;
- common IDs/enums;
- generic config utilities;
- observability primitives;
- truly shared utilities.

Không đặt:
- SQLAlchemy ORM model;
- Controller repository;
- Detection logic;
- Agent collector;
- LB algorithm.

---

## 5. Quy tắc output của AI khi coding

Mỗi lần được yêu cầu triển khai một bước, AI phải trả theo cấu trúc:

### A. Mục tiêu milestone
Nêu chính xác milestone đang làm và điều gì KHÔNG làm.

### B. Files thay đổi
Liệt kê:
- file tạo mới;
- file sửa;
- file không đụng tới.

### C. Code
Đưa code đầy đủ từng file hoặc patch rõ ràng.

### D. Giải thích kiến trúc
Giải thích ngắn:
- trách nhiệm file;
- dependency direction;
- vì sao đặt ở folder đó.

### E. Commands
Đưa lệnh:
- install/update dependencies nếu có;
- format;
- lint;
- type check;
- tests;
- run.

### F. Expected result
Nêu kết quả mong đợi.

### G. Checkpoint
Chỉ khi checkpoint PASS mới đề xuất bước tiếp theo.

---

## 6. Quality Gate bắt buộc

Trước khi coi một milestone hoàn thành:

```bash
ruff check src tests
mypy src
pytest -q
```

Tất cả phải PASS.

Nếu milestone có integration/docker:
- integration tests phải PASS;
- smoke test phải PASS;
- startup/shutdown phải sạch.

Không "fix" test bằng cách xóa assertion hợp lệ.

---

## 7. Security/Safety

Không bao giờ:
- chạy destructive firewall command mặc định;
- block localhost;
- block Controller IP;
- block management IP;
- block node's own IP;
- block whitelist/protected CIDR;
- chạy attack simulation ra Internet;
- yêu cầu Controller chạy root nếu không cần;
- nhúng secrets vào source code;
- commit `.env`.

Firewall/self-healing thật chỉ triển khai đúng milestone và phải có safe/no-op mode.

---

## 8. Nguyên tắc repository

Repository là monorepo.

Các runtime Python:
- `src/sentinelx_controller`
- `src/sentinelx_agent`
- `src/sentinelx_lb`

Shared:
- `src/sentinelx_common`

Frontend:
- `dashboard`

PBL lab:
- `lab`

Deployment artifacts:
- `deploy`

Architecture docs:
- `docs`

Tests:
- `tests/unit`
- `tests/integration`
- `tests/e2e`

---

## 9. Khi thiếu thông tin

Nếu chi tiết implementation chưa được khóa:
- chọn giải pháp đơn giản nhất phù hợp với architecture;
- không tự thay đổi tech stack;
- ghi assumption rõ ràng;
- nếu assumption ảnh hưởng architecture/public contract/database schema/security, hỏi con người trước khi code.

---

## 10. Mục tiêu cuối Foundation

Foundation hoàn thành khi có vertical slice:

```text
Mock Agent
   ↓
Controller
   ↓
Validation
   ↓
PostgreSQL
   ↓
REST query
   ↓
WebSocket realtime
   ↓
Dashboard
```

và:

```text
Client
   ↓
SentinelX LB
   ↓
Backend01/02/03
```

kèm basic health check, tests và Docker lab ổn định.

Sau đó mới bước vào business logic.
