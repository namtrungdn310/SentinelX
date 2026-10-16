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
uv run python -m sentinelx_lb.main

# Linux/macOS Bash:
SENTINELX_LB_HOST=0.0.0.0 \
SENTINELX_LB_PORT=8080 \
SENTINELX_LB_BACKENDS="http://192.168.1.20:8080,http://192.168.1.30:8080" \
SENTINELX_LB_ALGORITHM=round_robin \
SENTINELX_LB_HEALTH_CHECK__ENABLED=true \
SENTINELX_LB_HEALTH_CHECK__PATH="/health" \
uv run python -m sentinelx_lb.main
```

### 1.5 Khởi động Dashboard UI
```bash
cd dashboard
npm run dev -- --host 0.0.0.0
```
Truy cập giao diện từ bất kỳ thiết bị nào qua: `http://192.168.1.10:5174`

---

## 3. Bước 2: Thiết lập Machine B và Machine C (Worker Nodes)

### 2.1 Cài đặt Workload Backend
Trên Machine B (192.168.1.20) và Machine C (192.168.1.30), chạy dịch vụ web ứng dụng (hoặc backend mẫu của lab):
```bash
# Machine B:
NODE_NAME=backend01 PORT=8080 uv run python deploy/mock_backend.py

# Machine C:
NODE_NAME=backend02 PORT=8080 uv run python deploy/mock_backend.py
```

### 2.2 Cài đặt & Chạy SentinelX Agent Daemon
Agent trên Machine B và Machine C tự động thực hiện outbound HTTP tới Machine A:
```bash
# Trên Machine B:
SENTINELX_CONTROLLER_URL="http://192.168.1.10:8000" \
SENTINELX_NODE_HOSTNAME="machine-b-node" \
uv run python -m sentinelx_agent.main

# Trên Machine C:
SENTINELX_CONTROLLER_URL="http://192.168.1.10:8000" \
SENTINELX_NODE_HOSTNAME="machine-c-node" \
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
