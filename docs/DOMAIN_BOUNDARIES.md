# SentinelX — Domain & Module Boundaries

## 1. Mục đích

File này ngăn AI/codebase tạo coupling giữa các module.

---

## 2. Controller Modules

### System
Trách nhiệm:
- health;
- version;
- readiness/liveness về sau.

Không chứa business logic.

### Projects
Trách nhiệm:
- project/infrastructure lifecycle;
- project identity.

### Nodes
Trách nhiệm:
- node registry;
- node identity;
- enrollment state;
- last_seen;
- online/offline derived status.

### Telemetry
Trách nhiệm:
- metric ingestion;
- validation;
- persistence;
- query;
- publish `MetricReceived` event.

### Detection
Trách nhiệm:
- consume metrics/network features;
- produce `DetectionEvent`.

Không:
- block IP;
- restart service;
- write firewall.

### Incidents
Trách nhiệm:
- group/track detection events;
- incident lifecycle;
- history.

### Policy
Trách nhiệm:
- map detection/incident context to authorized action intent;
- allow/deny action.

### Defense
Trách nhiệm:
- persist `DefenseAction`;
- dispatch command to Agent;
- record ACK/result;
- duplicate prevention.

### Recovery
Trách nhiệm:
- track unblock/re-add/recovery lifecycle;
- avoid recovery loops.

---

## 3. Agent Boundaries

Agent owns:
- local identity/credential;
- heartbeat;
- metric collection;
- network collection;
- buffering/retry;
- local command validation;
- nftables execution;
- local recovery executor.

Agent does not own:
- global policy decision;
- incident lifecycle;
- multi-node orchestration;
- DB schema.

---

## 4. Load Balancer Boundaries

LB owns:
- listener/proxy;
- backend registry cache;
- routing algorithm;
- active/in-flight counters;
- health check;
- backend health/routing state.

LB does not own:
- Detection policy;
- firewall policy;
- node Agent enrollment.

Adaptive selection from monitoring is Phase 2.

---

## 5. Dependency Rules

Allowed examples:

```text
telemetry.application
    -> telemetry.domain

telemetry.infrastructure
    -> telemetry.domain

detection.application
    -> detection.domain

controller API
    -> module public/application interface
```

Cross-module:

```text
Telemetry
    -> MetricReceived event
    -> Detection
```

or:

```text
Module A
    -> Module B public interface
```

Forbidden:

```text
Detection
    -> Telemetry PostgresRepository implementation

Policy
    -> Defense ORM table

Detection
    -> nftables executor
```

---

## 6. Contract vs Domain vs ORM

### Contract
Wire format between runtimes/API.

Example:
`MetricBatchRequest`

Location:
`sentinelx_common/contracts`

### Domain entity/value
Business model owned by one module.

Example:
`Node`, `DetectionEvent`

Location:
owning Controller module.

### ORM model
Persistence mapping only.

Location:
owning module/infrastructure/database area.

Agent must not import Controller ORM models.

---

## 7. Event naming

Events describe something that happened:

- `MetricReceived`
- `NetworkFeatureReceived`
- `DetectionCreated`
- `DefenseActionRequested`
- `DefenseActionApplied`
- `BackendHealthChanged`
- `RecoveryCompleted`

Commands describe intent:

- `BlockIp`
- `UnblockIp`
- `RestartService`

Không đặt command dưới dạng event nếu semantics là "hãy làm".
