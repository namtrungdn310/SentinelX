# Tích hợp M2 với M3 — 06/11/2026

## 1. Milestone và mục tiêu

Đưa M2 Network Collection đang ở commit local `4f499ee` vào `dev` đã có M3
Resource Detection (`b9e3f72`, PR #15), sửa lỗi tương tác từ M1 đến M3 và giữ nguyên
lịch sử migration đã có. Nhánh thực hiện: `fix/m2-m3-integration`.

## 2. Scope

Trong phạm vi: ghép router, migration, capture/aggregation M2, phát hiện tài nguyên
M3 trên batch M1, transaction/retry/concurrency, phục hồi cảnh báo trên dashboard
và kiểm thử tích hợp. Giữ kiến trúc modular monolith và cấu hình multi-host.

Ngoài phạm vi: M4 network detector, incident/policy, nftables, recovery, network
dashboard mới, account/auth mới, publish bundle tự động hoặc thay giao diện.

## 3. Repository inspection và lỗi được sửa

| Điểm kiểm tra | Trước tích hợp | Sau sửa |
|---|---|---|
| API router | M2 thêm network router, M3 thêm detection router tại cùng vị trí | Giữ cả hai router |
| Alembic | M2/M3 cùng parent 0003, tạo hai head | Merge 0005 nối hai nhánh, 0006 là head duy nhất |
| Batch M1 | Chỉ đánh giá sau khi thêm cả batch, bỏ lỡ quá tải ở đầu batch | Sắp xếp thời gian, đánh giá sau từng mẫu |
| Retry | Cùng một mẫu gửi lại có thể thành 3 mẫu liên tiếp | observed_at <= watermark không tiến detector |
| DB transaction | Detection và metric có thể dùng hai session/scope khác nhau | Cùng function-scoped session và một commit |
| Cooldown | Cập nhật RAM trước khi DB commit, lỗi lưu có thể làm mất alert khi retry | State/cooldown lưu cùng transaction với metric/event |
| Đồng thời/restart | Cache process mất khi restart và không chia sẻ worker | State PostgreSQL theo node, SELECT FOR UPDATE |
| Timestamp | Mẫu thiếu timezone/gap dài có thể sai phép tính hoặc nối chuỗi giả | UTC bắt buộc, giới hạn age/skew/gap |
| REST detection | total bằng số dòng trong trang | Count theo filter trước limit/offset |
| WebSocket | Có thể phát trước commit, client nhìn thấy dữ liệu chưa lưu | HTTP ingest queue message sau commit |
| Dashboard | Không hiểu detection_alert, reload mất lịch sử cảnh báo | Render severity/nội dung, hydrate REST, dedup theo event id |

## 4. File chính

| File | Trách nhiệm |
|---|---|
| `src/sentinelx_agent/network/aggregation.py` | Counters và sliding windows có giới hạn bộ nhớ |
| `src/sentinelx_agent/network/capture.py` | Scapy/libpcap adapter, metadata thay raw PCAP |
| `src/sentinelx_agent/network/runtime.py` | Capture supervisor, bounded queue, retry độc lập M1 |
| `src/sentinelx_controller/api/v1/router.py` | Mount đủ network và detection endpoints |
| `migrations/versions/0005_merge_m2_m3.py` | Nối hai revision cũ, không đổi ID/parent đã phát hành |
| `migrations/versions/0006_detection_state.py` | State bounded theo node, FK cascade |
| `src/sentinelx_common/contracts/telemetry.py` | AwareDatetime/UTC, batch tối đa 1000 mẫu |
| `src/sentinelx_controller/config.py` | DetectionSettings và validation giới hạn |
| `src/sentinelx_controller/modules/detection/engine.py` | Đánh giá tuần tự, replay/gap/age, pure state transition |
| `src/sentinelx_controller/modules/detection/repository.py` | Lock state, save events, query/count |
| `src/sentinelx_controller/modules/detection/service.py` | Điều phối một transaction, không process-global cooldown |
| `src/sentinelx_controller/modules/detection/router.py` | Shared session scope, severity/time validation |
| `src/sentinelx_controller/modules/telemetry/service.py` | Metric insert và detection cùng thành công/thất bại |
| `src/sentinelx_controller/modules/telemetry/network_service.py` | Idempotent network windows và queue WS sau commit |
| `src/sentinelx_controller/infrastructure/realtime/publisher.py` | Best-effort publish sau commit, lỗi WS không đảo DB đã commit |
| `dashboard/src/api.ts`, `events.ts`, `useInfrastructure.ts` | Tải lịch sử, kết hợp REST/WS, chống trùng |
| `dashboard/src/components/LiveEventStream.tsx` | Cảnh báo có text severity, tài nguyên và ngưỡng |
| `tests/unit/controller/detection/test_detection_regressions.py` | Batch/replay/gap/timestamp/pure state |
| `tests/integration/controller/test_detection_api.py` | Atomic rollback, commit trước HTTP 200, pagination |
| `tests/e2e/test_m3_live.py` | Concurrent requests và WS/REST trên PostgreSQL thật |
| `tests/e2e/test_m123_migrations.py` | Upgrade DB rỗng hoặc M2/M3 cũ, giữ dữ liệu |
| `deploy/m123/compose.acceptance.yaml` | Lab M1–M3 riêng, không mở host port |

## 5. Luồng chạy sau tích hợp

```text
Linux Agent
  ├─ M1: psutil -> MetricSample UTC -> batch REST
  │    -> NodeService xác minh identity
  │    -> insert metric rows
  │    -> DetectionService lock detection_node_state của node
  │       -> engine evaluate_state (không sửa cache dùng chung)
  │       -> insert DetectionEvent và cập nhật state/cooldown
  │    -> commit duy nhất
  │    -> HTTP 200; background task phát metric_update + detection_alert
  │
  └─ M2 opt-in: libpcap -> metadata -> sliding windows -> batch REST
       -> xác minh identity -> insert windows theo stable window_id
       -> commit -> HTTP 200; background task phát network_feature_update

Dashboard -> REST recent detection history + WebSocket live
          -> merge theo stable event id -> nhật ký/cảnh báo
```

Telemetry chỉ gọi public DetectionService; không truy cập repository/ORM của
detection. Agent chỉ dùng shared contracts, không import ORM Controller.
Network features vẫn là dữ liệu quan sát, không tự chạy network detection M4.

## 6. Semantics và cấu hình cần hiểu

### Detection trên metric M1

- CPU: HIGH >=80%, CRITICAL >=95%, 3 mẫu liên tiếp.
- RAM: HIGH >=85%, CRITICAL >=95%, 3 mẫu liên tiếp.
- Disk: HIGH >=85%, CRITICAL >=95%, 1 mẫu hợp lệ; null không giả thành 0.
- Giữ ngưỡng detector M3 đã có; ngưỡng attention tức thời của dashboard (CPU 75%)
  là chỉ báo giao diện khác với sustained CPU detector 80%, không đồng nhất hai loại.
- Ví dụ batch CPU `[98,98,98,20,20]` tạo cảnh báo ở mẫu thứ ba. Việc hai mẫu cuối
  hạ xuống không xóa sự kiện đã xảy ra trước đó trong batch.
- Sắp xếp mỗi batch theo observed_at; mỗi node giữ watermark từ mẫu cuối đã nhận
  vào detector. Mẫu trùng hoặc cũ hơn watermark không tính lại. Timestamp trùng
  nhưng giá trị khác cũng không thay thế giá trị đã nhận trước.
- Metric storage M1 vẫn có thể chứa duplicate rows do retry. Bản sửa bảo đảm
  retry không tạo sai chuỗi detection/cooldown, không tuyên bố exactly-once M1.
- Request cùng node được serialize bằng row lock PostgreSQL. Hai batch khác nhau
  đến ngược thứ tự: mẫu <= watermark bị bỏ khỏi detection dù vẫn lưu telemetry;
  không có reorder buffer xuyên request trong scope này.
- Failure lúc save/commit rollback metric, events, state và cooldown. Agent retry
  được đánh giá lại; không có cooldown ở RAM che mất event chưa commit.
- State bounded theo window_size và số detector; xóa node cascade state. Restart
  Controller không làm mất watermark/cooldown đã commit. SQLite unit tests không
  chứng minh concurrency; ca live dùng PostgreSQL riêng.

Mặc định trong `configs/controller.yaml`:

```yaml
detection:
  window_size: 10
  cooldown_seconds: 60
  max_gap_seconds: 60
  max_sample_age_seconds: 86400
  future_skew_seconds: 30
```

Có thể override qua `SENTINELX_DETECTION__MAX_GAP_SECONDS` và các khóa tương tự.
Nếu interval Agent lớn hơn 60s, tăng max_gap phù hợp; nếu không, CPU/RAM sẽ không
đạt ba mẫu liên tiếp. Gap quá lớn reset chuỗi mẫu, không reset cooldown đã commit.
Mẫu cũ hơn 24h hoặc tương lai quá 30s vẫn lưu telemetry nhưng không tiến detector.
Cooldown tính theo detected_at của event (timestamp mẫu kích hoạt), chỉ tiến với
mẫu mới đã được chấp nhận; nâng severity lên CRITICAL có thể phát ngay trước khi
hết cooldown. Replay bị chặn bởi watermark trước khi tới bước cooldown.

**Thay đổi validation:** MetricSample.observed_at phải có timezone (`Z` hoặc
`+07:00`...). Offset được đổi UTC; timestamp naive trả HTTP 422. Agent hiện tại
đã gửi UTC, client tự viết cần cập nhật. Batch tối đa 1000 samples.

### WebSocket và dashboard

Các HTTP ingest M1/M2/M3 chỉ queue event để phát sau commit. Lỗi broadcast sau
commit được log; không biến request đã lưu thành 500 gây retry giả.
Đây không phải durable outbox: crash sau commit có thể làm mất live message.
Dashboard fetch 50 detection events gần nhất khi load/reconnect và merge theo
event id; không thay thế phân trang lịch sử đầy đủ. Metric/network có REST query
riêng. Network messages chưa đưa vào resource event stream để tránh ngập nhật ký.

## 7. Migration và lệnh chạy

```text
0003_f8_telemetry_metric_samples
  ├─ 0004_m2_network_windows ─┐
  └─ 0004_m3_detection_events┤
                            └─ 0005_merge_m2_m3 -> 0006_detection_state (head)
```

Từ DB mới, DB M1, DB M2 cũ hoặc DB M3 cũ, dùng cùng lệnh sau trước khi khởi động
Controller mới. Không sửa alembic_version bằng tay, không stamp head thay migration.

```bash
uv sync --all-extras --frozen
uv run alembic heads
uv run alembic upgrade head
uv run alembic current
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
```

Head mong đợi: `0006_detection_state`. Hai revision 0004 giữ nguyên parent 0003;
merge revision chỉ nối graph. 0006 tạo bảng mới; dữ liệu M1/M2/M3 giữ nguyên.
State mới bắt đầu rỗng khi upgrade; cache RAM/cooldown trước upgrade không thể
khôi phục từ database cũ. Tính bền vững và chống replay áp dụng từ lần ingest
đầu tiên sau upgrade. Khi rollout, dừng/restart tất cả worker cũ để không trộn
evaluator dùng RAM với evaluator dùng DB.
Downgrade 0006 về 0005 xóa state/cooldown; không dùng downgrade như một cách
restart thông thường. Downgrade xa hơn có thể xóa bảng milestone tương ứng.

Dashboard:

```bash
cd dashboard
npm run lint
npm run build
npm run test:ui
```

Lab tự động (DB giả, không dùng deployment thật):

```bash
docker compose -p sentinelx-m123-integration -f deploy/m123/compose.acceptance.yaml up --build --abort-on-container-exit --exit-code-from agent-check
docker compose -p sentinelx-m123-integration -f deploy/m123/compose.acceptance.yaml down --volumes
```

Lab chạy 2 ca M1, 2 ca M2, 1 ca M3 và 3 đường migration. Test migration chỉ bật
khi có `SENTINELX_MIGRATION_TEST_URL`; nó tạo/xóa database UUID riêng trên server
QA. Không trỏ biến đó vào PostgreSQL đang sử dụng. `PGSSLMODE=disable` chỉ có
trong Compose lab vì PostgreSQL nội bộ lab không TLS, không đổi cấu hình production.

## 8. Expected result

Agent M1 tiếp tục heartbeat và gửi metric khi capture M2 lỗi. M2 trả processed_count
chỉ cho window mới, retry không tạo duplicate. M3 bắt overload ở mọi vị trí batch,
retry không tăng consecutive count, event lưu/query ngay sau HTTP success và
hiển thị trong event stream. DB upgrade có một head và giữ bản ghi cũ.

## 9. Troubleshooting

- `Multiple head revisions`: kiểm tra checkout có 0005/0006, chạy đúng phiên bản
  repository và `alembic heads`; không sửa parent hai migration cũ.
- `relation detection_node_state does not exist`: chưa chạy upgrade bằng DB URL
  thực của Controller. Dừng Controller cũ rồi migration và restart Controller mới.
- HTTP 422 timestamp: gửi ISO8601 có timezone; đừng bỏ phần `Z`/offset.
- Không có alert: kiểm tra ngưỡng, ba mẫu unique, khoảng gap, timestamp quá cũ/
  tương lai và cooldown. M2 network packets không kích hoạt detector tài nguyên.
- Không thấy WS nhưng REST có event: kết nối lại và tải history; live delivery
  best effort. Kiểm tra log realtime delivery failure và reverse proxy WS.
- Capture thiếu quyền/libpcap: xem AGENT_INSTALLATION; M2 opt-in chỉ NET_RAW,
  không thêm NET_ADMIN/privileged và không thay firewall.

## 10. Checkpoint

| Kiểm tra ngày 06/11/2026 | Kết quả |
|---|---|
| Ruff src/tests | PASS, 0 errors/warnings |
| Strict mypy src/tests | PASS, 149 source/test files |
| Full pytest Windows Python 3.12.10 | 224 passed, 8 opt-in live cases skipped |
| Full pytest Linux Python 3.12.15 | 224 passed, 8 opt-in live cases skipped |
| Combined M1/M2/M3 live, PostgreSQL 16 | 8 passed, không skip |
| DB mới / DB chỉ có M2 / DB chỉ có M3 | Upgrade head + giữ bản ghi cũ + downgrade 0006/upgrade PASS |
| Concurrent identical retry + immediate REST + WebSocket | PASS trên PostgreSQL thật |
| Simulated save/commit failure | PASS: rollback cả metric/event/state, không broadcast; retry thành công |
| Dashboard lint / production build / render checks | PASS, 27 checks |
| Alembic graph | Một head: 0006_detection_state |

Full suite còn 3 deprecation warnings Starlette có sẵn (httpx TestClient và hai
alias status 422); không có Ruff/mypy warning. Live tests opt-in được chạy riêng,
không tính skip thành pass. Chưa chạy nghiệm thu hai máy Linux/LAN hoặc benchmark
lưu lượng cao trong lượt tích hợp này. Native systemd M2 đã có bằng chứng ở
checkpoint 04/11, không gọi đó là kiểm thử mới ngày 06/11.

Checkpoint M2 ngày 04/11/2026 trong M2_NETWORK_COLLECTION giữ nguyên như bằng
chứng lịch sử. Push/merge được xác nhận bằng PR trên GitHub; tài liệu không tự
tuyên bố đã merge trước khi có kết quả từ remote.

## 11. Stop

Chỉ hoàn tất tích hợp M2 với M3 đã có. Không triển khai M4 trở đi. Việc merge
thực hiện qua PR vào dev; không commit trực tiếp dev/main hoặc đổi branch protection.
