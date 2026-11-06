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

Integration checkpoint 06/11/2026: each metric `observed_at` must include a
timezone (`Z` or an explicit offset), normalized to UTC; naive timestamps return
422. Each batch contains 1..1000 samples. Existing Agents already send UTC.

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

---

## 9. M2 network aggregate windows

| Endpoint | Contract |
|---|---|
| `POST /api/v1/telemetry/network-features` | `NetworkBatchRequest` -> `NetworkBatchResponse` |
| `GET /api/v1/telemetry/nodes/{node_id}/network-features` | `NetworkQueryResponse` |

Wire definitions: `sentinelx_common/contracts/network.py`. POST contains UUID
node_id/agent_id, sequence >=1, timezone-aware sent_at and 1..16 windows. Each
window has a stable UUID, UTC start/end (duration <=300s), interface, up to 1024
directional IP/protocol features, omitted_packets and skipped_windows. No raw
packet/payload/PCAP fields are allowed. Feature counters include IP bytes,
packets and TCP flag counts; bounded destination_ports has a truncation flag.

Only enrolled node credentials may ingest. `(node_id, window_id)` is idempotent:
retries return processed_count=0 for already stored windows and do not rebroadcast.
New windows broadcast `network_feature_update`, with node_id, received_at and
windows in data. This event is observation telemetry, not a detection/incident.
The HTTP ingest paths for M1 metric_update, M2 network_feature_update and M3
detection_alert now enqueue WebSocket delivery after the shared function-scoped
transaction commits. Failed persistence/commit returns an error and does not
broadcast these messages. Delivery is best effort, without a persistent outbox;
query REST history after a disconnect. HTTP success confirms durable DB state,
not delivery to every WebSocket subscriber.

GET accepts timezone-aware start_time/end_time (filter window_end), limit 1..100
(default 20); windows sort by window_end descending then window_id. Invalid UUID,
naive timestamps, reversed time range or invalid limits return 422; missing node
returns 404. Overlapping windows must not be summed as disjoint totals. An empty
valid window differs from capture being unavailable/stale. See
[M2_NETWORK_COLLECTION.md](M2_NETWORK_COLLECTION.md) for exact limits and privileges.

## 10. M3 resource detection integration (06/11/2026)

- `GET /api/v1/detection-events`: node_id, severity (`LOW`, `MEDIUM`, `HIGH`,
  `CRITICAL`), timezone-aware start_time/end_time, limit 1..100 (default 50),
  offset >=0. Reversed ranges, invalid UUID/severity or naive times return 422.
- Response `total` counts all matching rows before pagination; `items` sorts by
  detected_at descending then id. `GET /api/v1/detection-events/{event_id}` returns
  one event (404 when absent, 422 when UUID is invalid).
- `detection_alert` carries the persisted DetectionEventContract, including stable
  `id`, node_id, detector_name, severity, details and detected_at. REST/WS consumers
  deduplicate by event id. The dashboard restores the latest 50 events on initial
  load/reconnect; this is recent history, not a complete audit export.
- Each metric batch is sorted and evaluated sample by sample. Duplicate/late
  observed_at values do not progress detector state, although M1 metric storage
  itself still accepts duplicate rows. State, metric rows and new detection
  events commit atomically; per-node PostgreSQL row locks serialize evaluations.
- Default detection limits: 10 retained samples, 60s cooldown, 60s maximum gap,
  24h maximum sample age and 30s future skew. Samples outside the age/skew limits
  remain telemetry but do not affect detection; gaps reset consecutive counters.
  See [M2/M3 integration](M2_M3_INTEGRATION.md) for migration and configuration.
