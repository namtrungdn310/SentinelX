# SentinelX — PBL Demo Plan

## Demo 1 — Monitoring

```text
Backend01/02/03
 -> Agent
 -> Controller
 -> PostgreSQL
 -> WebSocket
 -> Dashboard
```

Show:
- CPU
- RAM
- RX/TX
- connections
- last_seen
- online/offline

---

## Demo 2 — CPU Overload

```text
CPU load
 -> metric
 -> Resource Detector
 -> DetectionEvent
 -> Incident/Alert
 -> Dashboard
```

Foundation chỉ chuẩn bị pipeline; detection thật sau Foundation Freeze.

---

## Demo 3 — Backend Failure

```text
stop backend02
 -> health check failures
 -> UNHEALTHY
 -> EJECTED
 -> traffic continues to 01/03
```

Recovery:

```text
start backend02
 -> health success threshold
 -> RECOVERING
 -> HEALTHY
 -> ENABLED
```

---

## Demo 4 — Port Scan / SYN Simulation

```text
Attack Simulator
 -> Network Collection
 -> NetworkFeature
 -> Detection
 -> Policy
 -> DefenseAction
 -> Agent
 -> nftables / safe executor
 -> Dashboard
```

Attack only isolated PBL lab.

---

## Demo 5 — Recovery

IP:
```text
temporary block
 -> expiry/cooldown
 -> unblock
 -> audit/recovery event
```

Backend:
```text
unhealthy
 -> recover
 -> re-add
```

---

## Demo Reliability Rules

- `demo-reset.sh`
- deterministic sample backends
- no dependency on Internet
- safe/noop defense fallback
- known-good config committed
- one command startup target by final phase
