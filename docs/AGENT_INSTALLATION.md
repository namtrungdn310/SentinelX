# Cài và vận hành SentinelX Agent — M1

Agent được cài **trên từng Linux server cần giám sát**. systemd chạy Agent dưới
tài khoản riêng; Agent đọc tài nguyên OS bằng psutil rồi chủ động gửi REST/JSON
đến Controller. Không cần cài Controller, PostgreSQL hay source ứng dụng khách
hàng trên server đó. M1 không thu gói tin, không cần root/capability firewall.

## 1. Yêu cầu và phạm vi hỗ trợ

- Linux có systemd đang chạy, Python hệ thống >=3.10 để chạy bộ quản lý cài đặt,
  `useradd`, `runuser`, `systemd-analyze`, và `uv` được cài từ nguồn tin cậy.
- Runtime Agent là **Python 3.12**, được uv quản lý riêng tại `/opt/sentinelx-agent/python`.
  Lần cài đầu cần Internet tới kho Python/PyPI, CA certificate và DNS hợp lệ.
- Cài/cập nhật/gỡ cần sudo; **daemon không chạy root**. Chưa cung cấp .deb/.rpm,
  installer offline hay Windows service. Kiểm chứng thực tế ở Ubuntu 22.04/systemd 249.
- Controller ở địa chỉ cấu hình được, có thể là máy/VM khác. Dùng HTTPS có chứng
  thư hợp lệ trên mạng không tin cậy; HTTP chỉ phù hợp lab có kiểm soát.

## 2. Tạo artifact trên máy phát triển

Tại gốc repository (không cần copy cả repository sang server đích):

```bash
uv sync --all-extras --frozen
uv run python scripts/build_agent_bundle.py
```

Kết quả: `dist/agent/sentinelx-agent-0.1.0-<hash>.tar.gz`. Bundle chỉ chứa
`sentinelx_agent`, `sentinelx_common`, requirements khóa version/hash xuất từ
`uv.lock`, bộ quản lý và systemd template. Không đóng gói Controller/DB/dev tools.
Release ID phụ thuộc nội dung; không ghi đè artifact cùng tên đã có.

Chuyển archive đến server bằng kênh tin cậy, đối chiếu `sha256sum` với checksum
nhận qua kênh tin cậy rồi giải nén. Manifest kiểm tra tính toàn vẹn từng file,
**không phải chữ ký xác thực nhà phát hành**. Không chạy `manage.py` từ nguồn lạ
bằng sudo, không dùng pipeline tải script trực tiếp vào shell.

## 3. Cài đặt và enrollment

Trên dashboard/API của Controller: tạo project, tạo node và cấp enrollment token
cho **đúng node UUID**. Token có hạn và dùng một lần; không đưa vào Git, shell
history, argv, ảnh chụp hay log. Các tên in hoa dưới đây là chỗ cần thay thế.

Trong thư mục bundle đã giải nén:

```bash
sudo python3 manage.py install \
  --controller-url https://CONTROLLER_HOST:PORT \
  --node-id NODE_UUID_FROM_CONTROLLER \
  --uv /absolute/path/to/uv --no-start
sudo python3 manage.py enroll
sudo python3 manage.py restart
sudo python3 manage.py check
sudo python3 manage.py status
```

`enroll` hỏi token bằng prompt ẩn. Service được enable sau khi cài; `--no-start`
để hoàn tất enrollment trước khi khởi chạy. Nếu máy reboot trước enrollment,
service báo chưa đăng ký và thoát mã 78; đăng ký xong chạy `restart`.

Với automation, cấp một file token **0600** nằm ngoài bundle, do root đọc được:
`sudo python3 manage.py enroll --token-file /secure/path/enrollment-token`.
Hoặc thêm `--token-file` khi `install` để enroll và start trong một lệnh.
Token được truyền vào tiến trình Agent qua stdin và không ghi vào config/identity;
bộ cài không xóa file đầu vào của operator. Xóa file này sau khi đăng ký thành công.

## 4. Dữ liệu, quyền và cấu hình

| Vị trí | Vai trò / quyền |
|---|---|
| `/opt/sentinelx-agent/releases/<release>` | Code + venv từng phiên bản, root quản lý |
| `/opt/sentinelx-agent/current`, `previous` | Con trỏ phiên bản hiện tại / rollback |
| `/etc/sentinelx-agent/agent.yaml` | Cấu hình JSON hợp lệ theo YAML; root:service 0640, thư mục 0750 |
| `/var/lib/sentinelx-agent/identity.json` | Identity chứa credential `agent_id`, file 0600, thư mục 0700 |
| `/etc/systemd/system/sentinelx-agent.service` | Unit systemd, root 0644 |

Sửa `/etc/sentinelx-agent/agent.yaml` bằng sudo; kiểm tra rồi restart. Các khóa:
`controller.url`, `agent.node_id`, `telemetry_collector_type: real`,
`telemetry_interval_seconds`, `telemetry_batch_size`, `telemetry_disk_path`,
`identity_path`; `agent.heartbeat_interval_seconds` đặt nhịp khởi đầu, Controller
có thể trả nhịp heartbeat mới. Xem `configs/agent.example.yaml` trong repository.
Không thêm enrollment token vào file vận hành thường xuyên.

`check` chỉ xác thực cấu hình/identity **cục bộ**, không chứng minh Controller còn
reachable hoặc đã lưu metric. Kiểm tra dashboard/API và journal cho đầu cuối.
Node UUID không khớp identity hoặc identity hỏng sẽ bị từ chối thay vì tự đăng ký lại.

Service có filesystem read-only trừ state, không truy cập home người dùng, không
có Linux capability. Nó giữ quyền đọc `/proc` và network namespace của host để đo
đúng host. Không áp dụng `PrivateNetwork`/ẩn `/proc` vì sẽ làm sai metric.

## 5. Log, restart và khởi động cùng hệ thống

```bash
sudo journalctl -u sentinelx-agent.service -n 100 --no-pager
sudo journalctl -u sentinelx-agent.service -f
sudo systemctl is-enabled sentinelx-agent.service
sudo systemctl stop sentinelx-agent.service
sudo systemctl start sentinelx-agent.service
```

systemd enable service cho boot, tự restart sau crash (5s), có giới hạn restart.
Lỗi config/identity mã 78 không restart lặp. `SIGTERM`/`SIGINT` dừng vòng lặp,
hủy task còn lại và đóng HTTP client. Bộ đệm RAM chưa gửi không bền qua restart;
M1 không tuyên bố exactly-once hoặc đảm bảo không mất mẫu khi crash/stop.

## 6. Cập nhật, rollback và gỡ

Giải nén bundle mới vào thư mục khác, xác minh nguồn/checksum rồi chạy từ đó:

```bash
sudo python3 manage.py update --uv /absolute/path/to/uv
sudo python3 manage.py check
sudo python3 manage.py rollback
```

Update dựng dependencies của release mới trước khi đổi `current`; giữ nguyên
config/identity ngoài release. Khi kiểm tra cục bộ/restart thất bại, khôi phục
release cũ. `previous` giữ một đích rollback; release cũ chưa tự động bị xóa.
Đây là rollback ứng dụng, không phải rollback schema DB (Agent không có DB).
Service active không đảm bảo Controller reachable; sau update vẫn cần kiểm tra
journal và metric mới trên Controller. `--no-start` không restart service đang có.

```bash
sudo python3 manage.py uninstall
# Cài lại bundle: giữ config/node/identity cũ, không truyền --node-id/--controller-url.
sudo python3 manage.py install --uv /absolute/path/to/uv
```

Uninstall dừng/disable unit và xóa runtime, giữ config, identity, tài khoản cùng
marker quản lý để cài lại không cần enrollment. Sao lưu identity như một secret.
`uninstall --purge` **xóa vĩnh viễn** config/identity/runtime và tài khoản; chỉ dùng
khi chủ động hủy Agent. Node trên Controller không tự bị xóa. Mất identity cần
operator xác nhận/quản lý node và cấp enrollment token mới; không copy identity
sang một server khác.

Mỗi host thông thường dùng tên mặc định. Trong lab, có thể dùng tên riêng:
`python3 manage.py --name sentinelx-agent-lab <command>`; mọi lệnh sau đó phải dùng
cùng tên. Chỉ tên bắt đầu `sentinelx-agent` được chấp nhận; bộ quản lý từ chối
ghi đè đường dẫn không có marker của chính nó.

## 7. Nghiệm thu trước khi đưa vào dùng

1. `check`, `is-active`, `is-enabled` đạt; PID Agent có UID service, không phải root.
2. Identity 0600; restart không enroll lại; journal không chứa token/agent credential.
3. CPU/RAM/disk trên Controller so với công cụ OS với cửa sổ đo tương đương.
4. RX/TX là delta byte giữa các lần đọc, không phải bytes/s; mất đọc/baseline là null.
5. Ngắt kết nối lab có kiểm soát rồi khôi phục: heartbeat/metric gửi tiếp, retry FIFO.
6. Cập nhật → rollback → uninstall giữ state → reinstall vẫn cùng identity.
7. Thử reboot **máy lab được phép reboot** để kiểm chứng boot thực tế. `enable`
   và restart test không thay thế bằng chứng reboot hay lab nhiều máy vật lý.

## 8. Xử lý lỗi

- `uv` không thấy khi sudo: truyền đường dẫn tuyệt đối; không đặt runtime trong `/root`.
- Cài dependency gián đoạn: chạy lại `install` trên installation đã có marker,
  không truyền lại node/Controller; release chưa hoàn tất sẽ được dựng lại.
- `78`: sửa config/khôi phục identity từ backup; `check` rồi `restart`.
- `start-limit-hit`: xử lý nguyên nhân rồi `sudo systemctl reset-failed sentinelx-agent`.
- Token hết hạn/đã dùng: cấp token mới cho đúng node; không log/copy token vào lệnh.
- Disk không đọc được: metric null là đúng; kiểm tra mount/quyền/path. Không cấp root
  cho Agent chỉ để làm biến mất một trường null.
- Controller timeout: kiểm tra DNS, port, route, TLS, bind address. URL Agent phải
  trỏ tới Controller thật trên mạng; localhost chỉ đúng khi cố ý chạy cùng host.

Thiết kế unit tham chiếu [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
và [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).

## 9. Bật thu thập mạng M2 (tùy chọn)

Capture mặc định tắt. Trên Ubuntu 22.04/Debian 12, cài thư viện hệ thống
`libpcap0.8` bằng package manager; Scapy đã có trong requirements của bundle M2.
Chọn interface thực tế của server (`ip -br link`), không mặc định mọi máy là eth0.
Sửa phần `agent` trong cấu hình, giữ các khóa/identity M1 đang có:

```yaml
network_capture_enabled: true
network_interface: ens3
network_bpf_filter: "ip or ip6"
network_window_seconds: 10
network_step_seconds: 5
network_max_groups: 256
```

Từ bundle đã giải nén, cấp profile capture rồi kiểm tra/restart:

```bash
sudo python3 manage.py capture-permissions --enable
sudo python3 manage.py check
sudo python3 manage.py restart
sudo journalctl -u sentinelx-agent.service -f
```

Profile cấp **CAP_NET_RAW**, cho phép socket AF_PACKET/AF_NETLINK cần thiết; daemon
vẫn chạy bằng user riêng, không có CAP_NET_ADMIN, không bật promiscuous mode.
Đường dẫn override: `/etc/systemd/system/sentinelx-agent.service.d/50-sentinelx-network.conf`.
Không setcap lên Python hệ thống và không dùng `--privileged` hoặc host networking.

Một cửa sổ tổng hợp theo IP nguồn/đích và giao thức; tối đa 64 cổng đích được giữ
cho mỗi nhóm. Không ghi PCAP hay packet payload. IP metadata vẫn là dữ liệu vận hành.
Agent gửi cửa sổ qua `/api/v1/telemetry/network-features`; query lịch sử theo node
qua `/api/v1/telemetry/nodes/{node_id}/network-features`. Đây chưa phải một trang
phân tích mạng riêng trên dashboard và chưa có phát hiện/chặn tấn công.

Khi thiếu libpcap/quyền/interface hoặc BPF không hợp lệ, journal báo
`Network capture unavailable`; resource monitoring M1 vẫn chạy. Không có cửa sổ
mới không đồng nghĩa lưu lượng bằng 0. Cửa sổ rỗng chỉ được gửi khi sniffer đang
chạy; kiểm tra timestamp và journal khi đánh giá độ mới của dữ liệu.

Để tắt: đặt `network_capture_enabled: false`, chạy
`sudo python3 manage.py capture-permissions --disable`, rồi restart. Uninstall
xóa override do SentinelX quản lý; khi cài lại mà vẫn muốn capture, cấp lại profile
này. Override đã chỉnh tay sẽ bị từ chối ghi đè/xóa để operator tự kiểm tra.

Theo dõi các dấu hiệu thiếu dữ liệu: `omitted_packets` (vượt số nhóm),
`ports_truncated` (vượt 64 cổng), `skipped_windows` (scheduler chậm), cùng log bộ
đệm đầy. Các trường này **không** đo số packet bị kernel/libpcap drop. Cửa sổ chồng
lấp, không cộng trực tiếp số gói/byte của các cửa sổ liên tiếp.
