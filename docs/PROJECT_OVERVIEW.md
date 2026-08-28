# SentinelX — Project Overview

## 1. Tên đề tài

**SentinelX — Nền tảng giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng máy chủ**

SentinelX là dự án PBL4 thuộc lĩnh vực **Hệ điều hành, Mạng máy tính và Lập trình mạng**.

Nhóm phát triển gồm **2 sinh viên**.

Mục tiêu của dự án là xây dựng một prototype end-to-end có khả năng hoạt động trên nhiều Linux node khác nhau, phản ánh được cách một nền tảng quản trị hạ tầng máy chủ thực tế được triển khai, nhưng vẫn giữ phạm vi phù hợp với một đồ án PBL4.

---

## 2. Product Definition

SentinelX là một nền tảng tập trung dùng để:

- onboard và quản lý các Linux node;
- thu thập telemetry từ các node;
- theo dõi trạng thái tài nguyên hệ thống;
- theo dõi process/service;
- thu thập network features;
- phát hiện bất thường tài nguyên;
- phát hiện một số bất thường hoặc tấn công mạng;
- tạo alert và incident;
- áp dụng policy;
- điều phối automated defense;
- hỗ trợ recovery/self-healing ở phạm vi phù hợp;
- phân phối traffic qua custom load balancer;
- theo dõi health của các backend;
- hiển thị trạng thái toàn bộ infrastructure qua Web Management Dashboard.

SentinelX Agent chạy độc lập trên hệ điều hành Linux và **không được nhúng vào source code của website, backend hoặc ứng dụng khách hàng**.

SentinelX không trực tiếp giám sát source code của ứng dụng.

Thay vào đó, hệ thống quan sát infrastructure nơi workload/service đang chạy thông qua:

- operating-system resources;
- process/service state;
- network activity;
- connection information;
- backend health.

---

## 3. Người dùng và khách hàng mục tiêu

### Primary User

Người dùng trực tiếp của SentinelX là:

- System Administrator;
- DevOps Engineer;
- Infrastructure Administrator;
- Developer/Owner tự quản lý Linux infrastructure.

Đây là những người chịu trách nhiệm vận hành và quản lý các server, VM hoặc service của một hệ thống.

SentinelX **không phải ứng dụng dành cho end-user** của website, mobile app hoặc desktop application.

Ví dụ:

```text
Customer
Công ty ABC
      |
      v
Primary SentinelX User
System Administrator / DevOps Engineer
      |
      v
SentinelX Dashboard
      |
      v
Customer Infrastructure
```

### Customer

Customer có thể là:

- cá nhân có VPS/server riêng;
- development team;
- startup;
- doanh nghiệp nhỏ;
- phòng lab;
- tổ chức có một số Linux server/VM cần quản lý.

Trong phạm vi PBL4, SentinelX không hướng tới enterprise-scale infrastructure.

---

## 4. Managed Infrastructure Scope

SentinelX CORE tập trung vào các **Linux infrastructure node** mà administrator có quyền quản trị và có khả năng cài SentinelX Agent.

Một Managed Node có thể là:

- Linux physical server;
- Linux Virtual Machine;
- Cloud VM;
- VPS;
- PC/laptop Linux đang được sử dụng như một server;
- Docker/container-based node dùng trong PBL lab.

Trên node có thể chạy:

- Web Backend;
- REST API;
- Reverse Proxy;
- Database Service;
- Worker;
- Cache Service;
- Network Service;
- System Service;
- hoặc workload/service khác cần được vận hành liên tục.

Ví dụ:

```text
Linux Node

├── Nginx
├── Customer Backend
├── Database / Worker / Service
└── SentinelX Agent
```

SentinelX không hướng tới việc giám sát máy tính cá nhân chỉ phục vụ các hoạt động end-user như:

- xem video;
- duyệt web;
- chơi game;
- sử dụng ứng dụng desktop thông thường.

Một PC/laptop chỉ nằm trong phạm vi SentinelX khi nó đang **đóng vai trò server/node** để chạy workload hoặc cung cấp service.

---

## 5. Các khái niệm chính

### Project / Infrastructure

Một nhóm logic đại diện cho infrastructure của một customer/system.

Một Project có thể chứa:

- nhiều Node;
- nhiều Agent;
- backend pools;
- monitoring data;
- incidents;
- policies;
- defense history;
- load-balancer configuration.

### Node

Một Linux server/VM/container được SentinelX quản lý.

Node đại diện cho một máy hoặc execution environment có identity riêng trong SentinelX.

Một Node không bắt buộc phải là backend của Load Balancer.

Ví dụ:

```text
Node A
└── Web Backend

Node B
└── Database

Node C
└── Worker
```

Cả ba vẫn có thể được SentinelX giám sát.

### Agent

SentinelX Agent là một daemon/service chạy trên từng managed Linux node.

Agent chịu trách nhiệm:

- node identity;
- enrollment/registration;
- heartbeat;
- resource telemetry collection;
- process/service observation;
- network feature collection;
- batching;
- gửi telemetry về Controller;
- reconnect/retry khi mất kết nối;
- nhận authorized command;
- local safety validation;
- command execution;
- action acknowledgement/result.

Agent không chịu trách nhiệm quyết định global policy.

### Controller

SentinelX Controller là **central control plane**.

Controller chịu trách nhiệm:

- project management;
- node registry;
- Agent enrollment;
- Agent authentication baseline;
- telemetry ingestion;
- network telemetry ingestion;
- validation;
- storage coordination;
- monitoring state;
- detection input;
- incident management;
- policy evaluation;
- defense coordination;
- recovery coordination;
- realtime API;
- Dashboard API;
- Load Balancer control information.

Controller sử dụng kiến trúc **Modular Monolith**.

### Load Balancer

SentinelX Load Balancer là một runtime/service riêng, đóng vai trò **custom HTTP reverse proxy** đứng trước backend pool.

CORE hỗ trợ:

- configurable backend pool;
- Round Robin;
- Least In-Flight;
- request forwarding;
- active/in-flight request tracking;
- active HTTP health checking;
- unhealthy backend detection;
- backend ejection;
- backend recovery;
- backend re-add.

Load Balancer không được hard-code cố định ba backend.

### Dashboard

Dashboard là Web Management UI dành cho administrator.

Các nhóm màn hình dự kiến:

- Infrastructure Overview;
- Projects;
- Nodes;
- Monitoring;
- Network;
- Alerts;
- Incidents;
- Load Balancer;
- Backend Health;
- Blocked IPs;
- Defense History;
- Whitelist;
- Settings.

Dashboard chỉ là **management interface**, không phải thành phần kỹ thuật trung tâm của SentinelX.

---

## 6. Real-World Deployment Target

Một hệ thống thực tế có thể có kiến trúc:

```text
                    Internet Users
                          |
                          v
                    Customer Domain
                          |
                          v
                SentinelX Load Balancer
                          |
              +-----------+-----------+
              |           |           |
              v           v           v
          Linux Node A Linux Node B Linux Node C
           Backend A    Backend B    Backend C
             Agent        Agent        Agent
              \            |            /
               \           |           /
                +----------+----------+
                           |
                           v
                 SentinelX Controller
                           |
                           v
                     PostgreSQL
                           |
                           v
                       Dashboard
                           ^
                           |
                   Administrator
```

SentinelX quản lý infrastructure phía server.

End-user có thể đang sử dụng:

- website;
- desktop application;
- Android application;
- iOS application;
- API client.

Tuy nhiên SentinelX không chạy trên các thiết bị end-user đó.

SentinelX Agent chạy trên Linux infrastructure nơi backend/service của hệ thống được vận hành.

---

## 7. Multi-Host Requirement

SentinelX phải được thiết kế để hoạt động trong môi trường **multi-host**.

Controller, Agent, Load Balancer và backend workloads có thể nằm trên:

- các physical machine khác nhau;
- các Virtual Machine khác nhau;
- các cloud instance khác nhau;

và giao tiếp thông qua:

- LAN;
- private IP network;
- hoặc Internet trong mô hình production-oriented.

Ví dụ:

```text
Machine A
192.168.1.10

├── SentinelX Controller
├── Dashboard
└── SentinelX Load Balancer

            |
            | LAN / IP Network
            |
      +-----+------+
      |            |
      v            v

Machine B        Machine C
192.168.1.20     192.168.1.30

Backend01        Backend02
Agent01          Agent02
```

Architecture không được giả định:

```text
Controller host == Agent host
```

hoặc:

```text
Load Balancer host == Backend host
```

hoặc:

```text
all components == localhost
```

Các địa chỉ mạng quan trọng phải configurable, bao gồm:

- Controller host/address;
- Controller port;
- Agent Controller URL;
- backend host;
- backend port;
- Load Balancer listen address;
- Load Balancer listen port.

`localhost` chỉ được sử dụng như development default khi phù hợp, không được trở thành architecture assumption.

---

## 8. Single-Server Case

SentinelX vẫn có giá trị khi customer chỉ có một Linux server/node.

Ví dụ:

```text
Linux Server

├── Backend
├── Nginx
└── SentinelX Agent
```

SentinelX vẫn có thể cung cấp:

- resource monitoring;
- process/service monitoring;
- network monitoring;
- resource anomaly detection;
- network anomaly detection;
- alerts;
- incidents;
- automated defense;
- service health;
- temporary network defense;
- một phần recovery.

Tuy nhiên:

> Load Balancer không có nhiều ý nghĩa khi chỉ có một backend instance.

Load Balancer phát huy đầy đủ giá trị khi infrastructure có từ hai backend instance trở lên.

---

## 9. PBL Development Environment

Docker được sử dụng chủ yếu để:

- development;
- integration testing;
- reproducible lab;
- backend simulation;
- traffic generation;
- attack simulation;
- fallback demo.

Ví dụ development lab:

```text
Developer Machine

├── SentinelX Controller
├── PostgreSQL
├── SentinelX Load Balancer
├── Backend01
├── Backend02
├── Backend03
├── Traffic Generator
├── Attack Simulator
└── Dashboard
```

Docker single-host deployment **không phải architectural limitation của SentinelX**.

Hệ thống phải có khả năng chuyển từ Docker/local development sang multi-host deployment mà không cần thay đổi business architecture hoặc hard-code lại source code.

---

## 10. Multi-Host PBL Demonstration

Ngoài Docker lab, project phải có khả năng chứng minh communication giữa nhiều máy khác nhau.

Topology tối thiểu:

```text
Machine A
├── Controller
├── Dashboard
└── Load Balancer

Machine B
├── Backend01
└── Agent01
```

Topology khuyến nghị:

```text
Machine A
├── Controller
├── Dashboard
└── Load Balancer

Machine B
├── Backend01
└── Agent01

Machine C
├── Backend02
└── Agent02
```

Multi-host demonstration phải chứng minh tối thiểu:

- Agent trên máy khác kết nối được tới Controller;
- Agent gửi heartbeat qua mạng;
- Agent gửi telemetry qua mạng;
- Dashboard hiển thị remote node;
- Load Balancer route được request tới backend trên remote host;
- backend failure/recovery có thể được phát hiện qua network health check;
- chuyển từ local development sang LAN không yêu cầu sửa source code.

---

## 11. PBL Demo Goals

### Demo 1 — Monitoring

```text
Linux Node
   ↓
Agent
   ↓
Controller
   ↓
Storage
   ↓
Dashboard
```

Hiển thị:

- CPU;
- RAM;
- load;
- network;
- connections;
- node status.

### Demo 2 — CPU Overload

```text
Generate CPU Load
        ↓
Agent Telemetry
        ↓
Controller
        ↓
Resource Detection
        ↓
Alert / Detection Event
        ↓
Dashboard
```

### Demo 3 — Backend Failure

```text
Stop Backend02
      ↓
Health Check Failure
      ↓
Backend UNHEALTHY
      ↓
EJECTED from Load Balancer
      ↓
Traffic continues through healthy backends
```

Sau recovery:

```text
Backend02 recovers
      ↓
Successful Health Checks
      ↓
RECOVERING
      ↓
HEALTHY
      ↓
RE-ADDED
```

### Demo 4 — Network Anomaly / Attack Simulation

```text
Attack Simulator
      ↓
Network Collection
      ↓
NetworkFeature
      ↓
Detection
      ↓
DetectionEvent
      ↓
Policy
      ↓
DefenseAction
      ↓
Agent
      ↓
Defense Executor
```

Attack simulation chỉ được thực hiện trong controlled PBL lab.

### Demo 5 — Recovery

```text
Temporary IP Block
      ↓
Expiration / Cooldown
      ↓
Automatic Unblock
```

và:

```text
Backend Failure
      ↓
Backend Recovery
      ↓
Health Verification
      ↓
Backend Re-add
```

---

## 12. PBL4 Technical Alignment

SentinelX tập trung vào ba nhóm kiến thức chính.

### Operating Systems

- Linux resource monitoring;
- process/service observation;
- memory/resource usage;
- concurrency;
- daemon/service execution;
- system-level interfaces;
- local firewall execution;
- process/service recovery concepts.

### Computer Networks

- IP addressing;
- ports;
- TCP connections;
- HTTP;
- network traffic;
- packet/flow features;
- health checking;
- reverse proxy;
- load balancing;
- network anomaly detection.

### Network Programming

- multi-host Agent ↔ Controller communication;
- REST/HTTP communication;
- WebSocket realtime channel;
- asynchronous network I/O;
- retry/reconnect;
- custom HTTP reverse proxy;
- concurrent requests;
- remote backend health checking;
- Agent command/result communication.

SentinelX phải thể hiện rõ các thành phần Hệ điều hành và Mạng máy tính trong implementation và demo, thay vì chỉ tập trung vào Web Dashboard.

---

## 13. CORE Scope

CORE ưu tiên một hệ thống end-to-end chạy ổn định.

Các thành phần trọng tâm:

- multi-host Agent–Controller communication;
- Linux resource monitoring;
- process/service health;
- network monitoring;
- centralized Controller;
- PostgreSQL storage;
- realtime Dashboard;
- custom HTTP Load Balancer;
- Round Robin;
- backend health checking;
- backend ejection/re-add;
- baseline resource detection;
- baseline network detection;
- alert/incident pipeline;
- policy boundary;
- một automated defense path;
- một recovery path.

---

## 14. Out of Scope / Phase 2

Các nội dung sau không thuộc CORE nếu baseline chưa hoàn thành:

- Isolation Forest;
- advanced Machine Learning;
- Adaptive Load Balancing;
- eBPF;
- advanced traffic shaping;
- advanced cgroups control;
- Kubernetes;
- Microservices;
- Kafka;
- RabbitMQ;
- specialized Time-Series Database;
- distributed Controller;
- Controller High Availability;
- enterprise RBAC;
- production-grade TLS/mTLS infrastructure;
- automatic horizontal scaling;
- complex self-healing orchestration.

Các nội dung này chỉ được nghiên cứu hoặc triển khai sau khi CORE hoạt động ổn định.

---

## 15. Nguyên tắc phạm vi

SentinelX ưu tiên:

- end-to-end functionality;
- Linux relevance;
- computer-network relevance;
- real network communication;
- multi-host capability;
- integration;
- observability;
- debugability;
- testability;
- deterministic demo;
- safety;
- maintainability;
- khả năng hoàn thành với nhóm 2 sinh viên.

SentinelX không ưu tiên:

- enterprise scale;
- distributed-system complexity;
- số lượng feature;
- UI complexity;
- technology novelty;
- architecture over-engineering.

Nguyên tắc chính:

> Một CORE nhỏ nhưng hoạt động end-to-end, có chiều sâu về Hệ điều hành và Mạng máy tính, có khả năng chạy trên nhiều máy và demo ổn định có giá trị cao hơn một hệ thống có nhiều feature nhưng không hoàn chỉnh.

---

## 16. Product Boundary Summary

SentinelX nên được hiểu theo mô hình:

```text
Customer Infrastructure
        |
        +-- Linux Node A
        |      ├── Workload/Service
        |      └── SentinelX Agent
        |
        +-- Linux Node B
        |      ├── Workload/Service
        |      └── SentinelX Agent
        |
        +-- Linux Node C
               ├── Workload/Service
               └── SentinelX Agent

                 ↓

        SentinelX Controller

                 ↓

        Management Dashboard

                 ↑

        System Administrator
```

SentinelX:

- quản lý **infrastructure**, không quản lý source code ứng dụng;
- phục vụ **administrator**, không phục vụ end-user;
- tập trung vào **Linux server/node**, không phải PC monitoring thông thường;
- hỗ trợ **multi-host deployment**, không bị giới hạn ở localhost/Docker;
- sử dụng Dashboard như management interface, không xem Dashboard là phần kỹ thuật trung tâm của đề tài.
