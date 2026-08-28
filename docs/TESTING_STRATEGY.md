# SentinelX — Testing Strategy

## 1. Test Pyramid

### Unit
Nhanh, isolated.

Dùng cho:
- config;
- validation;
- routing algorithm;
- state transitions;
- policy rules;
- aggregators.

### Integration
Kiểm tra boundary thật.

Dùng cho:
- FastAPI + PostgreSQL;
- Agent client + Controller;
- telemetry ingestion + storage;
- LB + sample backend.

### E2E / Smoke
Kiểm tra demo flow.

Dùng Docker Compose khi cần.

---

## 2. Directory

```text
tests/
├── unit/
│   ├── common/
│   ├── controller/
│   ├── agent/
│   └── load_balancer/
├── integration/
│   ├── controller/
│   ├── agent_controller/
│   └── load_balancer/
└── e2e/
```

---

## 3. Required Quality Gate

Mọi milestone:

```bash
ruff check src tests
mypy src
pytest -q
```

Milestone DB:
- migration test;
- DB integration test.

Milestone Docker/LB:
- smoke test.

---

## 4. Determinism

Tests không phụ thuộc:
- Internet;
- public services;
- random timing không kiểm soát;
- real external targets.

Attack simulation chỉ chạy isolated lab.

---

## 5. Time-sensitive tests

Dùng:
- injectable clock khi business logic thời gian phức tạp;
- timeout hợp lý;
- tránh `sleep()` dài.

---

## 6. Foundation Required Tests

F2:
- config load;
- env override;
- health endpoint;
- correlation ID.

F3:
- contract validation.

F4:
- migration;
- DB lifecycle.

F6:
- enrollment valid/invalid/reuse.

F7:
- heartbeat;
- last_seen.

F8:
- metric validation;
- batch persistence;
- query.

F9:
- WebSocket event.

F12:
- round robin;
- proxy response.

F13:
- failure threshold;
- ejection;
- recovery threshold;
- re-add.

---

## 7. Demo regression tests

Trước demo:
1. clean state;
2. start stack;
3. verify health;
4. run monitoring flow;
5. LB routing;
6. backend fail/recover;
7. reset stack.

`demo-reset.sh` phải tồn tại trước final demo.
