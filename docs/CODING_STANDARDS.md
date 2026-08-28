# SentinelX — Coding Standards

## 1. General

- Python 3.12.
- Type hints bắt buộc cho production code.
- Không `print()` trong service code; dùng structured logging.
- Không global mutable state nếu tránh được.
- Async cho I/O orchestration; không biến mọi function thành async vô lý.
- Code đơn giản hơn abstraction generic.

---

## 2. Formatting & Static Checks

Tools:
- Ruff
- mypy
- pytest

Target command:

```bash
make check
```

hoặc:

```bash
ruff check src tests
mypy src
pytest -q
```

---

## 3. Naming

Python:
- files/functions/variables: `snake_case`
- classes: `PascalCase`
- constants: `UPPER_SNAKE_CASE`

Events:
- past tense/event fact: `MetricReceived`

Commands:
- intent: `BlockIpCommand`

Repositories:
- interface/protocol: `NodeRepository`
- implementation: `PostgresNodeRepository`

---

## 4. Imports

Dependency direction phải rõ.

Không import bằng relative path xuyên module.

Không import `infrastructure` của module khác.

---

## 5. Pydantic

Pydantic dùng cho:
- API/wire contracts;
- settings;
- validation boundary.

Không dùng Pydantic BaseModel làm ORM replacement.

---

## 6. SQLAlchemy

ORM model là persistence detail.

Không expose ORM entity trực tiếp qua API.

Map:
```text
API Contract
 -> Application input
 -> Domain
 -> Repository
 -> ORM
```

Có thể đơn giản hóa mapping khi model còn nhỏ nhưng boundary phải được giữ.

---

## 7. Async Rules

- DB async I/O: async.
- HTTP client/server I/O: async.
- WebSocket: async.
- blocking collector: thread/executor nếu cần.
- CPU-heavy detection: không block event loop; phase sau có thể tách executor.

---

## 8. Error Handling

Không swallow exception.

Error phải:
- log có context;
- map thành API error phù hợp ở boundary;
- không leak secret/internal traceback cho client production.

---

## 9. Logging

Structured log fields khi có:
- timestamp
- level
- component
- correlation_id
- project_id
- node_id
- event_id
- action_id
- event_type
- result

Không log:
- token;
- password;
- raw credential.

---

## 10. Config

Thứ tự ưu tiên:

```text
safe defaults
 -> YAML
 -> environment variables
```

Secrets không nằm trong YAML commit.

---

## 11. Comments & Docstrings

Comment giải thích **why**, không lặp lại **what**.

Public interface/complex rule cần docstring.

Không comment dài để bù cho architecture tệ.

---

## 12. Scope Discipline

Khi task yêu cầu F3:
- không refactor F9;
- không add dashboard;
- không thêm firewall.

Mỗi commit/milestone phải có scope hẹp, test được.
