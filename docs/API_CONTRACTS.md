# SentinelX — API & Wire Contract Conventions

> Đây là convention foundation. Endpoint/schema cụ thể được thêm theo milestone.

## 1. API Versioning

Controller REST API dùng prefix:

```text
/api/v1
```

System health:
```text
GET /api/v1/system/health
```

---

## 2. JSON Naming

Dùng `snake_case` nhất quán cho JSON giữa Python Agent và Controller.

Frontend TypeScript có thể map hoặc sử dụng schema-generated types về sau.

---

## 3. Time

Internally:
- UTC.

API:
- ISO 8601/RFC3339 timestamp.

Ví dụ:
```text
2026-08-28T02:30:00Z
```

Phân biệt khi cần:
- `observed_at`: thời điểm Agent quan sát;
- `received_at`: thời điểm Controller nhận.

---

## 4. IDs

Domain entities:
- UUID.

Examples:
- `project_id`
- `node_id`
- `agent_id`
- `event_id`
- `incident_id`
- `action_id`

Telemetry rows có thể dùng DB numeric key nội bộ nhưng external identity vẫn dựa trên domain IDs.

---

## 5. Correlation

HTTP request:
- `X-Correlation-ID`.

Pipeline events/actions phải carry correlation context khi phù hợp.

---

## 6. Error shape

Khi bắt đầu public API error contract, giữ shape nhất quán, ví dụ:

```json
{
  "error": {
    "code": "NODE_NOT_FOUND",
    "message": "Node does not exist",
    "correlation_id": "..."
  }
}
```

Không expose traceback nội bộ.

---

## 7. Telemetry batch principle

Không gửi mỗi metric bằng một HTTP request.

Target shape ở F3/F8:

```json
{
  "node_id": "...",
  "sequence": 10,
  "sent_at": "...",
  "metrics": [
    {
      "observed_at": "...",
      "cpu_pct": 42.5,
      "memory_pct": 61.2
    }
  ]
}
```

Schema cuối cùng được khóa khi triển khai F3.

### M1 resource semantics (02/11/2026)

The actual `/api/v1/telemetry/metrics` payload uses `samples` with
`observed_at`, `cpu_percent`, `memory_percent`, `disk_percent`,
`network_rx_bytes` and `network_tx_bytes` (see `MetricSample`).

- CPU is sampled over a bounded 100ms window inside the Agent worker, independent
  of thread-local psutil history. The configured interval is the wait between collections.
- Disk is nullable: unreadable/missing mounts produce `null`, never a fabricated `0%`.
- RX/TX are bytes between checks, not since boot, session totals or bytes/second.
  Missing network counters and the first observation after a gap produce `null`;
  the next observation uses the new baseline. Counter reset yields a nonnegative
  zero delta and rebases. A measured zero remains valid data.
- Preserve optional `null` through persistence, REST and WebSocket. No wire field
  is added/renamed. The ORM no longer replaces missing byte fields with client-side
  zero defaults; SQL columns already allow explicit NULL, so no migration is needed.
- Fleet network KPI sums the latest available deltas per online host; their
  timestamps and intervals may differ. This is not synchronized fleet throughput.
- Project/node/telemetry DB dependencies use function scope: commit/rollback
  finishes before a REST success response is sent. This prevents immediate
  create-project → create-node → issue-token requests from racing uncommitted data.
  Commit failure must return an error rather than a previously sent success.
  The minimum FastAPI requirement is 0.121.0; the locked version remains unchanged.

---

## 8. Agent command principle

Command tương lai phải có:
- `command_id`
- target node
- type
- issued timestamp
- expiry nếu cần
- payload validated
- acknowledgement/result

Không triển khai command firewall thật trong Foundation.
