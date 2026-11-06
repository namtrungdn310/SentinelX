# M2 — Network Collection + Aggregation

## 1. Milestone và scope

M2 bổ sung quan sát packet metadata trên Linux bằng Scapy 2.8/libpcap, tổng hợp
cửa sổ trượt, gửi batch về Controller và lưu/query/broadcast dữ liệu tổng hợp.
Không triển khai detector M3/M4, incident/policy, firewall, recovery, deep packet
inspection, connection reassembly hay trang dashboard mạng mới. Các việc publish
bundle/onboarding website còn mở ở M1 không được tuyên bố đã giải quyết bởi M2.

## 2. Luồng thực thi

```text
Linux interface (cấu hình) -> libpcap BPF, non-promiscuous
 -> Scapy callback store=False -> PacketObservation (metadata thuần)
 -> SlidingWindowAggregator (bounded, thread-safe)
 -> tối đa 16 cửa sổ chờ, mỗi POST tối đa 4 cửa sổ
 -> Controller xác minh node/Agent qua public NodeService
 -> PostgreSQL telemetry_network_windows (JSONB aggregate features)
 -> REST query / WebSocket network_feature_update
```

Capture chạy trong thread; heartbeat và resource loop M1 độc lập. Mất capture
không dừng M1 hoặc gửi các cửa sổ zero giả. Khi capture phục hồi, bắt đầu cửa sổ
đầy đủ mới; phần cửa sổ dở dang trước lỗi bị bỏ. Journal ghi loại lỗi, không dump
packet, payload, token hay credential.

## 3. Định nghĩa dữ liệu và giới hạn

- Một nhóm: `(source_ip, destination_ip, protocol)` có hướng, trong một interface.
- `packet_count`: số IP packet đã quan sát/giải mã trong cửa sổ.
- `byte_count`: tổng độ dài IP khai báo trong header (fallback độ dài IP đã giải
  mã khi dựng packet), không gồm Ethernet overhead; không phải application bytes.
- `protocol`: tcp/udp/icmp/other; hỗ trợ IPv4 và IPv6 cơ bản. IPv6 extension
  headers/tunnel được xếp `other` nếu transport không trực tiếp; không reassemble
  fragment. ICMP quoted inner TCP không bị đếm thành kết nối/TCP SYN của outer IP.
- `syn_count`, `ack_count`, `rst_count`, `fin_count`: đếm packet chứa từng bit,
  không phải connection count. SYN+ACK đóng góp cho cả SYN và ACK.
- `destination_ports`: danh sách phân biệt đã giữ, tối đa 64 ở Agent; vượt giới
  hạn đặt `ports_truncated=true`. Không tuyên bố đây là tổng distinct port chính xác.
- Window mặc định 10s, step 5s; tối đa 12 overlap, duration <=300s, size chia hết
  step. Các khoảng `[start,end)` dựa trên clock monotonic, anchor UTC lúc sniffer
  sẵn sàng. Không cộng các cửa sổ chồng lấp để tính tổng/rate toàn khoảng.
- Mặc định 256 nhóm/window (config tối đa 1024). Vượt nhóm ghi
  `omitted_packets`, không giữ thêm IP/port set vô hạn. Đây là cardinality
  truncation của aggregator, không phải kernel capture drop.
- Lịch sử aggregator bị giới hạn ở các cửa sổ active và tối đa 16 completed;
  scheduler quá chậm đặt `skipped_windows`. Các giới hạn cấu hình lớn dùng nhiều
  RAM hơn; không có bảo đảm capture không mất gói ở lưu lượng đường truyền lớn.
- Transport giữ tối đa 16 windows trong RAM, overflow bỏ window cũ và log. Không
  có disk spool; crash/restart có thể mất dữ liệu chưa gửi.
- Window ID ổn định khi retry. Khóa `(node_id, window_id)` chống insert trùng
  đồng thời; bản ghi đầu tiên giữ nguyên nếu replay cùng ID. Sequence là metadata,
  không thay thế idempotency key. Không có exactly-once end-to-end.

Capture chỉ thấy traffic trong interface/network namespace đang chạy, không phải
toàn bộ VPC/DigitalOcean hay mọi Docker host. Chọn BPF hẹp nếu cần loại trừ traffic
quản trị/Controller. Chỉ filter IPv4/IPv6 được giải mã; ARP và các frame khác bị bỏ.
Không export kernel/libpcap drop statistics trong bản M2 này.

## 4. API và lưu trữ

- `POST /api/v1/telemetry/network-features`: UUID node/Agent, sequence, sent_at
  có timezone, 1..16 windows. Xác minh credential trước khi lưu. HTTP 200 chứa
  `processed_count` số cửa sổ **mới**, retry đã lưu trả 0 vẫn là thành công.
- `GET /api/v1/telemetry/nodes/{node_id}/network-features`: `start_time`, `end_time`
  (timezone bắt buộc), `limit` 1..100 mặc định 20. Lọc theo window_end, thứ tự
  window_end giảm dần rồi window_id; unknown node 404, filter đảo ngược 422.
- Window: UUID, start/end UTC, interface, features, omitted_packets, skipped_windows.
  Payload/field không thuộc contract bị từ chối. Group duplicate bị từ chối.
- WebSocket event `network_feature_update` chứa node_id, received_at, windows mới;
  replay không broadcast lại. Không phải DetectionEvent. Sau tích hợp 06/11/2026,
  HTTP ingest chỉ phát event sau commit; lỗi commit không phát dữ liệu chưa lưu.
  WebSocket vẫn best effort; client query REST sau disconnect để phục hồi.
  Dashboard resource hiện bỏ qua event này để không đẩy các window lớn/tần suất
  cao vào nhật ký và phần sự kiện đáng chú ý của M1; chưa có network view consumer.
- Migration `0004_m2_network_windows`, parent `0003_f8_telemetry_metric_samples`;
  PK node/window, FK cascade node, index node/window_end, aggregate JSONB.
  Không đổi bảng metric cũ hay xóa dữ liệu M1.
  Khi ghép M3, giữ nguyên revision M2/M3 cũ, thêm merge revision 0005 rồi state
  revision 0006. Chạy `alembic upgrade head`, không stamp lại database hoặc xóa bảng.
  Chi tiết: [M2/M3 integration](M2_M3_INTEGRATION.md).

Các API này giữ mô hình quyền Foundation hiện tại; không bổ sung auth/account/
tenant isolation mới trong M2. Khi expose qua Internet, cấu hình gateway và quyền
truy cập vận hành theo deployment hiện có; feature metadata chứa IP thực tế.

## 5. Cài và bật

```bash
uv sync --all-extras --frozen
uv run alembic upgrade head
uv run python scripts/build_agent_bundle.py
```

Controller cần migration trước khi Agent bật capture. Agent bundle M2 chứa Scapy,
nhưng thư viện OS libpcap phải được cài riêng. Xem mục M2 trong
[AGENT_INSTALLATION.md](AGENT_INSTALLATION.md) cho config và lệnh
`manage.py capture-permissions --enable`. Capture vẫn mặc định tắt trên bản cài
mới và khi update cấu hình M1 chưa có các khóa network.

Profile systemd chỉ thêm CAP_NET_RAW cùng AF_PACKET/AF_NETLINK, giữ UID service,
NoNewPrivileges và các giới hạn filesystem. Không cấp CAP_NET_ADMIN và không
thay đổi firewall. `check` chỉ xác thực config/identity, không thử capture socket.

## 6. File và ranh giới

| File | Trách nhiệm |
|---|---|
| `sentinelx_common/contracts/network.py` | Wire validation, không có collector/ORM |
| `sentinelx_agent/network/aggregation.py` | Metadata counters, overlapping windows, bounds |
| `sentinelx_agent/network/capture.py` | Scapy/libpcap adapter, socket/thread cleanup |
| `sentinelx_agent/network/runtime.py` | Supervisor, queue, retry, failure isolation |
| Agent config/client/daemon/CLI | Opt-in config, REST push, lifecycle/local diagnostics |
| Telemetry `network_models/repository/service/router.py` | PostgreSQL persistence, public NodeService auth, query/WS |
| Migration `0004_m2_network_windows.py` | Schema upgrade/downgrade |
| `deploy/agent/manage.py` | Opt-in capability override và gỡ override do chính nó quản lý |
| `deploy/m2/compose.acceptance.yaml` | Isolated non-root packet capture acceptance |

## 7. Kiểm thử và lệnh tái lập

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
docker compose -p sentinelx-m2-acceptance -f deploy/m2/compose.acceptance.yaml up --build --abort-on-container-exit --exit-code-from agent-check
```

Lab M2 không mở host port, không mount host, không privileged/host networking.
Launcher container tạm dùng SETUID/SETGID/SETPCAP để hạ UID; process pytest/Agent
thực tế có UID10001 và **chỉ NET_RAW** trong effective/bounding/ambient sets. Test
assert các giá trị đó trước capture. UDP chỉ sinh trên loopback container của lab,
Controller và PostgreSQL ở container khác. Trường hợp interface sai phải vẫn có
metric M1 và không có network windows giả.

Full pytest mặc định skip các test live M1/M2 khi không có URL lab. Test bật live
ghi project/node giả vào database, tuyệt đối chỉ trỏ tới DB lab riêng.

Native systemd có HTTP contract fixture riêng (không phải Controller thật):

```bash
sudo python3 scripts/test_agent_systemd.py /path/to/extracted-bundle --uv /absolute/path/to/uv --network-capture
```

Script tạo service/user tên QA riêng, gửi UDP loopback, kiểm tra capability và
purge sau thử. Cần libpcap sẵn trên máy Linux lab. Không reboot máy.

Sau nghiệm thu lab, dọn đúng project này:

```bash
docker compose -p sentinelx-m2-acceptance -f deploy/m2/compose.acceptance.yaml down --volumes
```

## 8. Kết quả / checkpoint

Checkpoint 04/11/2026, nhánh `milestone/m2-network-collection` từ dev `f3cfcbe`.

| Kiểm tra | Kết quả |
|---|---|
| Ruff / strict mypy src + tests | PASS, 126 source/test files |
| Full pytest Windows Python 3.12.10 | 193 passed, 4 opt-in live cases skipped |
| Full pytest Linux Python 3.12.15 | 193 passed, 4 opt-in live cases skipped |
| Live M1 + M2 trên cùng Controller/PostgreSQL | 4 passed (2 M1, 2 M2) |
| Migration PostgreSQL 16 upgrade -> downgrade -> upgrade | PASS |
| Native Ubuntu 22.04/systemd 249, HTTP contract fixture | PASS, UID riêng, effective capability chỉ NET_RAW, capture thật, lifecycle/update/rollback/purge |
| Agent-only bundle | `dist/agent/sentinelx-agent-0.1.0-a761f8920467.tar.gz`, 19 runtime packages |
| Dashboard lint / production build / render smoke | PASS, 25 smoke checks; chỉ đổi lọc message, không đổi giao diện |

16 kiểm thử thường được bổ sung (15 unit về decode/aggregation/config/retry/failure,
1 integration endpoint) cùng 2 ca live M2. Các suite thường còn 3 cảnh báo
deprecation Starlette có sẵn. Native fixture không được gọi là Controller thật;
kiểm tra với Controller/PostgreSQL thật chạy trong Docker riêng. Lỗi live đầu
tiên đã phát hiện Scapy chưa load layer dissector trước mở pcap; đã sửa và chạy
lại capture thật thành công. systemd-analyze có warning snapd không thuộc unit
SentinelX trên WSL; không thay đổi service snapd.

Chưa có bằng chứng triển khai M2 trên hai máy/VM vật lý qua LAN hoặc benchmark
tải packet cao. Docker single-host và WSL không thay thế nghiệm thu đó.

## 9. Stop

Checkpoint ban đầu chỉ triển khai M2. Lượt 06/11/2026 được yêu cầu tích hợp M2
với M3 đã có trên dev và sửa lỗi tương tác; không triển khai M4 trở đi.

Tham chiếu: [Scapy sniffing](https://scapy.readthedocs.io/en/latest/usage.html#asynchronous-sniffing),
[Scapy/libpcap](https://scapy.readthedocs.io/en/latest/usage.html#configuring-super-sockets),
[Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html).
