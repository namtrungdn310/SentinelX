# Bàn giao nâng cấp lõi M1–M8

Ngày thực hiện: 13/11/2026. Nhánh: `fix/core-m1-m8-hardening`, từ `dev` tại
`1b67632`. Đây là đợt sửa độ tin cậy và an toàn của CORE đã có, không mở M9.
Không thay đổi giao diện. Không thêm Redis, broker, microservice hoặc thư viện runtime.

## 1. Milestone

Hoàn thiện đường đi: Agent → resource/network telemetry → detection → incident →
policy → command delivery → nftables → recovery. Sửa cả trường hợp lỗi, retry,
restart và rollback; không chỉ đường chạy thành công.

## 2. Scope

Đã triển khai: hợp đồng lệnh, ACK xác thực, lease, journal bền vững, deadline,
cooldown trong transaction, policy audit, nftables có enforcement thật, recovery
có ownership, kiểm tra thời gian/chiều lưu lượng, tương quan incident và retention.

Ngoài phạm vi: thiết kế UI, tài khoản/tenant/RBAC của M9, triển khai production,
benchmark tải lớn và nghiệm thu LAN/VPS nhiều máy vật lý. Các operator API vẫn
thuộc mô hình CORE trên mạng quản trị tin cậy; không coi đây là SaaS công khai hoàn chỉnh.

## 3. Repository inspection

Các module hiện hữu được giữ nguyên kiến trúc modular monolith. Lỗi chính trước sửa:

| Vấn đề | Hậu quả trước sửa | Hành vi sau sửa |
|---|---|---|
| PENDING → SENT một chiều | Mất response heartbeat có thể làm mất lệnh | Lease hết hạn cho phép giao lại, giới hạn attempts/deadline |
| Không có receipt bền vững | Restart có thể thực thi lại lệnh đã xong | SQLite journal giữ payload hash, deadline, kết quả và ACK chờ gửi |
| ACK thiếu identity/fencing | Nhận ACK sai node, sai action hoặc sai vòng đời | Kiểm tra agent/node, path/body ID, delivery token, timestamp và terminal transition |
| Simulated/noop thành APPLIED | Giao diện/lifecycle tưởng đã bảo vệ thật | SIMULATED/SKIPPED tách biệt; APPLIED yêu cầu kết quả executor thật |
| Cooldown trong RAM | Rollback vẫn mất lượt; nhiều worker không thống nhất | Row lock PostgreSQL, cập nhật cùng transaction, key theo node/policy/target |
| Duration dùng hai tên | Block và recovery không cùng deadline | Chuẩn hóa `duration_seconds`; alias cũ chỉ nhận nếu không mâu thuẫn |
| Recovery dựa thời điểm tạo | Gỡ quá sớm khi lệnh được giao muộn | Tính từ thời điểm thực thi, absolute `effective_until` |
| Chỉ tạo set nftables | Có trạng thái nhưng chưa chặn traffic | Xác minh base chain, hook, priority, timeout sets và hai drop rule |
| Không kiểm tra owner | Unblock cũ có thể gỡ block mới | Comment chứa action UUID; recovery chỉ gỡ đúng owner |
| Network không có watermark/rate | Replay, future timestamp, thời lượng cửa sổ làm sai detection | Age/skew/order checks, per-interface cursor, chuẩn hóa rate |
| Incident gộp theo project | Trộn node/attacker, severity không đúng | Correlation theo node + resource hoặc attacker; lấy mức nặng nhất |
| Lịch sử tăng không giới hạn | DB/journal/state phình dần | Maintenance theo batch, TTL/bounds cho state và journal |

## 4. Files to create/modify

| File/nhóm file | Action | Responsibility |
|---|---|---|
| `src/sentinelx_common/contracts/command_parameters.py` | Mới | Canonical IP/action/duration và giới hạn |
| `src/sentinelx_common/contracts/{agents,defense,network,nodes,policy,recovery}.py` | Sửa | Wire contract, capabilities và trạng thái thật |
| `src/sentinelx_agent/defense/journal.py` | Mới | Receipt/dedup/ACK retry qua restart |
| `src/sentinelx_agent/defense/{processor,validator}.py` | Sửa | Worker độc lập, local safety, reconciliation |
| `src/sentinelx_agent/defense/executors/nftables.py` | Sửa | Kiểm tra schema/owner/kernel và absolute TTL |
| `src/sentinelx_agent/{config,daemon}.py`, `network/` | Sửa | YAML/env, worker và chiều lưu lượng |
| Controller `modules/defense/`, `recovery/` | Sửa | Delivery/ACK/recovery trong transaction |
| Controller `modules/detection/`, `incidents/`, `policy/` | Sửa | State, correlation, cooldown và audit |
| Controller `modules/nodes/`, `telemetry/` | Sửa | Capability reporting và thứ tự lock khi ingest |
| `src/sentinelx_controller/infrastructure/database/locking.py` | Mới | PostgreSQL transaction advisory lock theo node |
| `src/sentinelx_controller/maintenance.py`, module `maintenance.py` | Mới | Retention có dry-run/batch |
| `migrations/versions/0010_core_reliability.py` | Mới | Nâng cấp từ M8; không viết lại migration cũ |
| `deploy/agent/manage.py`, `deploy/docker/`, `compose.yaml` | Sửa/mới | Capability profile, locked build, lab enrollment/network namespace |
| `deploy/core/compose.acceptance.yaml`, `tests/e2e/test_core_*.py` | Mới | PostgreSQL concurrency và chặn/mở traffic thật |
| Unit/integration tests liên quan | Sửa/mới | Giữ hợp đồng mới và regression faults |

## 5. Architecture notes

Detector chỉ phát event; không gọi firewall. Policy trả quyết định, Defense tạo
lệnh, Agent kiểm tra lại địa chỉ và thực thi. Recovery chỉ dùng public service
của Defense/Incidents; không truy cập repository/ORM của module khác. Detection
cung cấp public interface cho incident counts và quiet observations, tránh N+1.

Node advisory lock và action/state row lock được giữ tới commit. Telemetry,
policy cooldown, detection state, incident, lệnh và audit cùng transaction:
lỗi phía sau làm rollback cả thay đổi trước. Dry-run chỉ đọc state.

Realtime delivery vẫn đi sau commit. SQLite chỉ là command journal cục bộ của
Agent, không thay PostgreSQL làm storage của Controller.

## 6. Implementation

### Delivery và receipt

1. Agent heartbeat báo protocol version 2, executor mode và supported actions.
2. Controller xác thực identity, ghi capabilities vào Node, kiểm tra recovery,
   claim lệnh trong transaction. Agent protocol 1 vẫn gửi telemetry nhưng không nhận lệnh mới.
3. PENDING → SENT có lease mặc định 30 giây, TTL giao lệnh 300 giây, tối đa 5 lượt.
   Redelivery giữ action ID, payload và delivery token ổn định.
4. Heartbeat chỉ enqueue. Worker độc lập ghi journal trước khi thực thi và ghi
   receipt trước khi gửi ACK; lỗi ACK có exponential backoff tối đa 60 giây.
5. Restart hoặc redelivery đọc lại receipt đã lưu, không chạy lại một execution đã hoàn tất.
   Cùng ID nhưng đổi payload bị từ chối. Queue mặc định 64, journal tối đa 10.000 bản ghi;
   bản đã ACK và hết hạn hơn một ngày được dọn. Hết dung lượng thì từ chối thực thi.
6. ACK phải khớp node/agent/action/token; receipt terminal không được sửa nội dung.
   Receipt APPLIED cũ sau REVERTED được nhận idempotently, không phục hồi trạng thái block.
   Late ACK chỉ được tiếp nhận khi timestamp hợp lệ và không đụng action mới đang sở hữu target.

Đây là giao lệnh ít nhất một lần với xử lý idempotent và durable receipt, không
phải cam kết exactly-once giữa SQLite, kernel và PostgreSQL. Crash ngay sau khi
kernel đổi mà chưa lưu receipt được xử lý bằng owner UUID và deadline ban đầu.

### nftables và local safety

- Hỗ trợ thực thi thật: BLOCK_IP_NFTABLES, UNBLOCK_IP_NFTABLES; ALERT_ONLY → SKIPPED.
  Các enum như RATE_LIMIT/restart/cache chưa có CORE executor sẽ bị từ chối.
- Bảo vệ loopback, non-unicast, own interfaces, Controller DNS-resolved addresses
  và protected CIDRs. Không phân giải/đọc được dữ liệu bảo vệ thì từ chối block.
- Duration 1–86.400 giây, có thể giảm tiếp bằng `max_block_seconds` trên Agent.
- nftables table chỉ được tạo khi chưa có. Schema không tương thích bị từ chối,
  không tự flush hay ghi đè rule của operator. Hai timeout set có size tối đa 10.000;
  base filter hook input/forward, priority -100, policy accept, đúng hai drop rule.
  Một accept/jump bổ sung trong chain cũng làm verification thất bại.
- Đọc element qua `nft -j list set`: nftables 1.0.6 thực tế vẫn trả text với
  `-j get element`. Kiểm thử Linux đã xác nhận khác biệt này.
- Block dùng comment action UUID và absolute deadline; retry không gia hạn TTL.
  Unblock không được xóa element của owner mới.
- Khi worker khởi động lại, reconcile những real APPLIED block còn thời hạn trong
  journal, kiểm tra lại protected addresses và dùng deadline cũ. Bỏ qua block đã có
  unblock intent trong journal. Lỗi restore được ghi ERROR yêu cầu operator kiểm tra;
  receipt APPLIED là bằng chứng thời điểm thực thi, không phải bảo đảm trạng thái
  kernel không bao giờ bị tác nhân ngoài thay đổi.

### Detection, policy, incident, recovery

- Network có age/future-skew checks, per-interface watermark, state attacker TTL
  mặc định 3.600 giây, tối đa 2.048 entries và 16 interface cursors.
- Threshold network chuẩn hóa theo cửa sổ tham chiếu 10 giây. Outbound không
  thành nguồn tấn công; unknown vẫn có thể cảnh báo nhưng không được auto-block.
  Port data bị truncate không đủ làm bằng chứng auto-defense của port-scan.
- Watermark anomaly không giảm khi resource/network observations đến khác thứ tự.
- Policy chọn theo priority tăng dần, UUID làm tie-break; audit lưu cả event,
  quyết định, policy snapshot, whitelist và protected CIDRs trong cùng transaction.
- Incident theo node/context, severity cao nhất trong batch; aggregate counts dùng
  một query. Incident đã đóng không bị tái sử dụng như incident đang hoạt động.
- Chỉ real APPLIED block được recovery. Child unblock gắn original action ID;
  stale child ACK không được xác nhận cho retry mới.
- Mặc định recovery tối đa 3 attempts, backoff 30/60 giây. Quá budget giữ lỗi rõ
  ràng để operator reconcile; không lặp vô hạn.
- Unblock thành công → REVERTED/SUCCESS. Incident chỉ RESOLVED sau quiet period
  mặc định 120 giây, không còn action active và có observation mới, đầy đủ, bình thường.
  Không có dữ liệu hoặc dữ liệu stale không được coi là đã hết tấn công.
- Hủy lệnh PENDING chưa giao qua endpoint cancel; SENT phải chờ receipt/reconcile,
  APPLIED phải qua recovery, không đổi trạng thái DB để giả vờ đã gỡ firewall.

### Retention và cấu hình

Maintenance mặc định **dry-run**, batch 1.000 và tối đa 100 batches/lần gọi:
metric 7 ngày, network window 3 ngày, policy audit 90 ngày. Dùng `received_at`
cho telemetry; không xóa detection/incident/defense/recovery audit. Có index thời gian.
Dọn cooldown cũ theo thời hạn an toàn, vẫn tôn trọng policy cũ có cooldown dài.
Đặt cron/systemd timer cho maintenance nếu muốn retention chạy định kỳ; không tự
xóa dữ liệu lúc startup. Journal/state bounds vẫn hoạt động độc lập với lịch này.

Controller env ví dụ `SENTINELX_SAFETY__PROTECTED_CIDRS='["10.10.0.0/24"]'`;
Agent env `SENTINELX_PROTECTED_CIDRS='["10.10.0.0/24"]'`. Điền mạng quản trị thực tế.
Xem `configs/controller.yaml` và `configs/agent.example.yaml` cho giá trị đầy đủ.

## 7. Commands

Quality gate:

```powershell
uv sync --all-extras
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
uv run ruff check migrations/versions/0010_core_reliability.py deploy/agent/manage.py deploy/docker/bootstrap_agent.py
```

Lab riêng PostgreSQL + firewall + traffic (không host ports, host mounts hay host network):

```powershell
docker compose -p sentinelx-core-hardening-qa -f deploy/core/compose.acceptance.yaml build
docker compose -p sentinelx-core-hardening-qa -f deploy/core/compose.acceptance.yaml up -d postgres controller peer observer
docker compose -p sentinelx-core-hardening-qa -f deploy/core/compose.acceptance.yaml run --rm --use-aliases agent-check
docker compose -p sentinelx-core-hardening-qa -f deploy/m123/compose.acceptance.yaml run --rm agent-check
docker compose -p sentinelx-core-hardening-qa -f deploy/core/compose.acceptance.yaml down --volumes
```

`--use-aliases` cần thiết để peer tìm đúng container Agent đang chạy test. Observer
tách riêng giúp đọc kết quả probe dù source IP của peer đang bị Agent block.
Test traffic chỉ đi giữa các container QA thuộc project trên.

```powershell
uv run python -m sentinelx_controller.maintenance
uv run python -m sentinelx_controller.maintenance --apply --batches 10
uv run python scripts/build_agent_bundle.py --output dist/agent
docker compose --profile lab config --quiet
docker compose --profile lab build sentinelx_controller agent01
```

## 8. Expected result và nâng cấp

1. Backup PostgreSQL và Agent identity/journal; ghi nhận firewall rules đang có.
2. Tạm dừng tự động defense và worker Agent cũ khi nâng cấp để không nhận ACK
   format cũ trong khoảng chuyển phiên bản.
3. Dùng release mới, chạy `uv sync --all-extras`, `uv run alembic upgrade head`.
   Head phải là `0010_core_reliability`.
4. Khởi động Controller mới; cập nhật bundle Agent cùng release, giữ identity và journal.
5. Khởi động Agent, kiểm tra Node capabilities protocol 2, liveness và metrics.
6. Mặc định executor vẫn simulated. Chỉ opt-in nftables sau khi cấu hình protected
   networks, hook phù hợp và capability profile như `AGENT_INSTALLATION.md`.

Migration giữ audit cũ. Legacy PENDING/SENT được tombstone thành EXPIRED, không
giao lại mù quáng. Legacy APPLIED giữ nguyên bản ghi nhưng không tự suy diễn
deadline/kết quả thực thi thật: `effective_until` để NULL, cần kiểm tra host và
reconcile thủ công. Recovery không tự timeout các bản ghi thiếu deadline này.
Receipt/command cũ không tự chuyển thành receipt protocol 2.

Nếu table nftables cũ chỉ có tên set hoặc thiếu schema cần thiết: chụp/kiểm tra
rules hiện hữu trong maintenance window; chọn table name mới hoặc thực hiện
cleanup có chủ đích sau khi đối soát block. Executor không tự xóa table không tương thích.

Root Docker lab sửa DB URL, chạy migration khi startup, dùng dependencies từ
uv.lock, bootstrap UUID/token qua API thay static token/node ID. Agent mỗi backend
có identity volume riêng và share đúng backend network namespace. Container resource
metrics là resource nhìn thấy từ container, không thay nghiệm thu native Agent của VPS.
Bootstrap tự động chỉ dành lab opt-in, không phải cơ chế onboarding/authorization của M9.

## 9. Troubleshooting

| Biểu hiện | Kiểm tra/hướng xử lý |
|---|---|
| Không nhận command | protocol 2, supported actions, enrollment, lease/deadline |
| FAILED Operation not permitted | nft binary, NET_ADMIN và AF_NETLINK trong service profile |
| Schema incompatible | hook/table/rules; đối soát table cũ, không flush rules toàn máy |
| Không block được management/Controller | Đây là local safety; kiểm tra target và CIDR, không bypass protection |
| Reconciliation ERROR sau reboot | journal còn nguyên? permission? schema? owner khác? kiểm tra kernel và recovery audit |
| Recovery FAILED sau 3 lượt | Kiểm tra host thật rồi dùng quy trình operator reconciliation; không reset budget tự động |
| Incident chưa RESOLVED | Cần telemetry/window đầy đủ, mới và bình thường qua quiet period |
| Journal đầy/hỏng/không ghi được | Khôi phục filesystem/permission và backup; không xóa journal để ép chạy lại |
| Biểu đồ lịch sử bị giữ quá lâu | Dry-run maintenance, kiểm tra lịch cron/timer và retention config |

## 10. Checkpoint và bằng chứng

- Ruff và mypy strict chạy trên src/tests; Ruff bổ sung cho migration/installer/bootstrap.
- Windows: **311 PASS, 11 SKIP** (11 ca live opt-in được chạy riêng trong lab).
- Linux unit/integration: **311 PASS**. Hai bộ đều có 5 cảnh báo deprecation
  Starlette đã tồn tại, không có test fail. Không thêm dependency để che cảnh báo.
- Mypy strict: **220 files, 0 errors**. Ruff: **0 errors** cho src/tests và các
  script/migration bổ sung. `git diff --check` sạch đối với thay đổi bàn giao.
- Lab PostgreSQL M1–M3 + migration: 9 PASS, gồm empty/M2/M3/M8 → head,
  downgrade từ 0010 về 0009 rồi upgrade lại; dữ liệu kiểm tra được giữ.
- Lab CORE: 2 PASS: real nft block/unblock với traffic từ namespace khác,
  receipt sau restart, concurrent action/heartbeat; policy concurrent transaction
  chỉ authorize một lần và rollback giải phóng cooldown.
- Native nftables ở lab chạy dưới UID 10001, chỉ NET_ADMIN + NET_RAW; capture M2
  chạy riêng dưới UID không root và chỉ NET_RAW. Không dùng privileged/host network.
- Agent Docker image mới đã bootstrap/enroll/heartbeat và gửi real metrics vào
  PostgreSQL trong private network; PID 1 UID 10001, node online và có hàng trăm samples.
- Controller Docker image mới chạy UID 10001:10001 với capabilities bị drop,
  migration startup thành công và health check healthy trên PostgreSQL lab.
- Bundle `dist/agent/sentinelx-agent-0.1.0-996e3957bc6a.tar.gz`: 51 file, đã kiểm
  tra SHA-256 theo manifest và xác nhận không chứa package Controller.
- Không đụng các container/dữ liệu ứng dụng khác đang chạy.

Giới hạn bằng chứng: chưa nghiệm thu lại trên VPS/LAN nhiều máy, chưa chạy live
systemd profile mới trên VPS trong đợt này, chưa benchmark tải/công suất tối đa.
Systemd override mới có kiểm thử quản lý file và có thể tái lập bằng hướng dẫn cài đặt.
Các test API dùng receipt fixture không được coi là bằng chứng kernel; bằng chứng
kernel nằm riêng ở `tests/e2e/test_core_live.py`.

## 11. Stop

Bàn giao tại CORE M1–M8. Không tự mở M9 hoặc thay đổi giao diện. Thay đổi nằm trên
nhánh làm việc; không tự push/merge trong yêu cầu hoàn thiện lõi này.
