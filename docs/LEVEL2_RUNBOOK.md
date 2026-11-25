# SentinelX — Kế hoạch Triển khai Mức 2 Chi tiết (2 Laptop + VMware Linked Clone + Tailscale)

Tài liệu này là **runbook từng bước một** dành riêng cho mô hình 2 thành viên PBL4, tận dụng máy ảo `Ubuntu 24.04` sẵn có trên **VMware Workstation Pro** mà **tuyệt đối không làm ảnh hưởng** tới các máy ảo lab môn Điện toán đám mây (`Ubuntu 24.04`, `Server2K12-DNS`, `Windows8-DomainLab`).

> **Nguyên tắc thực hiện:** Làm cuốn chiếu **từng bước (Step-by-Step)** — kiểm tra **PASS** tiêu chí của bước hiện tại rồi mới sang bước kế tiếp.

---

## 1. Phân vai & Kiến trúc Mạng Mức 2

```text
                ┌──────────────────────────────────────────┐
                │   Wi-Fi Nhà / Hotspot 5G iPhone / LAN    │
                └──────────┬────────────────────┬──────────┘
                           │ (Tailscale Mesh)   │ (Tailscale Mesh)
                           ▼                    ▼
┌────────────────────────────────────┐    ┌────────────────────────────────────┐
│ LAPTOP A (Máy của bạn - Windows)   │    │ LAPTOP B (Máy bạn cùng nhóm)       │
│ Tailscale IP: <TS_LAPTOP_A>        │    │                                    │
│                                    │    │  ┌──────────────────────────────┐  │
│  [Docker --profile core]           │    │  │ VM: SentinelX-Node02 (NAT)   │  │
│   ├── postgres_db (:5432)          │    │  │ Linked Clone Ubuntu 24.04    │  │
│   ├── sentinelx_controller (:8000) │◄───┼──┤ Tailscale IP: <TS_VM_02>     │  │
│   └── sentinelx_dashboard (:5174)  │    │  │ ├── Web Workload (:8080)     │  │
│                                    │    │  │ └── sentinelx-agent (systemd)│  │
│  [Host Windows Process]            │    │  └──────────────────────────────┘  │
│   └── sentinelx_lb (:8080) ────────┼────┼──► HTTP Proxy + /health            │
│                                    │    └────────────────────────────────────┘
│  ┌──────────────────────────────┐  │
│  │ VM: SentinelX-Node01 (NAT)   │  │
│  │ Linked Clone Ubuntu 24.04    │  │
│  │ Tailscale IP: <TS_VM_01>     │  │
│  │ ├── Web Workload (:8080)     │  │
│  │ └── sentinelx-agent (systemd)│  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

### Tại sao chọn kiến trúc này?
1. **Bảo toàn 100% lab Điện toán đám mây**: Chỉ clone từ snapshot `new` của `Ubuntu 24.04` (đang *Powered off*) bằng **Linked Clone**; giữ nguyên `Server2K12-DNS` và `Windows8-DomainLab`.
2. **Tương thích 5G Hotspot iPhone & Wi-Fi trường**: Giữ card VMware ở chế độ **`NAT`** kết hợp **`Tailscale`** (`100.x.y.z`) để các máy giữ IP cố định, không gặp lỗi DHCP Bridged trên iPhone Hotspot hay Client Isolation ở giảng đường.
3. **Tách Control Plane & LB tối ưu cho multi-host**:
   - Postgres + Controller + Dashboard chạy bằng Docker (`--profile core`), giữ nguyên endpoint tải **Agent Bundle tự động** (`/api/v1/system/agent-bundle/download`) và Nginx SPA (`:5174`).
   - Load Balancer (`sentinelx_lb`) chạy trực tiếp trên Windows Laptop A (`0.0.0.0:8080`) để đi thẳng qua card Tailscale của Windows tới `http://<TS_VM_01>:8080` và `http://<TS_VM_02>:8080`.

---

## 2. Checklist Bảng Ghi IP Thực tế (Điền khi triển khai)

| Thành phần | Máy vật lý / VM | Tên máy / Ghi chú | Tailscale IP (`100.x.y.z`) | Cổng sử dụng |
|---|---|---|---|---|
| **Control Plane + LB** | Laptop A (Windows) | Chạy Docker `core` + `sentinelx_lb` | `TS_LAPTOP_A = ___________` | `8000`, `5174`, `8080` |
| **Worker Node 1** | VM `SentinelX-Node01` (Laptop A) | Linked Clone từ `Ubuntu 24.04` | `TS_VM_01 = ______________` | `8080` (Web app) |
| **Worker Node 2** | VM `SentinelX-Node02` (Laptop B) | Linked Clone Ubuntu trên Laptop B | `TS_VM_02 = ______________` | `8080` (Web app) |

---

## 3. Lộ trình Triển khai Từng Bước Một (7 Bước)

### Bước 1 — Tạo Linked Clone an toàn trên VMware (Laptop A & Laptop B)
- **Thao tác**:
  1. Kiểm tra `Ubuntu 24.04` đang ở trạng thái *Powered off* (không chạm `Server2K12-DNS`, `Windows8-DomainLab`).
  2. Trên Laptop A: chuột phải `Ubuntu 24.04` → **Manage → Clone** → chọn snapshot `new` → **Create a linked clone** → đặt tên **`SentinelX-Node01`**.
  3. Chỉnh RAM xuống `2 GB` (khuyến nghị để chạy nhẹ song song với Docker trên Laptop A), giữ nguyên **Network Adapter = NAT**.
  4. Trên Laptop B: làm tương tự tạo **`SentinelX-Node02`**.
  5. Bật nguồn 2 VM clone, kiểm tra có Internet bình thường.
- **Tiêu chí PASS Bước 1**: Cả `SentinelX-Node01` và `SentinelX-Node02` boot lên Ubuntu thành công, `ping -c 2 1.1.1.1` thông, 3 máy lab cũ vẫn nguyên trạng.

### Bước 2 — Thiết lập mạng Mesh Tailscale & Mở Firewall Windows Laptop A
- **Thao tác**:
  1. Cài **Tailscale** trên **Laptop A (Windows)**, **`SentinelX-Node01`**, và **`SentinelX-Node02`** (đăng nhập cùng 1 tài khoản Tailscale).
  2. Lấy IP Tailscale (`tailscale ip -4` trên Linux, icon Tailscale trên Windows) và ghi vào bảng ở Mục 2 (`TS_LAPTOP_A`, `TS_VM_01`, `TS_VM_02`).
  3. Trên **Windows Defender Firewall** của Laptop A: mở Inbound TCP port **`8000`**, **`8080`**, **`5174`** (hoặc cấu hình rule cho phép interface Tailscale).
- **Tiêu chí PASS Bước 2**: Từ bên trong `SentinelX-Node01` và `SentinelX-Node02`, lệnh `ping -c 2 <TS_LAPTOP_A>` thông; Laptop A `ping <TS_VM_01>` và `ping <TS_VM_02>` thông (thử kiểm tra luôn qua Wi-Fi và/hoặc Hotspot 5G iPhone).

### Bước 3 — Khởi động Control Plane & Load Balancer trên Laptop A (Chuyển từ Lab Mức 1 sang Mức 2)
- **Thao tác**:
  1. Dừng cụm lab Mức 1 đang chiếm cổng `8080` và tách dữ liệu lab cũ:
     ```powershell
     docker compose --profile lab down
     ```
  2. Bật cụm Control Plane (`postgres_db` + `sentinelx_controller` + `sentinelx_dashboard`), trỏ `SENTINELX_DEFAULT_LB_URL` về LB chạy trên Windows host:
     ```powershell
     $env:SENTINELX_DEFAULT_LB_URL = "http://host.docker.internal:8080"
     docker compose --profile core up -d --build
     ```
  3. Tại một terminal PowerShell khác ở gốc repo trên Laptop A, khởi động **Load Balancer** chế độ động (để Dashboard đồng bộ pool VM thật):
     ```powershell
     $env:SENTINELX_LB_HOST = "0.0.0.0"
     $env:SENTINELX_LB_PORT = "8080"
     $env:SENTINELX_LB_BACKENDS = ""
     $env:SENTINELX_LB_ALGORITHM = "round_robin"
     $env:SENTINELX_LB_HEALTH_CHECK__ENABLED = "true"
     $env:SENTINELX_LB_HEALTH_CHECK__PATH = "/health"
     $env:SENTINELX_LB_HEALTH_CHECK__INTERVAL_SECONDS = "3.0"
     $env:SENTINELX_LB_ADMIN_TOKEN = "sentinelx_dev_lb_token"
     uv run python -m sentinelx_lb.main
     ```
- **Tiêu chí PASS Bước 3**:
  - Truy cập `http://localhost:5174` trên Laptop A và `http://<TS_LAPTOP_A>:5174` trên Laptop B đều mở được Dashboard xanh `"Đã kết nối"`.
  - Từ terminal trong `SentinelX-Node01` / `SentinelX-Node02`, chạy `curl -fsS http://<TS_LAPTOP_A>:8000/api/v1/system/agent-bundle` trả về `"available": true`.

### Bước 4 — Bật Web Workload (Ứng dụng khách hàng mẫu) trên 2 VM Ubuntu
- **Thao tác**:
  1. Cài công cụ nền tảng trên cả `SentinelX-Node01` và `SentinelX-Node02`:
     ```bash
     sudo apt-get update && sudo apt-get install -y curl python3 python3-venv libpcap0.8 nftables
     curl -LsSf https://astral.sh/uv/install.sh | sh
     export PATH="$HOME/.local/bin:$PATH"
     ```
  2. Chạy web app mẫu ([lab/backend/app.py](file:///d:/DUT/Nam3/pbl4/code/lab/backend/app.py)) ở cổng `8080` (hoặc tạo systemd unit riêng cho app web đó):
     - Chép file `lab/backend/app.py` sang `/opt/demo-webapp/app.py` trên mỗi VM.
     - Tạo venv nhỏ chỉ cài `aiohttp` rồi chạy:
       - Trên `SentinelX-Node01`: `NODE_NAME=vm-node-01 PORT=8080 python app.py`
       - Trên `SentinelX-Node02`: `NODE_NAME=vm-node-02 PORT=8080 python app.py`
- **Tiêu chí PASS Bước 4**: Từ Laptop A chạy `curl http://<TS_VM_01>:8080/health` và `curl http://<TS_VM_02>:8080/health` đều trả về `{"status": "healthy", ...}`.

### Bước 5 — Đăng ký Node trên Dashboard & Cài `sentinelx-agent` qua Bundle Self-Service
- **Thao tác**:
  1. Trên Dashboard (`http://localhost:5174`), tạo **Project** mới (ví dụ: `PBL4 Multi-Host Demo`).
  2. Bấm **+ Thêm máy chủ** lần lượt cho 2 VM (sửa ô **Controller URL** thành `http://<TS_LAPTOP_A>:8000`):
     - Máy 1: Hostname = `vm-node-01`, Địa chỉ IP = `<TS_VM_01>`
     - Máy 2: Hostname = `vm-node-02`, Địa chỉ IP = `<TS_VM_02>`
  3. Tại Bước 2 của modal (tab **Cài chuẩn Linux (systemd)**), copy đoạn lệnh tải bundle + kiểm tra `sha256sum -c -` + `sudo python3 manage.py install ...` chạy trên từng VM; sau đó chạy `sudo python3 manage.py enroll` và dán token 1 lần từ Dashboard.
  4. Cấu hình `/etc/sentinelx-agent/agent.yaml` trên mỗi VM trước khi chạy thật:
     - Kiểm tra tên card mạng Tailscale/NAT bằng `ip -br link` (thường để bắt gói tin LAN/Tailscale chọn `tailscale0` cho traffic qua Tailscale hoặc interface thực tế nhận attack).
     - Điền `protected_cidrs: ["<TS_LAPTOP_A>/32", "127.0.0.0/8"]` (**bắt buộc** để không tự khóa Control Plane/LB).
     - Bật `network_capture_enabled: true` và `defense_executor_type: nftables`.
  5. Cấp capability tối thiểu & khởi động:
     ```bash
     sudo python3 manage.py capture-permissions --enable
     sudo python3 manage.py defense-permissions --enable
     sudo python3 manage.py check
     sudo python3 manage.py restart
     sudo python3 manage.py status
     ```
- **Tiêu chí PASS Bước 5**: Cả `vm-node-01` và `vm-node-02` hiện **Trực tuyến (ONLINE)** trên Dashboard, hiển thị đúng số CPU/RAM thật riêng của từng VM (2 vCPU / 2–4 GB RAM) và đổ đồ thị realtime.

### Bước 6 — Kích hoạt Load Balancer Pool & Chính sách Bảo vệ từ Dashboard
- **Thao tác**:
  1. Vào mục **Cân bằng tải** của Project → bật Load Balancer (đặt Endpoint `http://host.docker.internal:8080` hoặc giữ mặc định nếu đã set `SENTINELX_DEFAULT_LB_URL`), chọn thuật toán `Round Robin`, health path `/health`.
  2. Chọn thêm `vm-node-01` (port `8080`) và `vm-node-02` (port `8080`) vào Pool.
  3. Vào mục **Chính sách bảo vệ**:
     - Thêm `<TS_LAPTOP_A>/32` vào **Danh sách an toàn (Whitelist)**.
     - Bật các chính sách cần demo (ví dụ phát hiện quá tải CPU/RAM, SYN Flood / Port Scan).
- **Tiêu chí PASS Bước 6**: Gọi nhiều lần `curl http://<TS_LAPTOP_A>:8080/` từ Laptop B hoặc Laptop A thấy response luân phiên `vm-node-01` ↔ `vm-node-02`; trang **Cân bằng tải** hiển thị 2 backend khỏe mạnh và tăng số request thực tế.

### Bước 7 — Chạy Bộ Kịch bản Nghiệm thu Mức 2 & Thu thập Bằng chứng Báo cáo
Thực hiện lần lượt 4 kịch bản và chụp ảnh/lưu log đưa vào báo cáo:
1. **CPU Overload trên 1 VM thật**: gọi `POST http://<TS_VM_01>:8080/stress/cpu?duration=25` → chứng minh chỉ CPU của `vm-node-01` tăng vọt còn `vm-node-02` giữ nguyên ở mức thấp (khắc phục giới hạn dùng chung `/proc` của Mức 1) và Controller phát sinh Sự cố.
2. **LB Health Check Ejection & Recovery**: tắt web `:8080` trên `SentinelX-Node02` → sau 3 probe lỗi LB tự loại `vm-node-02` và 100% request vẫn trả `200 OK` qua `vm-node-01`; bật lại web trên `SentinelX-Node02` → sau 2 probe thành công LB tự thêm lại vào pool.
3. **Tấn công & Chặn thật bằng `nftables` trên Linux**: chạy port scan / flood có kiểm soát từ Laptop B (hoặc `SentinelX-Node02`) vào `<TS_VM_01>` (đảm bảo IP máy bắn test **không** nằm trong `protected_cidrs` hay Whitelist; địa chỉ `100.x.y.z` của Tailscale được `LocalSafetyValidator` cho phép chặn hợp lệ trong khi Controller `<TS_LAPTOP_A>` vẫn luôn được bảo vệ) → Agent phát hiện, nhận lệnh `BLOCK_IP_NFTABLES`, kiểm chứng rule thật trên VM bằng `sudo nft list table inet sentinelx`, và verify gỡ chặn tự động/thủ công trên Dashboard.
4. **Kiểm thử qua 5G Hotspot iPhone**: chuyển cả Laptop A và Laptop B sang Wi-Fi phát từ iPhone → xác nhận toàn bộ kết nối Tailscale, telemetry và LB vẫn chạy thông suốt.
