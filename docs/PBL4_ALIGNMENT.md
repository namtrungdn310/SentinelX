# SentinelX — PBL4 Alignment

## 1. Mục đích

File này ghi rõ cách SentinelX bám sát phạm vi PBL4 **Hệ điều hành & Mạng máy tính**, đồng thời ngăn project trượt thành một web dashboard thông thường hoặc một hệ thống chỉ chạy local.

---

## 2. PBL4 Knowledge Alignment

SentinelX phải thể hiện kiến thức thuộc ba trục chính:

### Hệ điều hành

SentinelX áp dụng:

- Linux resource monitoring;
- quản lý/truy cập thông tin CPU, memory và I/O;
- process/service observation;
- daemon/service execution;
- concurrency;
- asynchronous processing;
- system-level interfaces;
- privilege/capability considerations;
- local firewall execution;
- recovery/service-management concepts.

### Mạng máy tính

SentinelX áp dụng:

- IP addressing;
- port;
- TCP connection;
- HTTP;
- network traffic;
- network feature aggregation;
- remote health check;
- reverse proxy;
- load balancing;
- connection/request tracking;
- network anomaly detection.

### Lập trình mạng

SentinelX áp dụng:

- chương trình chạy trên nhiều host;
- Agent ↔ Controller communication;
- HTTP REST;
- WebSocket realtime;
- retry/reconnect;
- timeout;
- concurrent network I/O;
- custom HTTP reverse proxy;
- remote backend communication;
- Agent command/result communication.

---

## 3. Required Multi-Host Property

SentinelX phải có khả năng triển khai:

```text
Machine A
Controller + Dashboard + Load Balancer

        |
        | LAN / IP network
        |

Machine B
Backend + Agent
```

và có thể mở rộng:

```text
Machine C
Backend + Agent
```

Controller, Agent và backend không được bắt buộc chạy trên cùng một máy.

Docker single-host chỉ là:
- development environment;
- integration lab;
- reproducible fallback.

Docker không phải architectural limitation.

---

## 4. PBL Demonstration Requirement

Final demonstration nên chứng minh tối thiểu:

1. Remote Agent kết nối Controller qua LAN.
2. Heartbeat/telemetry truyền giữa hai máy.
3. Dashboard hiển thị node remote.
4. Load Balancer route request qua network tới remote backend.
5. Health check phát hiện remote backend failure.
6. Backend recovery được phát hiện và re-add.
7. OS/network business logic được thể hiện rõ, không chỉ UI.

---

## 5. Scope Guardrail

SentinelX không được biến thành:

- CRUD dashboard project;
- PC monitoring app cho người dùng cuối;
- single-machine Task Manager;
- Docker-only simulation không chứng minh network communication;
- AI/ML project;
- Kubernetes/Microservices project.

Dashboard và PostgreSQL là thành phần hỗ trợ.

Phần technical trọng tâm phải nằm ở:

```text
Linux Agent
+
OS Resource/Service Monitoring
+
Network Communication
+
Network Collection
+
Custom Load Balancer
+
Detection
+
Defense/Recovery
```

---

## 6. Primary PBL User

Primary user:

> **System Administrator / DevOps Engineer / Infrastructure Administrator**

User dùng SentinelX để quản lý các Linux server/VM thuộc infrastructure mà họ có quyền quản trị.

SentinelX không trực tiếp phục vụ end-user của website/mobile/desktop application.

---

## 7. Completion Philosophy

Đối với nhóm 2 sinh viên:

> Một hệ thống nhỏ nhưng chạy end-to-end, multi-host, có chiều sâu OS/network và demo chắc chắn quan trọng hơn nhiều feature nhưng không hoàn chỉnh.

CORE phải được hoàn thành trước Phase 2.
