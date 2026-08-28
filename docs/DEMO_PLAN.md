# SentinelX — PBL Demo Plan

## 1. Demo Environment Strategy

SentinelX có hai profile demo:

### Development / Fallback Profile
Docker Compose trên một máy.

Dùng cho:
- integration;
- repeatability;
- automated tests;
- fallback nếu network lab gặp sự cố.

### Final Network Profile
Multi-host qua LAN/IP network.

Khuyến nghị:

```text
Machine A
├── Controller
├── Dashboard
└── Load Balancer

Machine B
├── Backend01
└── Agent01

Machine C (recommended)
├── Backend02
└── Agent02
```

---

## Demo 1 — Multi-Host Monitoring

```text
Remote Node
   ↓
Agent
   ↓ LAN / HTTP
Controller
   ↓
PostgreSQL
   ↓ WebSocket
Dashboard
```

Show:
- node identity;
- CPU;
- RAM;
- load;
- RX/TX;
- connections;
- last_seen;
- online/offline.

Acceptance:
- remote Agent không chạy cùng máy Controller;
- không sửa source code để chuyển local → LAN.

---

## Demo 2 — CPU Overload

```text
Generate CPU load on remote Node
 -> Agent metric
 -> Controller
 -> Resource Detector
 -> DetectionEvent
 -> Alert/Incident
 -> Dashboard
```

Foundation chỉ chuẩn bị pipeline; real detector triển khai sau Foundation Freeze.

---

## Demo 3 — Backend Failure + LB Failover

```text
Client
  ↓
LB on Machine A
  ↓
Remote Backend B/C
```

Stop one backend:

```text
health check failures
 -> UNHEALTHY
 -> EJECTED
 -> traffic continues to healthy backend
```

Recovery:

```text
backend starts again
 -> successful probes
 -> RECOVERING
 -> HEALTHY
 -> ENABLED
```

---

## Demo 4 — Port Scan / SYN Simulation

```text
Attack Simulator
 -> Target Linux Node
 -> Network Collection
 -> NetworkFeature
 -> Detection
 -> Policy
 -> DefenseAction
 -> Agent
 -> nftables / safe executor
 -> Dashboard
```

Attack chỉ chạy trong controlled PBL lab/private network.

---

## Demo 5 — Recovery

IP:

```text
temporary block
 -> expiry/cooldown
 -> automatic unblock
 -> audit/recovery event
```

Backend:

```text
unhealthy
 -> recover
 -> health verification
 -> re-add
```

---

## Demo Reliability Rules

- có `demo-reset.sh`;
- không phụ thuộc Internet;
- có Docker fallback;
- có known-good config;
- remote IP/port configurable;
- defense có safe/no-op fallback;
- attack target chỉ private/controlled host;
- trước bảo vệ phải chạy full rehearsal ít nhất một lần trên topology multi-host.
