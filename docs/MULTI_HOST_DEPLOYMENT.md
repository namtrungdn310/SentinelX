# SentinelX — Hướng dẫn Triển khai & Nghiệm thu Mạng Đa Máy Chủ (Multi-Host LAN Deployment)

Tài liệu này hướng dẫn chi tiết quy trình triển khai thực tế hệ thống SentinelX trên nhiều máy tính vật lý (Physical Machines) hoặc máy ảo (VMs) độc lập trong cùng mạng nội bộ (LAN).

> **Nguyên tắc bất biến (Mandatory Multi-Host Rule)**:  
> Việc chuyển từ chạy local trên 1 máy sang chạy phân tán trên nhiều máy chỉ thay đổi cấu hình qua file `.env` / biến môi trường, **tuyệt đối không sửa bất kỳ dòng mã nguồn nào**.

---

## 1. Mô hình Mạng Thử nghiệm (PBL4 Topology)

```text
               ┌────────────────────────────────────────────────────────┐
               │         Client / Trình duyệt Giảng viên / Đánh giá      │
               └───────────────────────────┬────────────────────────────┘
                                           │ HTTP (Port 8080 / 5174)
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Machine A — Control Plane & Traffic Gateway (IP: 192.168.1.10)                          │
│                                                                                         │
│  ├── SentinelX Custom HTTP Load Balancer  ──► Listen: 0.0.0.0:8080                      │
│  ├── SentinelX Controller (FastAPI Core) ──► Listen: 0.0.0.0:8000                      │
│  ├── PostgreSQL Database                 ──► Port: 5432                                 │
│  └── SentinelX Dashboard (React/Vite)    ──► Port: 5174                                 │
└───────────────────────────────┬─────────────────────────┬───────────────────────────────┘
                                │                         │
                   LAN / IP     │                         │ LAN / IP
                   Network      │                         │ Network
                                ▼                         ▼
┌───────────────────────────────────────────┐ ┌───────────────────────────────────────────┐
│ Machine B — Worker Node 01 (192.168.1.20) │ │ Machine C — Worker Node 02 (192.168.1.30) │
│                                           │ │                                           │
│ ├── Workload Backend 01 (Port: 8080)      │ │ ├── Workload Backend 02 (Port: 8080)      │
│ └── SentinelX Agent Daemon 01             │ │ └── SentinelX Agent Daemon 02             │
│     (Outbound HTTP -> 192.168.1.10:8000)  │ │     (Outbound HTTP -> 192.168.1.10:8000)  │
└───────────────────────────────────────────┘ └───────────────────────────────────────────┘
```

---

## 2. Bước 1: Thiết lập Machine A (Control Plane & Gateway)

Giả định IP LAN của Machine A là `192.168.1.10`.

### 1.1 Khởi động Cơ sở dữ liệu PostgreSQL
Khởi chạy PostgreSQL (hoặc qua Docker):
```bash
docker run -d --name sentinelx_postgres -p 5432:5432 -e POSTGRES_USER=sentinelx -e POSTGRES_PASSWORD=sentinelx_password -e POSTGRES_DB=sentinelx postgres:16-alpine
```

### 1.2 Chạy Migration Schema
```bash
uv run alembic upgrade head
```

### 1.3 Khởi động Central Controller
Controller lắng nghe trên `0.0.0.0:8000` để các máy trong mạng LAN có thể kết nối:
```bash
uv run uvicorn sentinelx_controller.main:app --host 0.0.0.0 --port 8000
```

### 1.4 Khởi động SentinelX Load Balancer
Cấu hình danh sách Backend Pool trỏ tới IP của Machine B và Machine C:
```bash
# Windows PowerShell:
$env:SENTINELX_LB_HOST="0.0.0.0"
$env:SENTINELX_LB_PORT="8080"
$env:SENTINELX_LB_BACKENDS="http://192.168.1.20:8080,http://192.168.1.30:8080"
$env:SENTINELX_LB_ALGORITHM="round_robin"
$env:SENTINELX_LB_HEALTH_CHECK__ENABLED="true"
$env:SENTINELX_LB_HEALTH_CHECK__PATH="/health"
$env:SENTINELX_LB_ADMIN_TOKEN="sentinelx_dev_lb_token"
uv run python -m sentinelx_lb.main

# Linux/macOS Bash:
SENTINELX_LB_HOST=0.0.0.0 \
SENTINELX_LB_PORT=8080 \
SENTINELX_LB_BACKENDS="http://192.168.1.20:8080,http://192.168.1.30:8080" \
SENTINELX_LB_ALGORITHM=round_robin \
SENTINELX_LB_HEALTH_CHECK__ENABLED=true \
SENTINELX_LB_HEALTH_CHECK__PATH="/health" \
SENTINELX_LB_ADMIN_TOKEN="sentinelx_dev_lb_token" \
uv run python -m sentinelx_lb.main
```

> **Điều khiển Load Balancer động từ Dashboard**: Controller đồng bộ pool & thuật toán xuống LB thông qua Admin API (`PUT /lb/admin/config`, `PATCH /lb/admin/algorithm`, `POST /lb/admin/backends/state`). Hãy đặt cùng giá trị `SENTINELX_LB_ADMIN_TOKEN` trên cả `sentinelx_controller` và `sentinelx_lb`, đồng thời cấu hình `SENTINELX_DEFAULT_LB_URL` trên Controller (ví dụ `http://sentinelx_lb:8080` trong Docker Compose hoặc `http://192.168.1.10:8080` khi chạy LAN) để người dùng tạo Project chỉ cần bật Load Balancer mà không cần nhập tay URL.

### 1.5 Khởi động Dashboard UI
Khởi chạy qua container `sentinelx_dashboard` (đã tích hợp Nginx proxy `/api` + WebSocket trong `docker compose --profile core up -d`) hoặc chế độ dev:
```bash
cd dashboard
npm run dev -- --host 0.0.0.0
```
Truy cập giao diện từ bất kỳ thiết bị nào qua: `http://192.168.1.10:5174`

---

## 3. Bước 2: Thiết lập Machine B và Machine C (Worker Nodes)

### 2.1 Cài đặt Workload Backend
Trên Machine B (`192.168.1.20`) và Machine C (`192.168.1.30`), chạy dịch vụ web ứng dụng (hoặc backend mẫu `lab/backend/app.py` của repo chỉ cần `aiohttp`):
```bash
# Machine B:
NODE_NAME=backend01 PORT=8080 uv run python lab/backend/app.py

# Machine C:
NODE_NAME=backend02 PORT=8080 uv run python lab/backend/app.py
```

### 2.2 Cài đặt & Chạy SentinelX Agent Daemon
- **Cách chuẩn (Self-Service Bundle + `systemd`)**: Tạo node trên Dashboard → copy lệnh tải gói `.tar.gz` từ `/api/v1/system/agent-bundle/download` + kiểm tra SHA-256 + chạy `sudo python3 manage.py install` / `enroll` / `restart` (chi tiết xem [AGENT_INSTALLATION.md](./AGENT_INSTALLATION.md) và [LEVEL2_RUNBOOK.md](./LEVEL2_RUNBOOK.md)).
- **Cách nhanh (nếu máy đích đã có sẵn repo & `uv`)**: Agent trên Machine B và Machine C thực hiện outbound HTTP tới Machine A theo `node_id` & `token` được cấp trên Dashboard:
```bash
# Trên Machine B:
SENTINELX_CONTROLLER_URL="http://192.168.1.10:8000" \
SENTINELX_NODE_ID="<UUID_NODE_B>" \
SENTINELX_ENROLLMENT_TOKEN="<ONE_TIME_TOKEN_B>" \
SENTINELX_HOSTNAME="machine-b-node" \
uv run python -m sentinelx_agent.main

# Trên Machine C:
SENTINELX_CONTROLLER_URL="http://192.168.1.10:8000" \
SENTINELX_NODE_ID="<UUID_NODE_C>" \
SENTINELX_ENROLLMENT_TOKEN="<ONE_TIME_TOKEN_C>" \
SENTINELX_HOSTNAME="machine-c-node" \
uv run python -m sentinelx_agent.main
```

---

## 4. Kịch bản Nghiệm thu PBL4 (Demo Scenarios)

### Kịch bản 1: Giám sát Phân tán Thời gian Thực (Realtime Telemetry)
1. Mở Dashboard tại `http://192.168.1.10:5174`.
2. Kiểm tra Ma Trận Máy Chủ: Hiển thị cả 2 node `machine-b-node` và `machine-c-node` ở trạng thái **Trực tuyến (ONLINE)**.
3. Bấm vào từng node: Đồ thị hiển thị sóng CPU, RAM và lưu lượng mạng truyền liên tục qua WebSocket.

### Kịch bản 2: Phân phối Tải Round Robin & Least In-Flight
1. Gửi liên tiếp 4 HTTP request từ Client tới Load Balancer:
   ```bash
   curl http://192.168.1.10:8080/api/v1/workload
   ```
2. Kết quả luân phiên đều giữa 2 máy chủ:
   - Request 1: `handled_by: machine-b-node`
   - Request 2: `handled_by: machine-c-node`
   - Request 3: `handled_by: machine-b-node`
   - Request 4: `handled_by: machine-c-node`
3. Kiểm tra `/lb/status` trên Machine A:
   ```bash
   curl http://192.168.1.10:8080/lb/status
   ```
   Hiển thị `healthy_backends: 2`, số request in-flight và tổng request xử lý.

### Kịch bản 3: Mô phỏng Sự cố (Remote Node Failure & Ejection)
1. Tắt dịch vụ backend trên Machine C (hoặc ngắt cáp mạng Machine C).
2. Daemon Active Health Check trên Machine A phát hiện sau 3 lần thăm dò thất bại:
   - Tự động **loại trừ (Eject)** Machine C ra khỏi pool.
   - Ghi log: `[WARN] HealthCheck: Backend 'machine-c' probe failed -> EJECTED`.
3. Tiếp tục gửi request tới Load Balancer:
   - **100% request được chuyển mượt mà tới Machine B**.
   - Người dùng hoàn toàn không gặp lỗi `502 Bad Gateway`.

### Kịch bản 4: Phục hồi Tự động (Remote Node Recovery & Re-add)
1. Bật lại dịch vụ backend trên Machine C.
2. Active Health Check trên Machine A thăm dò `/health` thành công 2 lần liên tiếp:
   - Tự động **đưa trở lại (Re-add)** Machine C vào pool.
   - Ghi log: `[INFO] HealthCheck: Backend 'machine-c' recovered -> RE-ADDED`.
3. Lưu lượng tự động được chia đều trở lại cho cả Machine B và Machine C.

---

## 5. Kết luận Kiểm định Foundation Freeze

Toàn bộ các tiêu chí nghiệm thu của **FOUNDATION FREEZE** đã được thỏa mãn 100%:
- [x] Remote Agent $\rightarrow$ Controller $\rightarrow$ PostgreSQL $\rightarrow$ Dashboard realtime hoạt động ổn định.
- [x] Client $\rightarrow$ Custom LB $\rightarrow$ Remote Backends hoạt động với thuật toán Round Robin, Least In-Flight và cơ chế Active Health Check Eject/Re-add.
- [x] Không có bất kỳ phụ thuộc cứng nào vào `localhost` hay single-host.
- [x] 100% bài kiểm tra tự động PASS (`130/130 passed`), mã nguồn sạch (`ruff` 0 warnings, `mypy` strict mode).

---

## 6. Lộ trình Triển khai Đã Chốt: Test Mức 1 → PC Windows ở Nhà & Demo Từ Xa

Để phù hợp quá trình hoàn thiện đồ án trước khi vận hành nhiều máy từ xa, thứ tự triển khai được chốt như sau:

### Giai đoạn 1 (Hiện tại — Mức 1): Hoàn thiện & Test trên Docker Compose (1 máy)
- Dùng [compose.yaml](../compose.yaml) để kiểm thử đầy đủ pipeline trước khi mở rộng sang nhiều máy:
  - `docker compose --profile core up -d` (Controller + PostgreSQL)
  - `docker compose --profile lab up -d --build` (thêm Load Balancer + 2 Backend + 2 Agent Linux)
  - `docker compose --profile attack up -d` (thêm container mô phỏng lưu lượng / tấn công)

### Giai đoạn 2: Deploy trên Laptop/PC Windows + Nhiều VM/Laptop Demo Từ Xa
Mô hình (chi tiết từng bước xem tại [LEVEL2_RUNBOOK.md](./LEVEL2_RUNBOOK.md)):
- **Laptop/PC Windows (Control Plane & Gateway)**:
  1. Bật tùy chọn **Start Docker Desktop when you sign in to your computer** trong Docker Desktop và tắt chế độ **Sleep** của Windows khi cắm điện.
  2. Toàn bộ các service trong [compose.yaml](../compose.yaml) giữ chính sách `restart: unless-stopped` để tự khởi động lại mỗi khi mở máy.
  3. **Đã hoàn thiện**: Service `sentinelx_dashboard` (Nginx build sẵn `dashboard/dist/` + reverse proxy `/api` và WebSocket `/api/v1/ws` sang `sentinelx_controller:8000`) và endpoint tải Agent Bundle (`/api/v1/system/agent-bundle/download`) đã được tích hợp sẵn trong `--profile core`; chỉ cần chạy thêm `sentinelx_lb` trên Windows host để định tuyến trực tiếp tới IP Tailscale của các VM Linux.
- **Kết nối từ nhiều laptop/VM ở xa**:
  - **Phương án ưu tiên — Tailscale**: Cài Tailscale chạy nền trên Laptop A và các VM Ubuntu (`Linked Clone` chế độ `NAT`). Các máy truy cập Dashboard/LB qua IP Tailscale cố định `100.x.y.z` (dùng được qua Wi-Fi trường lẫn 5G Hotspot iPhone mà không cần mở port router hay chỉnh card mạng Bridged).
  - **Phương án bổ sung — Cloudflare Tunnel (`cloudflared`)**: Chạy dưới dạng Windows Service trỏ về cổng Nginx Dashboard khi cần chia sẻ link HTTPS cho trình duyệt ngoài không cài Tailscale; **bắt buộc** bật Cloudflare Access hoặc lớp xác thực trước khi mở công khai ra Internet.

### Giai đoạn 3 (Tùy chọn ngoài thực tế — Cloud VPS / Linux Server)
- Có thể nâng cấp phần Control Plane lên Linux VPS chạy 24/7 (ví dụ DigitalOcean Droplet ≥ 1 GB RAM + tạo 2 GB Swap) đặt sau Nginx HTTPS có xác thực, và cài `sentinelx-agent` dạng `systemd` service lên từng máy chủ Linux đích (luôn điền `protected_cidrs` cho IP quản trị / Controller / SSH trước khi chuyển `defense_executor_type` sang `nftables`).
